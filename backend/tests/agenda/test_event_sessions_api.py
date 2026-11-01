"""US15 agenda, PR 2 (SCRUM-139, story SCRUM-18): the Organiser lists, adds, edits and deletes their event's
sessions. See docs/testing/US15-event-agenda.md."""

import threading
import uuid
from collections.abc import Generator
from datetime import date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

import app.agenda.service as agenda_service_module
from app.agenda.models import EventSession, SessionType
from app.agenda.schemas import SessionWrite
from app.agenda.service import agenda_service
from app.core.exceptions import DomainError
from app.event.models import DeliveryMode, Event, EventStatus
from app.user.models import User, UserRole
from tests.event.test_event_request_clarification_api import auth
from tests.factories import NOW, SGT, make_user

pytestmark = pytest.mark.anyio

# A draft's window (D94, as D65): either preferred date, 09:00 to 12:00 Singapore time.
DAY_ONE = date(2026, 10, 8)
DAY_TWO = date(2026, 10, 10)
# A planning event's window: its own start_at to end_at.
PLANNED_DAY = date(2026, 10, 20)
PLANNED_STATUSES = (EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.PREPARATION)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), SGT)


def iso(day: date, hour: int, minute: int = 0) -> str:
    return at(day, hour, minute).isoformat()


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


def request_event(
    db: Session,
    organiser: User,
    status: EventStatus = EventStatus.DRAFT,
    coordinator: User | None = None,
    dates: list[date] | None = None,
) -> Event:
    """The organiser's own request in `status`: preferred dates and times always (none if `dates` is []),
    and its own 10:00 to 17:00 once planned."""
    dated = dates is None or bool(dates)
    event = Event(
        name="Community design workshop",
        status=status,
        registration_enabled=False,
        event_category="Workshop",
        purpose="Plan a community design session",
        preferred_dates=[DAY_ONE, DAY_TWO] if dates is None else (dates or None),
        preferred_start_time=time(9, 0) if dated else None,
        preferred_end_time=time(12, 0) if dated else None,
        expected_attendees=24,
        created_by_user_id=organiser.id,
        coordinator_id=coordinator.id if coordinator else None,
    )
    if status != EventStatus.DRAFT:
        event.submitted_by_user_id = organiser.id
        event.submitted_at = NOW - timedelta(days=1)
        event.request_reference = f"ER-2026-{uuid.uuid4().int % 900000 + 100000}"
    if status in PLANNED_STATUSES:
        event.start_at = at(PLANNED_DAY, 10)
        event.end_at = at(PLANNED_DAY, 17)
        event.capacity = 40
        event.delivery_mode = DeliveryMode.IN_PERSON
    db.add(event)
    db.flush()
    return event


def add_session(
    db: Session, event: Event, starts_at: datetime, ends_at: datetime, title: str = "Opening keynote"
) -> EventSession:
    session = EventSession(
        event_id=event.id,
        title=title,
        session_type=SessionType.PRESENTATION,
        speaker_name="Dr Tan",
        starts_at=starts_at,
        ends_at=ends_at,
    )
    db.add(session)
    db.flush()
    return session


def body(starts_at: str, ends_at: str, **overrides: object) -> dict[str, object]:
    fields = {
        "title": "Opening keynote",
        "session_type": "presentation",
        "speaker_name": "Dr Tan",
        "starts_at": starts_at,
        "ends_at": ends_at,
    }
    return fields | overrides


def sessions_url(event: Event | uuid.UUID) -> str:
    return f"/api/v1/event-requests/{event.id if isinstance(event, Event) else event}/sessions"


def session_url(session_id: object) -> str:
    return f"/api/v1/event-sessions/{session_id}"


def stored(db: Session, event: Event) -> list[EventSession]:
    db.expire_all()
    return list(db.scalars(select(EventSession).where(EventSession.event_id == event.id).order_by(EventSession.starts_at)))


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --- TC-US15-05 the owner adds each type of session and lists them in order (AC 1, 2, 5) ---


async def test_tc_us15_05_the_owner_adds_each_type_and_lists_them_in_order(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    draft = request_event(db, organiser)
    added = [
        body(iso(DAY_ONE, 11), iso(DAY_ONE, 12), title="Design sprint", session_type="workshop", speaker_name="Mei Lin"),
        body(iso(DAY_ONE, 10, 30), iso(DAY_ONE, 11), title="Coffee break", session_type="break", speaker_name=None),
        body(iso(DAY_ONE, 9), iso(DAY_ONE, 9, 45)),
        body(iso(DAY_ONE, 9, 45), iso(DAY_ONE, 10), title="Questions", session_type="other"),
        body(iso(DAY_ONE, 10), iso(DAY_ONE, 10, 30), title="Industry panel", session_type="panel", speaker_name="Three guests"),
    ]

    for sent in added:
        response = await client.post(sessions_url(draft), headers=auth(organiser), json=sent)
        assert response.status_code == 201, response.json()
        saved = response.json()
        assert uuid.UUID(saved["id"])
        assert saved["event_id"] == str(draft.id)
        assert (saved["title"], saved["session_type"], saved["speaker_name"]) == (
            sent["title"], sent["session_type"], sent["speaker_name"]
        )
        assert (instant(saved["starts_at"]), instant(saved["ends_at"])) == (
            instant(sent["starts_at"]), instant(sent["ends_at"])
        )
        assert saved["outside_window"] is False

    listed = await client.get(sessions_url(draft), headers=auth(organiser))
    assert listed.status_code == 200
    sessions = listed.json()["sessions"]
    assert [s["title"] for s in sessions] == ["Opening keynote", "Questions", "Industry panel", "Coffee break", "Design sprint"]
    assert [s["session_type"] for s in sessions] == ["presentation", "other", "panel", "break", "workshop"]
    assert sessions[3]["speaker_name"] is None
    assert len(stored(db, draft)) == 5


async def test_tc_us15_05_the_owner_adds_to_a_planning_event(client: AsyncClient, db: Session, organiser: User) -> None:
    planning = request_event(db, organiser, EventStatus.PLANNING)

    response = await client.post(sessions_url(planning), headers=auth(organiser), json=body(iso(PLANNED_DAY, 10), iso(PLANNED_DAY, 11)))

    assert response.status_code == 201
    assert [s.title for s in stored(db, planning)] == ["Opening keynote"]


async def test_tc_us15_05_text_is_trimmed_and_a_blank_speaker_is_none(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    draft = request_event(db, organiser)

    response = await client.post(
        sessions_url(draft),
        headers=auth(organiser),
        json=body(iso(DAY_ONE, 10), iso(DAY_ONE, 10, 15), title="  Coffee  ", session_type="break", speaker_name="  "),
    )

    assert response.status_code == 201
    assert (response.json()["title"], response.json()["speaker_name"]) == ("Coffee", None)


# --- TC-US15-06 the owner edits a session, then deletes it (AC 1) ---


async def test_tc_us15_06_the_owner_edits_then_deletes_a_session(client: AsyncClient, db: Session, organiser: User) -> None:
    draft = request_event(db, organiser)
    session = add_session(db, draft, at(DAY_ONE, 9), at(DAY_ONE, 10))

    edited = await client.patch(
        session_url(session.id),
        headers=auth(organiser),
        json={"title": "Welcome keynote", "speaker_name": "Prof Lee", "starts_at": iso(DAY_ONE, 9, 15), "ends_at": iso(DAY_ONE, 10, 15)},
    )
    assert edited.status_code == 200, edited.json()
    out = edited.json()
    assert (out["id"], out["title"], out["speaker_name"], out["session_type"]) == (
        str(session.id), "Welcome keynote", "Prof Lee", "presentation"
    )
    assert (instant(out["starts_at"]), instant(out["ends_at"])) == (at(DAY_ONE, 9, 15), at(DAY_ONE, 10, 15))

    # Only the fields sent change.
    renamed = await client.patch(session_url(session.id), headers=auth(organiser), json={"title": "Keynote"})
    assert renamed.status_code == 200
    assert (renamed.json()["title"], renamed.json()["speaker_name"], instant(renamed.json()["starts_at"])) == (
        "Keynote", "Prof Lee", at(DAY_ONE, 9, 15)
    )

    deleted = await client.delete(session_url(session.id), headers=auth(organiser))
    assert deleted.status_code == 204
    assert (await client.get(sessions_url(draft), headers=auth(organiser))).json() == {"sessions": []}
    again = await client.delete(session_url(session.id), headers=auth(organiser))
    assert (again.status_code, again.json()) == (404, {"code": "NOT_FOUND"})


async def test_tc_us15_06_an_edit_to_a_break_needs_no_speaker(client: AsyncClient, db: Session, organiser: User) -> None:
    draft = request_event(db, organiser)
    session = add_session(db, draft, at(DAY_ONE, 10), at(DAY_ONE, 10, 30))

    response = await client.patch(
        session_url(session.id), headers=auth(organiser), json={"title": "Lunch", "session_type": "break", "speaker_name": None}
    )

    assert response.status_code == 200
    assert (response.json()["session_type"], response.json()["speaker_name"]) == ("break", None)


# --- TC-US15-07 a session falls within the event's window (AC 3, D94) ---


async def test_tc_us15_07_a_planning_event_takes_sessions_within_its_own_times(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    planning = request_event(db, organiser, EventStatus.PLANNING)  # 10:00 to 17:00

    early = await client.post(sessions_url(planning), headers=auth(organiser), json=body(iso(PLANNED_DAY, 9, 30), iso(PLANNED_DAY, 10, 30)))
    late = await client.post(sessions_url(planning), headers=auth(organiser), json=body(iso(PLANNED_DAY, 16, 30), iso(PLANNED_DAY, 17, 30)))

    assert (early.status_code, early.json()["code"], early.json()["fields"]) == (422, "INVALID_SESSION", ["starts_at"])
    assert (late.status_code, late.json()["code"], late.json()["fields"]) == (422, "INVALID_SESSION", ["ends_at"])
    assert "10:00" in early.json()["errors"]["starts_at"]
    for starts, ends in ((10, 11), (16, 17)):  # the edges
        edge = await client.post(sessions_url(planning), headers=auth(organiser), json=body(iso(PLANNED_DAY, starts), iso(PLANNED_DAY, ends)))
        assert edge.status_code == 201, edge.json()
    assert len(stored(db, planning)) == 2


async def test_tc_us15_07_a_draft_takes_sessions_on_a_preferred_date_between_its_times(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    draft = request_event(db, organiser)  # 8 or 10 Oct, 09:00 to 12:00
    not_preferred = date(2026, 10, 9)

    refusals = {
        "starts_at": [
            body(iso(not_preferred, 9), iso(not_preferred, 10)),
            body(iso(DAY_ONE, 8, 30), iso(DAY_ONE, 9, 30)),
        ],
        "ends_at": [body(iso(DAY_TWO, 11, 30), iso(DAY_TWO, 12, 30))],
    }
    for field, sent_bodies in refusals.items():
        for sent in sent_bodies:
            response = await client.post(sessions_url(draft), headers=auth(organiser), json=sent)
            assert (response.status_code, response.json()["code"], response.json()["fields"]) == (
                422, "INVALID_SESSION", [field]
            ), sent
    for starts, ends in ((9, 10), (11, 12)):  # the edges, on the second preferred date
        edge = await client.post(sessions_url(draft), headers=auth(organiser), json=body(iso(DAY_TWO, starts), iso(DAY_TWO, ends)))
        assert edge.status_code == 201, edge.json()
    assert len(stored(db, draft)) == 2


async def test_tc_us15_07_a_draft_without_dates_and_times_takes_no_sessions_yet(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    draft = request_event(db, organiser, dates=[])

    response = await client.post(sessions_url(draft), headers=auth(organiser), json=body(iso(DAY_ONE, 9), iso(DAY_ONE, 10)))

    assert (response.status_code, response.json()["code"], response.json()["fields"]) == (422, "INVALID_SESSION", ["starts_at"])
    assert "preferred dates" in response.json()["errors"]["starts_at"]
    assert stored(db, draft) == []


async def test_tc_us15_07_an_edit_is_checked_against_the_window_too(client: AsyncClient, db: Session, organiser: User) -> None:
    draft = request_event(db, organiser)
    session = add_session(db, draft, at(DAY_ONE, 9), at(DAY_ONE, 10))

    response = await client.patch(session_url(session.id), headers=auth(organiser), json={"ends_at": iso(DAY_ONE, 12, 30)})

    assert (response.status_code, response.json()["fields"]) == (422, ["ends_at"])
    assert stored(db, draft)[0].ends_at == at(DAY_ONE, 10)


async def test_tc_us15_07_a_session_left_outside_moved_dates_is_marked(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    """Moving the event's times doesn't re-check its sessions (D94, as D65); the list marks those now outside."""
    planning = request_event(db, organiser, EventStatus.PLANNING)
    add_session(db, planning, at(PLANNED_DAY, 10), at(PLANNED_DAY, 11), title="Early")
    add_session(db, planning, at(PLANNED_DAY, 15), at(PLANNED_DAY, 16), title="Late")
    planning.start_at = at(PLANNED_DAY, 13)
    db.flush()

    sessions = (await client.get(sessions_url(planning), headers=auth(organiser))).json()["sessions"]

    assert [(s["title"], s["outside_window"]) for s in sessions] == [("Early", True), ("Late", False)]


# --- TC-US15-08 one track: no two sessions overlap (AC 4, D95) ---


async def test_tc_us15_08_an_overlapping_session_is_refused_naming_the_clash(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    draft = request_event(db, organiser)
    ten = add_session(db, draft, at(DAY_ONE, 10), at(DAY_ONE, 11))

    added = await client.post(sessions_url(draft), headers=auth(organiser), json=body(iso(DAY_ONE, 10, 30), iso(DAY_ONE, 11, 30), title="Workshop"))
    assert (added.status_code, added.json()["code"]) == (409, "SESSION_OVERLAP")
    assert (added.json()["session"]["id"], added.json()["session"]["title"]) == (str(ten.id), "Opening keynote")
    assert instant(added.json()["session"]["starts_at"]) == at(DAY_ONE, 10)
    assert instant(added.json()["session"]["ends_at"]) == at(DAY_ONE, 11)

    after = await client.post(sessions_url(draft), headers=auth(organiser), json=body(iso(DAY_ONE, 11), iso(DAY_ONE, 12), title="Next"))
    before = await client.post(sessions_url(draft), headers=auth(organiser), json=body(iso(DAY_ONE, 9), iso(DAY_ONE, 10), title="First"))
    assert (after.status_code, before.status_code) == (201, 201)  # back-to-back

    moved = await client.patch(session_url(after.json()["id"]), headers=auth(organiser), json={"starts_at": iso(DAY_ONE, 10, 30)})
    assert (moved.status_code, moved.json()["code"], moved.json()["session"]["id"]) == (409, "SESSION_OVERLAP", str(ten.id))

    # A session doesn't clash with itself.
    shortened = await client.patch(session_url(ten.id), headers=auth(organiser), json={"ends_at": iso(DAY_ONE, 10, 45)})
    assert shortened.status_code == 200
    assert [s.title for s in stored(db, draft)] == ["First", "Opening keynote", "Next"]


async def test_tc_us15_08_another_events_sessions_dont_clash(client: AsyncClient, db: Session, organiser: User) -> None:
    draft, other = request_event(db, organiser), request_event(db, organiser)
    add_session(db, other, at(DAY_ONE, 10), at(DAY_ONE, 11))

    response = await client.post(sessions_url(draft), headers=auth(organiser), json=body(iso(DAY_ONE, 10), iso(DAY_ONE, 11)))

    assert response.status_code == 201


# --- TC-US15-09 every invalid field is named at once (AC 2) ---


async def test_tc_us15_09_every_invalid_field_is_named_at_once(client: AsyncClient, db: Session, organiser: User) -> None:
    draft = request_event(db, organiser)

    response = await client.post(
        sessions_url(draft),
        headers=auth(organiser),
        json=body(iso(DAY_ONE, 11), iso(DAY_ONE, 10), title="  ", session_type="keynote", speaker_name=None),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_SESSION"
    assert response.json()["fields"] == ["title", "session_type", "speaker_name", "ends_at"]
    assert set(response.json()["errors"]) == {"title", "session_type", "speaker_name", "ends_at"}
    assert stored(db, draft) == []


async def test_tc_us15_09_missing_fields_and_times_without_an_offset(client: AsyncClient, db: Session, organiser: User) -> None:
    draft = request_event(db, organiser)

    empty = await client.post(sessions_url(draft), headers=auth(organiser), json={})
    naive = await client.post(
        sessions_url(draft), headers=auth(organiser), json=body("2026-10-08T09:00:00", "2026-10-08T10:00:00")
    )
    unknown_field = await client.post(sessions_url(draft), headers=auth(organiser), json=body(iso(DAY_ONE, 9), iso(DAY_ONE, 10), room="2-1"))

    assert (empty.status_code, empty.json()["code"]) == (422, "INVALID_SESSION")
    assert empty.json()["fields"] == ["title", "session_type", "speaker_name", "starts_at", "ends_at"]
    assert (naive.status_code, naive.json()["fields"]) == (422, ["starts_at", "ends_at"])
    assert unknown_field.status_code == 422
    assert stored(db, draft) == []


async def test_tc_us15_09_an_edit_cant_drop_a_presentations_speaker(client: AsyncClient, db: Session, organiser: User) -> None:
    draft = request_event(db, organiser)
    session = add_session(db, draft, at(DAY_ONE, 9), at(DAY_ONE, 10))

    response = await client.patch(session_url(session.id), headers=auth(organiser), json={"speaker_name": " "})

    assert (response.status_code, response.json()["code"], response.json()["fields"]) == (422, "INVALID_SESSION", ["speaker_name"])
    assert stored(db, draft)[0].speaker_name == "Dr Tan"


# --- TC-US15-10 only a draft or planning event's agenda changes (AC 1, D93) ---


@pytest.mark.parametrize(
    "status",
    [
        EventStatus.SUBMITTED,
        EventStatus.AWAITING_CLARIFICATION,
        EventStatus.APPROVED,
        EventStatus.CONFIRMED,
        EventStatus.PREPARATION,
    ],
)
async def test_tc_us15_10_the_agenda_is_read_only_past_draft_and_planning(
    client: AsyncClient, db: Session, organiser: User, status: EventStatus
) -> None:
    event = request_event(db, organiser, status)
    day = PLANNED_DAY if status in PLANNED_STATUSES else DAY_ONE
    session = add_session(db, event, at(day, 10), at(day, 11))
    refused = {"code": "AGENDA_NOT_EDITABLE", "status": status.value}

    for response in (
        await client.post(sessions_url(event), headers=auth(organiser), json=body(iso(day, 11), iso(day, 12))),
        await client.patch(session_url(session.id), headers=auth(organiser), json={"title": "Renamed"}),
        await client.delete(session_url(session.id), headers=auth(organiser)),
    ):
        assert (response.status_code, response.json()) == (409, refused)

    assert [(s.id, s.title) for s in stored(db, event)] == [(session.id, "Opening keynote")]
    listed = await client.get(sessions_url(event), headers=auth(organiser))
    assert [s["id"] for s in listed.json()["sessions"]] == [str(session.id)]


# --- TC-US15-11 who may list and change an agenda ---


async def test_tc_us15_11_another_organiser_gets_404(client: AsyncClient, db: Session, organiser: User) -> None:
    draft = request_event(db, organiser)
    session = add_session(db, draft, at(DAY_ONE, 9), at(DAY_ONE, 10))
    stranger = make_user(db, UserRole.ORGANISER)

    for response in (
        await client.get(sessions_url(draft), headers=auth(stranger)),
        await client.post(sessions_url(draft), headers=auth(stranger), json=body(iso(DAY_ONE, 10), iso(DAY_ONE, 11))),
        await client.patch(session_url(session.id), headers=auth(stranger), json={"title": "Mine"}),
        await client.delete(session_url(session.id), headers=auth(stranger)),
    ):
        assert (response.status_code, response.json()) == (404, {"code": "NOT_FOUND"})
    assert [s.title for s in stored(db, draft)] == ["Opening keynote"]


async def test_tc_us15_11_a_lead_and_the_assigned_coordinator_read_but_dont_change(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR)
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    submitted = request_event(db, organiser, EventStatus.SUBMITTED, coordinator=coordinator)
    session = add_session(db, submitted, at(DAY_ONE, 9), at(DAY_ONE, 10))

    for reader in (lead, coordinator):
        listed = await client.get(sessions_url(submitted), headers=auth(reader))
        assert [s["id"] for s in listed.json()["sessions"]] == [str(session.id)]
        for response in (
            await client.post(sessions_url(submitted), headers=auth(reader), json=body(iso(DAY_ONE, 10), iso(DAY_ONE, 11))),
            await client.patch(session_url(session.id), headers=auth(reader), json={"title": "Theirs"}),
            await client.delete(session_url(session.id), headers=auth(reader)),
        ):
            assert (response.status_code, response.json()) == (403, {"code": "FORBIDDEN"})

    # Nobody else reads a draft (D11), nor a coordinator a request that isn't theirs.
    draft = request_event(db, organiser)
    other_coordinator = make_user(db, UserRole.COORDINATOR)
    assert (await client.get(sessions_url(draft), headers=auth(lead))).status_code == 404
    assert (await client.get(sessions_url(submitted), headers=auth(other_coordinator))).status_code == 404


async def test_tc_us15_11_other_roles_no_identity_and_unknown_ids(client: AsyncClient, db: Session, organiser: User) -> None:
    draft = request_event(db, organiser)
    session = add_session(db, draft, at(DAY_ONE, 9), at(DAY_ONE, 10))
    tech = make_user(db, UserRole.TECH_SUPPORT)

    calls = [
        ("GET", sessions_url(draft), None),
        ("POST", sessions_url(draft), body(iso(DAY_ONE, 10), iso(DAY_ONE, 11))),
        ("PATCH", session_url(session.id), {"title": "Renamed"}),
        ("DELETE", session_url(session.id), None),
    ]
    for method, url, sent in calls:
        anonymous = await client.request(method, url, json=sent)
        assert (anonymous.status_code, anonymous.json()["code"]) == (401, "UNAUTHENTICATED")
        other_role = await client.request(method, url, headers=auth(tech), json=sent)
        assert (other_role.status_code, other_role.json()) == (403, {"code": "FORBIDDEN"})

    for method, url, sent in [
        ("GET", sessions_url(uuid.uuid4()), None),
        ("POST", sessions_url(uuid.uuid4()), body(iso(DAY_ONE, 10), iso(DAY_ONE, 11))),
        ("PATCH", session_url(uuid.uuid4()), {"title": "Renamed"}),
        ("DELETE", session_url(uuid.uuid4()), None),
    ]:
        unknown = await client.request(method, url, headers=auth(organiser), json=sent)
        assert (unknown.status_code, unknown.json()) == (404, {"code": "NOT_FOUND"})


# --- TC-US15-12 two overlapping sessions saved at the same moment (AC 4) ---


class Committed:
    """Rows committed for real, so two sessions on separate connections both see them (as TC-US27-11)."""

    def __init__(self, organiser: uuid.UUID, event: uuid.UUID) -> None:
        self.organiser, self.event = organiser, event

    def add(self, engine: Engine, starts_at: datetime) -> object:
        """One session added in its own database session: 201, or the refusal's (status, code)."""
        sent = SessionWrite(
            title="Keynote", session_type="presentation", speaker_name="Dr Tan",
            starts_at=starts_at, ends_at=starts_at + timedelta(hours=1),
        )
        with Session(engine) as session:
            try:
                agenda_service.add(session, session.get(User, self.organiser), self.event, sent)
                return 201
            except DomainError as error:
                return (error.status_code, error.code)


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    with Session(engine) as setup:
        organiser = make_user(setup, UserRole.ORGANISER)
        draft = request_event(setup, organiser)
        setup.commit()
        rows = Committed(organiser.id, draft.id)
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(EventSession).where(EventSession.event_id == rows.event))
            cleanup.execute(delete(Event).where(Event.id == rows.event))
            cleanup.execute(delete(User).where(User.id == rows.organiser))
            cleanup.commit()


def test_tc_us15_12_two_overlapping_sessions_at_once_only_one_saves(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real race: both wait at a barrier just before locking the event, then both go. The lock makes the
    second wait for the first's commit and see its session, so it's refused as an overlap, by name."""
    barrier = threading.Barrier(2, timeout=10)
    original = agenda_service_module._lock_event

    def wait_then_lock(*args: object, **kwargs: object) -> object:
        barrier.wait()
        return original(*args, **kwargs)

    monkeypatch.setattr(agenda_service_module, "_lock_event", wait_then_lock)
    outcomes: list[object] = []
    threads = [
        threading.Thread(target=lambda starts=starts: outcomes.append(committed.add(engine, starts)))
        for starts in (at(DAY_ONE, 10), at(DAY_ONE, 10, 30))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes, key=str) == sorted([201, (409, "SESSION_OVERLAP")], key=str)
    with Session(engine) as check:
        assert check.scalar(select(func.count()).where(EventSession.event_id == committed.event)) == 1
