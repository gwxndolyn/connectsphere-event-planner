"""US10e (SCRUM-83): the Lead reassigns an event to another coordinator."""

import logging
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentRequestLine
from app.event.models import AssignmentKind, CoordinatorAssignment, Event, EventStatus
from app.user.models import User, UserRole
from app.venue.models import VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.equipment.test_equipment_schema import make_type
from tests.event.test_coordinator_assignment_api import assign
from tests.event.test_event_request_clarification_api import BODY as CLARIFICATION, make_request, make_user, send
from tests.event.test_event_requests import auth
from tests.factories import NOW, make_event, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

DATES = [(NOW + timedelta(days=7)).date()]
REASON = "Casey is on leave for the event week"


def reassign_url(request_id: uuid.UUID) -> str:
    return f"/api/v1/event-requests/{request_id}/reassignment"


async def reassign(
    client: AsyncClient,
    user: User | None,
    request_id: uuid.UUID,
    coordinator_id: uuid.UUID,
    reason: str | None = REASON,
):
    body: dict[str, object] = {"coordinator_id": str(coordinator_id)}
    if reason is not None:
        body["reason"] = reason
    return await client.post(reassign_url(request_id), headers=auth(user) if user else {}, json=body)


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def lead(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR_LEAD)


@pytest.fixture
def casey(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.full_name = "Casey Tan"
    db.flush()
    return user


@pytest.fixture
def jordan(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.full_name = "Jordan Lim"
    db.flush()
    return user


@pytest.fixture
def event(db: Session, organiser: User, casey: User) -> Event:
    """An under-review request that Casey owns."""
    request = make_request(db, organiser, EventStatus.UNDER_REVIEW)
    request.request_reference = f"ER-2026-{uuid.uuid4().int % 900000 + 100000}"
    request.preferred_dates = DATES
    request.coordinator_id = casey.id
    db.flush()
    return request


def records(db: Session, event: Event) -> list[CoordinatorAssignment]:
    return list(db.scalars(select(CoordinatorAssignment).where(CoordinatorAssignment.event_id == event.id)))


async def test_tc_us10e_01_the_lead_moves_the_event_and_the_history_records_it(
    client: AsyncClient, db: Session, event: Event, lead: User, casey: User, jordan: User
) -> None:
    response = await reassign(client, lead, event.id, jordan.id)

    assert response.status_code == 200
    assert response.json()["coordinator"] == {"id": str(jordan.id), "name": "Jordan Lim"}
    assert response.json()["status"] == "under_review"  # reassigning is not a status change
    db.refresh(event)
    assert event.coordinator_id == jordan.id
    [record] = records(db, event)
    assert (record.kind, record.coordinator_id, record.assigned_by_user_id, record.reason) == (
        AssignmentKind.REASSIGNMENT,
        jordan.id,
        lead.id,
        REASON,
    )
    history = await client.get(f"/api/v1/event-requests/{event.id}/assignment-history", headers=auth(lead))
    assert [(row["kind"], row["reason"]) for row in history.json()["assignments"]] == [("reassignment", REASON)]


@pytest.mark.parametrize(
    "status",
    [
        EventStatus.UNDER_REVIEW,
        EventStatus.AWAITING_CLARIFICATION,
        EventStatus.APPROVED,
        EventStatus.PLANNING,
        EventStatus.CONFIRMED,
    ],
)
async def test_tc_us10e_02_every_active_status_can_be_reassigned(
    client: AsyncClient, db: Session, event: Event, lead: User, jordan: User, status: EventStatus
) -> None:
    event.status = status
    if status in (EventStatus.PLANNING, EventStatus.CONFIRMED):  # events_final_fields_required
        event.start_at, event.end_at = NOW + timedelta(days=7), NOW + timedelta(days=7, hours=2)
        event.capacity, event.delivery_mode = 30, "online"
    db.flush()

    response = await reassign(client, lead, event.id, jordan.id)

    assert response.status_code == 200
    assert response.json()["status"] == status.value


@pytest.mark.parametrize("status", [EventStatus.REJECTED, EventStatus.CANCELLED, EventStatus.COMPLETED])
async def test_tc_us10e_03_rejected_cancelled_and_completed_events_are_refused(
    client: AsyncClient, db: Session, event: Event, lead: User, casey: User, jordan: User, status: EventStatus
) -> None:
    event.status = status
    if status != EventStatus.REJECTED:
        event.start_at, event.end_at = NOW + timedelta(days=7), NOW + timedelta(days=7, hours=2)
        event.capacity, event.delivery_mode = 30, "online"
    db.flush()

    response = await reassign(client, lead, event.id, jordan.id)

    assert response.status_code == 409
    assert response.json()["code"] == "REASSIGNMENT_NOT_ALLOWED"
    db.refresh(event)
    assert event.coordinator_id == casey.id
    assert records(db, event) == []


async def test_tc_us10e_04_an_unassigned_request_must_be_assigned_not_reassigned(
    client: AsyncClient, db: Session, organiser: User, lead: User, jordan: User
) -> None:
    unassigned = make_request(db, organiser, EventStatus.SUBMITTED)

    response = await reassign(client, lead, unassigned.id, jordan.id)

    assert response.status_code == 409
    assert response.json()["code"] == "REASSIGNMENT_NOT_ALLOWED"


async def test_tc_us10e_05_a_draft_or_unknown_request_is_not_found(
    client: AsyncClient, db: Session, organiser: User, lead: User, jordan: User
) -> None:
    draft = make_request(db, organiser, EventStatus.DRAFT)

    assert (await reassign(client, lead, draft.id, jordan.id)).status_code == 404
    assert (await reassign(client, lead, uuid.uuid4(), jordan.id)).status_code == 404


async def test_tc_us10e_06_the_same_coordinator_is_refused_with_a_reason_and_nothing_changes(
    client: AsyncClient, db: Session, event: Event, lead: User, casey: User, notifier: FakeNotifier
) -> None:
    response = await reassign(client, lead, event.id, casey.id)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_COORDINATOR"
    assert response.json()["reason"] == "same_coordinator"
    db.refresh(event)
    assert event.coordinator_id == casey.id
    assert records(db, event) == []
    assert notifier.reassignments == []


@pytest.mark.parametrize("target", ["lead", "organiser", "inactive", "unknown"])
async def test_tc_us10e_07_only_an_active_coordinator_can_be_picked(
    client: AsyncClient, db: Session, event: Event, organiser: User, lead: User, casey: User, target: str
) -> None:
    picked = {
        "lead": lead.id,
        "organiser": organiser.id,
        "inactive": make_user(db, UserRole.COORDINATOR, active=False).id,
        "unknown": uuid.uuid4(),
    }[target]

    response = await reassign(client, lead, event.id, picked)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_COORDINATOR"
    db.refresh(event)
    assert event.coordinator_id == casey.id
    assert records(db, event) == []


@pytest.mark.parametrize("reason", [None, "", "   "])
async def test_tc_us10e_08_a_reason_is_required(
    client: AsyncClient, db: Session, event: Event, lead: User, casey: User, jordan: User, reason: str | None
) -> None:
    response = await reassign(client, lead, event.id, jordan.id, reason)

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": ["reason"]}
    db.refresh(event)
    assert event.coordinator_id == casey.id
    assert records(db, event) == []


async def test_tc_us10e_09_the_reason_is_trimmed_and_capped(
    client: AsyncClient, db: Session, event: Event, lead: User, jordan: User
) -> None:
    too_long = await reassign(client, lead, event.id, jordan.id, "x" * 1001)
    assert too_long.status_code == 422

    await reassign(client, lead, event.id, jordan.id, f"  {REASON}  ")

    [record] = records(db, event)
    assert record.reason == REASON


@pytest.mark.parametrize("role", [UserRole.COORDINATOR, UserRole.ORGANISER, UserRole.VENUE_STAFF, None])
async def test_tc_us10e_10_only_the_lead_can_reassign(
    client: AsyncClient, db: Session, event: Event, casey: User, jordan: User, role: UserRole | None
) -> None:
    caller = make_user(db, role) if role else None
    if role == UserRole.COORDINATOR:
        caller = casey  # a coordinator can't hand their own event over directly (AC 6)

    response = await reassign(client, caller, event.id, jordan.id)

    assert response.status_code == (403 if caller else 401)
    db.refresh(event)
    assert event.coordinator_id == casey.id
    assert records(db, event) == []


async def test_tc_us10e_11_the_previous_coordinator_loses_the_event_and_the_new_one_gains_it(
    client: AsyncClient, db: Session, event: Event, lead: User, casey: User, jordan: User
) -> None:
    url = f"/api/v1/event-requests/{event.id}"
    assert (await client.get(url, headers=auth(casey))).status_code == 200
    assert str(event.id) in {row["id"] for row in (await client.get("/api/v1/event-requests", headers=auth(casey))).json()["event_requests"]}

    await reassign(client, lead, event.id, jordan.id)

    assert (await client.get(url, headers=auth(casey))).status_code == 404
    assert (await client.get(f"{url}/clarifications", headers=auth(casey))).status_code == 404
    assert str(event.id) not in {row["id"] for row in (await client.get("/api/v1/event-requests", headers=auth(casey))).json()["event_requests"]}
    assert (await send(client, casey, event.id)).status_code == 404
    assert (await client.get(url, headers=auth(jordan))).status_code == 200
    assert str(event.id) in {row["id"] for row in (await client.get("/api/v1/event-requests", headers=auth(jordan))).json()["event_requests"]}
    assert (await send(client, jordan, event.id, CLARIFICATION)).status_code == 201


async def test_tc_us10e_12_the_clarification_thread_moves_with_the_event(
    client: AsyncClient, db: Session, event: Event, lead: User, casey: User, jordan: User
) -> None:
    event.status = EventStatus.UNDER_REVIEW
    db.flush()
    await send(client, casey, event.id, CLARIFICATION)

    await reassign(client, lead, event.id, jordan.id)

    thread = await client.get(f"/api/v1/event-requests/{event.id}/clarifications", headers=auth(jordan))
    assert thread.status_code == 200
    [message] = thread.json()["clarifications"]
    assert message["comment"] == CLARIFICATION["comment"]


async def test_tc_us10e_13_venue_requests_move_and_the_new_coordinator_manages_them(
    client: AsyncClient, db: Session, lead: User, casey: User, jordan: User
) -> None:
    planned = make_event(db, status=EventStatus.APPROVED, coordinator_id=casey.id)
    booking = make_venue_booking(db, event=planned, venue=make_venue(db), user=casey)

    await reassign(client, lead, planned.id, jordan.id)

    listed = await client.get(f"/api/v1/events/{planned.id}/venue-bookings", headers=auth(jordan))
    assert [row["id"] for row in listed.json()["bookings"]] == [str(booking.id)]
    assert (await client.get(f"/api/v1/events/{planned.id}/venue-bookings", headers=auth(casey))).status_code == 404
    url = f"/api/v1/venue-bookings/{booking.id}/withdraw"
    # D20: the booking stays Casey's request, but only the event's coordinator manages it now.
    assert (await client.post(url, headers=auth(casey))).status_code == 404
    withdrawn = await client.post(url, headers=auth(jordan))
    assert withdrawn.status_code == 200
    db.refresh(booking)
    assert booking.status == VenueBookingStatus.WITHDRAWN


async def test_tc_us10e_14_equipment_requests_move_and_the_new_coordinator_manages_them(
    client: AsyncClient, db: Session, lead: User, casey: User, jordan: User
) -> None:
    planned = make_event(db, status=EventStatus.PLANNING, coordinator_id=casey.id)
    line = EquipmentRequestLine(
        event_id=planned.id, equipment_type_id=make_type(db).id, quantity=2, requested_by_user_id=casey.id
    )
    db.add(line)
    db.flush()

    await reassign(client, lead, planned.id, jordan.id)

    listed = await client.get(f"/api/v1/events/{planned.id}/equipment-lines", headers=auth(jordan))
    assert [row["id"] for row in listed.json()["lines"]] == [str(line.id)]
    assert (await client.get(f"/api/v1/events/{planned.id}/equipment-lines", headers=auth(casey))).status_code == 404
    assert (await client.delete(f"/api/v1/equipment-lines/{line.id}", headers=auth(casey))).status_code == 404
    assert (await client.delete(f"/api/v1/equipment-lines/{line.id}", headers=auth(jordan))).status_code == 204


async def test_tc_us10e_15_the_history_keeps_every_step_newest_first(
    client: AsyncClient, db: Session, organiser: User, lead: User, casey: User, jordan: User
) -> None:
    fresh = make_request(db, organiser, EventStatus.SUBMITTED)
    await assign(client, lead, fresh.id, casey.id)
    await reassign(client, lead, fresh.id, jordan.id, "First move")
    # created_at is the transaction's start; the test shares one, so space the rows out.
    for index, record in enumerate(sorted(records(db, fresh), key=lambda r: r.kind != AssignmentKind.ASSIGNMENT)):
        record.created_at = NOW + timedelta(hours=index)
    db.flush()
    await reassign(client, lead, fresh.id, casey.id, "Moving back")
    latest = [r for r in records(db, fresh) if r.reason == "Moving back"][0]
    latest.created_at = NOW + timedelta(hours=5)
    db.flush()

    response = await client.get(f"/api/v1/event-requests/{fresh.id}/assignment-history", headers=auth(lead))

    rows = response.json()["assignments"]
    assert [(row["kind"], row["coordinator"]["id"], row["reason"]) for row in rows] == [
        ("reassignment", str(casey.id), "Moving back"),
        ("reassignment", str(jordan.id), "First move"),
        ("assignment", str(casey.id), None),
    ]


async def test_tc_us10e_16_the_organiser_and_both_coordinators_are_told(
    client: AsyncClient, db: Session, event: Event, organiser: User, lead: User, casey: User, jordan: User,
    notifier: FakeNotifier,
) -> None:
    event.name = "Alumni night"
    db.flush()

    await reassign(client, lead, event.id, jordan.id)

    by_recipient = {n["recipient"]: n for n in notifier.reassignments}
    assert set(by_recipient) == {"new_coordinator", "previous_coordinator", "organiser"}
    assert len(notifier.reassignments) == 3  # no copy to the Lead
    assert by_recipient["new_coordinator"]["email"] == jordan.email
    assert by_recipient["previous_coordinator"]["email"] == casey.email
    assert by_recipient["organiser"]["email"] == organiser.email
    for notice in notifier.reassignments:
        assert notice["request_reference"] == event.request_reference
        assert notice["event_name"] == "Alumni night"
        assert notice["previous_coordinator_name"] == "Casey Tan"
        assert notice["new_coordinator_name"] == "Jordan Lim"
        assert notice["event_dates"] == DATES
        assert notice["reason"] == REASON


async def test_tc_us10e_17_a_refused_reassignment_notifies_no_one(
    client: AsyncClient, db: Session, event: Event, lead: User, casey: User, notifier: FakeNotifier
) -> None:
    await reassign(client, lead, event.id, casey.id)
    await reassign(client, lead, event.id, uuid.uuid4())
    await reassign(client, lead, event.id, casey.id, "")

    assert notifier.reassignments == []


async def test_tc_us10e_18_a_failing_notifier_never_undoes_the_move(
    client: AsyncClient, db: Session, event: Event, lead: User, jordan: User, notifier: FakeNotifier,
    caplog: pytest.LogCaptureFixture,
) -> None:
    notifier.fail = True

    with caplog.at_level(logging.ERROR):
        response = await reassign(client, lead, event.id, jordan.id)

    assert response.status_code == 200
    db.refresh(event)
    assert event.coordinator_id == jordan.id
    assert len(notifier.reassignments) == 3  # each recipient still tried
    assert "reassignment notice" in caplog.text


async def test_tc_us10e_19_a_reassignment_row_without_a_reason_is_refused_by_the_database(
    db: Session, event: Event, lead: User, jordan: User
) -> None:
    db.add(
        CoordinatorAssignment(
            event_id=event.id, assigned_by_user_id=lead.id, coordinator_id=jordan.id, kind=AssignmentKind.REASSIGNMENT
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


async def test_tc_us10e_20_the_lead_s_assigned_tab_follows_the_latest_lead(
    client: AsyncClient, db: Session, organiser: User, lead: User, casey: User, jordan: User
) -> None:
    other_lead = make_user(db, UserRole.COORDINATOR_LEAD)
    fresh = make_request(db, organiser, EventStatus.SUBMITTED)
    await assign(client, lead, fresh.id, casey.id)
    [first] = records(db, fresh)
    first.created_at = NOW  # the test shares one transaction, so space the two rows out
    db.flush()

    await reassign(client, other_lead, fresh.id, jordan.id)
    [later] = [r for r in records(db, fresh) if r.kind == AssignmentKind.REASSIGNMENT]
    later.created_at = NOW + timedelta(hours=1)
    db.flush()

    async def assigned_ids(who: User) -> set[str]:
        response = await client.get("/api/v1/event-requests/assigned", headers=auth(who))
        return {row["id"] for row in response.json()["event_requests"]}

    assert str(fresh.id) not in await assigned_ids(lead)
    assert str(fresh.id) in await assigned_ids(other_lead)


# --- AC 6: a coordinator can ask the Lead for a transfer ---


def transfer_url(request_id: uuid.UUID) -> str:
    return f"/api/v1/event-requests/{request_id}/transfer-request"


async def test_tc_us10e_21_a_coordinator_can_ask_for_a_transfer_and_the_leads_are_told(
    client: AsyncClient, db: Session, event: Event, lead: User, casey: User, notifier: FakeNotifier
) -> None:
    other_lead = make_user(db, UserRole.COORDINATOR_LEAD)
    event.name = "Alumni night"
    db.flush()

    response = await client.post(transfer_url(event.id), headers=auth(casey), json={"reason": "  On leave  "})

    assert response.status_code == 202
    db.refresh(event)
    assert event.coordinator_id == casey.id  # nothing moved
    assert records(db, event) == []
    assert {n["email"] for n in notifier.transfer_requests} == {lead.email, other_lead.email}
    for notice in notifier.transfer_requests:
        assert notice["coordinator_name"] == "Casey Tan"
        assert notice["event_name"] == "Alumni night"
        assert notice["reason"] == "On leave"


@pytest.mark.parametrize("reason", [None, "", "  "])
async def test_tc_us10e_22_a_transfer_request_needs_a_reason(
    client: AsyncClient, event: Event, casey: User, notifier: FakeNotifier, reason: str | None
) -> None:
    body = {} if reason is None else {"reason": reason}

    response = await client.post(transfer_url(event.id), headers=auth(casey), json=body)

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": ["reason"]}
    assert notifier.transfer_requests == []


async def test_tc_us10e_23_only_the_events_own_coordinator_can_ask(
    client: AsyncClient, db: Session, event: Event, lead: User, organiser: User, jordan: User, notifier: FakeNotifier
) -> None:
    for caller, expected in ((jordan, 404), (lead, 403), (organiser, 403)):
        response = await client.post(transfer_url(event.id), headers=auth(caller), json={"reason": REASON})
        assert response.status_code == expected
    assert notifier.transfer_requests == []


async def test_tc_us10e_24_a_finished_event_cannot_be_transferred(
    client: AsyncClient, db: Session, event: Event, casey: User, notifier: FakeNotifier
) -> None:
    event.status = EventStatus.REJECTED
    db.flush()

    response = await client.post(transfer_url(event.id), headers=auth(casey), json={"reason": REASON})

    assert response.status_code == 409
    assert notifier.transfer_requests == []
