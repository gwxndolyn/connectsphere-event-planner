"""US31 (SCRUM-107): a user reads their own notifications, newest first, and marks them read."""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.notification.models import Notification
from app.user.models import User, UserRole
from tests.event.test_event_request_clarification_api import make_request
from tests.event.test_event_requests import auth
from tests.factories import NOW, make_attendee, make_user

pytestmark = pytest.mark.anyio

URL = "/api/v1/me/notifications"


def note(
    db: Session,
    user: User,
    *,
    message: str = "Your request ER-2026-000101 was approved.",
    event: Event | None = None,
    name: str | None = "Alumni night",
    at: datetime = NOW,
    read: bool = False,
    kind: str = "request_decided",
) -> Notification:
    row = Notification(
        user_id=user.id,
        kind=kind,
        event_id=event.id if event else None,
        event_name=name,
        message=message,
        created_at=at,
        read_at=at if read else None,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


# --- AC 2: only mine, newest first, with the event, what happened and when ---


async def test_tc_us31_20_the_list_is_my_own_newest_first_with_event_what_happened_and_when(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = make_request(db, organiser, EventStatus.APPROVED)
    older = note(db, organiser, message="Older", event=event, at=NOW - timedelta(hours=2), read=True)
    newer = note(db, organiser, message="Newer", event=event, at=NOW - timedelta(hours=1))
    note(db, coordinator, message="Someone else's")

    response = await client.get(URL, headers=auth(organiser))

    assert response.status_code == 200
    body = response.json()
    assert [n["message"] for n in body["notifications"]] == ["Newer", "Older"]
    assert body["notifications"][0] == {
        "id": str(newer.id),
        "kind": "request_decided",
        "event_id": str(event.id),
        "event_name": "Alumni night",
        "message": "Newer",
        "created_at": (NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "read": False,
        "can_open": True,
    }
    assert body["notifications"][1]["id"] == str(older.id) and body["notifications"][1]["read"] is True
    assert "Someone else's" not in response.text


async def test_tc_us31_21_someone_with_nothing_gets_an_empty_list(client: AsyncClient, organiser: User) -> None:
    response = await client.get(URL, headers=auth(organiser))

    assert (response.status_code, response.json()) == (200, {"notifications": [], "unread_count": 0})


async def test_tc_us31_22_every_role_reads_its_own_and_nobody_else_does(client: AsyncClient, db: Session) -> None:
    holders = [make_user(db, role) for role in UserRole if role.value != "operations_manager"]
    holders.append(make_user(db, UserRole.ORGANISER, UserRole.COORDINATOR))
    for holder in holders:
        note(db, holder, message=f"For {holder.id}")

    for holder in holders:
        response = await client.get(URL, headers=auth(holder))
        assert [n["message"] for n in response.json()["notifications"]] == [f"For {holder.id}"]
    attendee = make_attendee(db)
    assert (await client.get(URL, headers={"X-User-Id": str(attendee.id)})).status_code == 200
    assert (await client.get(URL)).status_code == 401
    inactive = make_user(db, UserRole.ORGANISER, active=False)
    assert (await client.get(URL, headers=auth(inactive))).status_code == 403


# --- AC 3: unread ---


async def test_tc_us31_23_the_unread_count_covers_every_unread_one_not_just_the_ones_listed(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    for index in range(5):
        note(db, organiser, message=f"n{index}", at=NOW - timedelta(minutes=index), read=index == 4)

    listed = (await client.get(f"{URL}?limit=2", headers=auth(organiser))).json()
    count = await client.get(f"{URL}/unread-count", headers=auth(organiser))

    assert [n["message"] for n in listed["notifications"]] == ["n0", "n1"]
    assert listed["unread_count"] == 4
    assert (count.status_code, count.json()) == (200, {"unread_count": 4})


async def test_tc_us31_24_unread_only_leaves_out_what_was_read(client: AsyncClient, db: Session, organiser: User) -> None:
    note(db, organiser, message="Read", read=True, at=NOW - timedelta(minutes=1))
    note(db, organiser, message="Unread")

    response = await client.get(f"{URL}?unread_only=true", headers=auth(organiser))

    assert [n["message"] for n in response.json()["notifications"]] == ["Unread"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=abc"])
async def test_tc_us31_25_a_limit_outside_1_to_100_is_refused(client: AsyncClient, organiser: User, query: str) -> None:
    assert (await client.get(f"{URL}?{query}", headers=auth(organiser))).status_code == 422


# --- AC 4: mark read ---


async def test_tc_us31_26_marking_one_read_keeps_the_first_time_and_lowers_the_count(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    first = note(db, organiser, message="First", at=NOW - timedelta(minutes=2))
    note(db, organiser, message="Second", at=NOW - timedelta(minutes=1))

    done = await client.post(f"{URL}/{first.id}/read", headers=auth(organiser))
    again = await client.post(f"{URL}/{first.id}/read", headers=auth(organiser))

    assert (done.status_code, done.json()["read"], again.status_code, again.json()["read"]) == (200, True, 200, True)
    db.refresh(first)
    assert first.read_at == NOW
    assert (await client.get(f"{URL}/unread-count", headers=auth(organiser))).json() == {"unread_count": 1}


async def test_tc_us31_27_somebody_elses_or_an_unknown_notification_is_404_and_stays_unread(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    theirs = note(db, coordinator)

    for target in (theirs.id, uuid.uuid4()):
        assert (await client.post(f"{URL}/{target}/read", headers=auth(organiser))).status_code == 404
    assert (await client.post(f"{URL}/{theirs.id}/read")).status_code == 401
    db.refresh(theirs)
    assert theirs.read_at is None


async def test_tc_us31_28_mark_all_read_reads_mine_and_only_mine(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    note(db, organiser, message="a")
    note(db, organiser, message="b", read=True, at=NOW - timedelta(minutes=1))
    note(db, organiser, message="c", at=NOW - timedelta(minutes=2))
    theirs = note(db, coordinator)

    first = await client.post(f"{URL}/read-all", headers=auth(organiser))
    second = await client.post(f"{URL}/read-all", headers=auth(organiser))

    assert (first.status_code, first.json()) == (200, {"updated": 2, "unread_count": 0})
    assert second.json() == {"updated": 0, "unread_count": 0}
    db.refresh(theirs)
    assert theirs.read_at is None
    assert (await client.post(f"{URL}/read-all")).status_code == 401


# --- AC 5: open the related event ---


async def test_tc_us31_29_can_open_follows_who_may_read_the_request(client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    other_organiser = make_user(db, UserRole.ORGANISER)
    coordinator = make_user(db, UserRole.COORDINATOR)
    other_coordinator = make_user(db, UserRole.COORDINATOR)
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    staff = make_user(db, UserRole.VENUE_STAFF)
    event = make_request(db, organiser, EventStatus.SUBMITTED, coordinator=coordinator)
    draft = make_request(db, organiser, EventStatus.DRAFT)
    expected = {organiser: True, coordinator: True, lead: True, other_organiser: False, other_coordinator: False, staff: False}
    for reader in expected:
        note(db, reader, message="about the request", event=event)
    note(db, organiser, message="draft", event=draft, at=NOW - timedelta(minutes=1))
    note(db, organiser, message="no event", event=None, name=None, at=NOW - timedelta(minutes=2))

    for reader, can_open in expected.items():
        rows = (await client.get(URL, headers=auth(reader))).json()["notifications"]
        by_message = {row["message"]: row for row in rows}
        assert by_message["about the request"]["can_open"] is can_open
        # The notice still names the event whether or not the reader may open it.
        assert by_message["about the request"]["event_id"] == str(event.id)
    rows = {r["message"]: r for r in (await client.get(URL, headers=auth(organiser))).json()["notifications"]}
    assert (rows["draft"]["can_open"], rows["no event"]["can_open"], rows["no event"]["event_id"]) == (True, False, None)


async def test_tc_us31_30_a_read_notification_reports_can_open_too(client: AsyncClient, db: Session, organiser: User) -> None:
    event = make_request(db, organiser, EventStatus.APPROVED)
    row = note(db, organiser, event=event)

    response = await client.post(f"{URL}/{row.id}/read", headers=auth(organiser))

    assert response.json()["can_open"] is True


# --- the table ---


def test_tc_us31_31_the_database_refuses_a_blank_kind_or_message(db: Session, organiser: User) -> None:
    for kind, message in (("", "x"), ("request_decided", "  ")):
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(Notification(user_id=organiser.id, kind=kind, message=message))
                db.flush()


def test_tc_us31_33_the_table_has_no_foreign_keys_so_a_notice_never_waits_on_the_caller_s_locks(engine) -> None:
    from sqlalchemy import inspect

    assert inspect(engine).get_foreign_keys("notifications") == []


def test_tc_us31_32_a_new_notification_is_unread_and_stamped(db: Session, organiser: User) -> None:
    row = Notification(user_id=organiser.id, kind="request_decided", message="Hello")
    db.add(row)
    db.flush()
    db.refresh(row)

    assert row.read_at is None and row.created_at is not None
    assert db.scalars(select(Notification).where(Notification.user_id == organiser.id)).all() == [row]
