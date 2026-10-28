"""US18 (SCRUM-85): the assigned coordinator confirms an event once its arrangements are ready."""

import logging
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentLineStatus
from app.event.models import DeliveryMode, Event, EventStatus
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.equipment.test_equipment_api import make_line
from tests.equipment.test_equipment_schema import make_type
from tests.event.test_event_request_clarification_api import make_request, make_user
from tests.event.test_event_requests import auth
from tests.factories import NOW, make_attendee, make_event, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

STARTS = NOW + timedelta(days=7)


def url(event_id: uuid.UUID, action: str) -> str:
    return f"/api/v1/event-requests/{event_id}/{action}"


@pytest.fixture
def organiser(db: Session) -> User:
    user = make_user(db, UserRole.ORGANISER)
    user.email = "olivia.organiser@smu.edu.sg"
    db.flush()
    return user


@pytest.fixture
def casey(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def venue_staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def safety_officer(db: Session) -> User:
    return make_user(db, UserRole.SAFETY_OFFICER)


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db, name="SCIS Seminar Room 2-1")


@pytest.fixture
def event(db: Session, organiser: User, casey: User) -> Event:
    """An approved request Casey owns, with nothing arranged yet."""
    request = make_request(db, organiser, EventStatus.APPROVED, coordinator=casey)
    request.request_reference = "ER-2026-000042"
    request.expected_attendees = 35
    db.flush()
    return request


def book(db: Session, event: Event, venue: Venue, coordinator: User, venue_staff: User, status=VenueBookingStatus.APPROVED, **overrides):
    extra = {"decided_by_user_id": venue_staff.id} if status in (VenueBookingStatus.APPROVED, VenueBookingStatus.REJECTED) else {}
    return make_venue_booking(db, event=event, venue=venue, user=coordinator, status=status, **(extra | overrides))


def approve_safety(db: Session, event: Event, officer: User) -> None:
    event.safety_approved_at = NOW - timedelta(hours=1)
    event.safety_approved_by_user_id = officer.id
    db.flush()


@pytest.fixture
def ready(db: Session, event: Event, casey: User, venue: Venue, venue_staff: User, safety_officer: User) -> Event:
    """Every arrangement complete: an approved venue booking and the Safety Officer's approval."""
    book(db, event, venue, casey, venue_staff, starts_at=STARTS)
    approve_safety(db, event, safety_officer)
    return event


async def readiness(client: AsyncClient, user: User | None, event: Event):
    return await client.get(url(event.id, "readiness"), headers=auth(user) if user else {})


async def confirm(client: AsyncClient, user: User | None, event: Event):
    return await client.post(url(event.id, "confirmation"), headers=auth(user) if user else {})


def outstanding(body: dict) -> list[str]:
    return [item["kind"] for item in body["outstanding"]]


# --- AC 1, 3: confirming ---


async def test_tc_us18_01_a_ready_event_is_confirmed(client: AsyncClient, db: Session, ready: Event, casey: User) -> None:
    response = await confirm(client, casey, ready)

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["confirmed_at"] is not None
    db.refresh(ready)
    assert ready.status == EventStatus.CONFIRMED
    assert ready.confirmed_by_user_id == casey.id


async def test_tc_us18_02_confirming_gives_the_event_its_date_capacity_and_venue(
    client: AsyncClient, db: Session, ready: Event, casey: User, venue: Venue, venue_staff: User
) -> None:
    second = make_venue(db, name="Auditorium")
    book(db, ready, second, casey, venue_staff, starts_at=STARTS + timedelta(days=1), ends_at=STARTS + timedelta(days=1, hours=3))

    await confirm(client, casey, ready)

    db.refresh(ready)
    assert ready.start_at == STARTS
    assert ready.end_at == STARTS + timedelta(days=1, hours=3)
    assert ready.capacity == 35  # the request's expected attendance
    assert ready.delivery_mode == DeliveryMode.IN_PERSON
    assert ready.venue_name == "SCIS Seminar Room 2-1, Auditorium"


async def test_tc_us18_03_a_date_the_event_already_holds_is_kept(
    client: AsyncClient, db: Session, ready: Event, casey: User
) -> None:
    ready.start_at, ready.end_at, ready.capacity = NOW + timedelta(days=30), NOW + timedelta(days=30, hours=1), 12
    db.flush()

    await confirm(client, casey, ready)

    db.refresh(ready)
    assert (ready.start_at, ready.capacity) == (NOW + timedelta(days=30), 12)


async def test_tc_us18_04_a_planning_event_is_confirmed_too(client: AsyncClient, db: Session, ready: Event, casey: User) -> None:
    ready.status = EventStatus.PLANNING
    ready.start_at, ready.end_at, ready.capacity, ready.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    assert (await confirm(client, casey, ready)).status_code == 200


# --- AC 1, 2, 5: blocked, with the readiness list ---


async def test_tc_us18_05_a_pending_venue_booking_blocks_and_is_named(
    client: AsyncClient, db: Session, ready: Event, casey: User, venue: Venue, venue_staff: User
) -> None:
    other = make_venue(db, name="Auditorium")
    book(db, ready, other, casey, venue_staff, status=VenueBookingStatus.REQUESTED, starts_at=STARTS + timedelta(days=2))

    response = await confirm(client, casey, ready)

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "EVENT_NOT_READY"
    assert [(item["name"], item["kind"]) for item in body["outstanding"]] == [("Auditorium", "venue")]
    db.refresh(ready)
    assert ready.status == EventStatus.APPROVED and ready.confirmed_at is None


async def test_tc_us18_06_no_venue_blocks(client: AsyncClient, db: Session, event: Event, casey: User, safety_officer: User) -> None:
    approve_safety(db, event, safety_officer)

    body = (await confirm(client, casey, event)).json()

    assert body["code"] == "EVENT_NOT_READY"
    assert [item["detail"] for item in body["outstanding"]] == ["No venue has been requested yet."]


async def test_tc_us18_07_rejected_and_withdrawn_bookings_are_not_required(
    client: AsyncClient, db: Session, ready: Event, casey: User, venue: Venue, venue_staff: User
) -> None:
    book(db, ready, make_venue(db), casey, venue_staff, status=VenueBookingStatus.REJECTED, starts_at=STARTS + timedelta(days=3))
    book(db, ready, make_venue(db), casey, venue_staff, status=VenueBookingStatus.WITHDRAWN, starts_at=STARTS + timedelta(days=4))

    assert (await confirm(client, casey, ready)).status_code == 200


async def test_tc_us18_08_a_pending_equipment_line_blocks_and_an_approved_one_does_not(
    client: AsyncClient, db: Session, ready: Event, casey: User
) -> None:
    make_line(db, event=ready, equipment_type=make_type(db), requested_by=casey, status=EquipmentLineStatus.APPROVED)
    pending = make_line(db, event=ready, equipment_type=make_type(db), requested_by=casey)

    blocked = await confirm(client, casey, ready)

    assert blocked.status_code == 409
    assert outstanding(blocked.json()) == ["equipment"]
    assert "1 of 2 equipment lines" in blocked.json()["outstanding"][0]["detail"]

    reviewer = make_user(db, UserRole.TECH_SUPPORT)
    pending.status = EquipmentLineStatus.REJECTED
    pending.reviewed_by_user_id = reviewer.id
    pending.reviewed_at = NOW
    db.flush()
    assert (await confirm(client, casey, ready)).status_code == 200


async def test_tc_us18_09_equipment_nobody_asked_for_does_not_block(client: AsyncClient, ready: Event, casey: User) -> None:
    body = (await readiness(client, casey, ready)).json()

    assert body["ready"] is True
    assert [item["detail"] for item in body["items"] if item["kind"] == "equipment"] == ["No equipment was requested."]


async def test_tc_us18_10_no_safety_approval_blocks(
    client: AsyncClient, db: Session, ready: Event, casey: User
) -> None:
    ready.safety_approved_at = None
    ready.safety_approved_by_user_id = None
    db.flush()

    response = await confirm(client, casey, ready)

    assert response.status_code == 409
    assert [item["kind"] for item in response.json()["outstanding"]] == ["safety"]


async def test_tc_us18_11_every_outstanding_arrangement_is_listed_at_once(
    client: AsyncClient, db: Session, event: Event, casey: User, venue: Venue, venue_staff: User
) -> None:
    book(db, event, venue, casey, venue_staff, status=VenueBookingStatus.REQUESTED, starts_at=STARTS)
    make_line(db, event=event, equipment_type=make_type(db), requested_by=casey)

    body = (await confirm(client, casey, event)).json()

    assert [item["kind"] for item in body["outstanding"]] == ["venue", "equipment", "safety"]
    assert len(body["items"]) == 3  # complete ones come too, so the screen needn't ask again


async def test_tc_us18_12_the_readiness_list_shows_complete_and_outstanding_per_venue(
    client: AsyncClient, db: Session, ready: Event, casey: User, venue_staff: User
) -> None:
    book(db, ready, make_venue(db, name="Auditorium"), casey, venue_staff, status=VenueBookingStatus.REQUESTED, starts_at=STARTS + timedelta(days=2))

    response = await readiness(client, casey, ready)

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert [(item["kind"], item["name"], item["complete"]) for item in body["items"]] == [
        ("venue", "SCIS Seminar Room 2-1", True),
        ("venue", "Auditorium", False),
        ("equipment", "Equipment", True),
        ("safety", "Safety check", True),
    ]


# --- AC 5: statuses, and no override ---


@pytest.mark.parametrize(
    "status",
    [
        EventStatus.CANCELLED,
        EventStatus.REJECTED,
        EventStatus.CONFIRMED,
        EventStatus.PREPARATION,
        EventStatus.COMPLETED,
        EventStatus.UNDER_REVIEW,
        EventStatus.AWAITING_CLARIFICATION,
        EventStatus.SUBMITTED,
    ],
)
async def test_tc_us18_13_an_event_that_cannot_be_confirmed_is_refused(
    client: AsyncClient, db: Session, ready: Event, casey: User, status: EventStatus
) -> None:
    ready.status = status
    ready.start_at, ready.end_at, ready.capacity, ready.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    response = await confirm(client, casey, ready)

    assert response.status_code == 409
    assert response.json() == {"code": "CONFIRMATION_NOT_ALLOWED", "status": status.value}
    db.refresh(ready)
    assert ready.status == status and ready.confirmed_at is None


async def test_tc_us18_14_nothing_overrides_an_incomplete_arrangement(
    client: AsyncClient, db: Session, event: Event, casey: User
) -> None:
    response = await client.post(url(event.id, "confirmation"), headers=auth(casey), json={"override": True, "force": True})

    assert response.status_code == 409
    db.refresh(event)
    assert event.status == EventStatus.APPROVED


async def test_tc_us18_15_confirming_twice_is_refused_the_second_time(client: AsyncClient, ready: Event, casey: User) -> None:
    assert (await confirm(client, casey, ready)).status_code == 200

    second = await confirm(client, casey, ready)

    assert (second.status_code, second.json()["code"]) == (409, "CONFIRMATION_NOT_ALLOWED")


async def test_tc_us18_16_the_readiness_list_is_not_offered_before_approval(
    client: AsyncClient, db: Session, ready: Event, casey: User
) -> None:
    ready.status = EventStatus.UNDER_REVIEW
    db.flush()

    assert (await readiness(client, casey, ready)).status_code == 409


# --- AC 4: the notice ---


async def test_tc_us18_17_the_organiser_hears_the_date_time_and_venues(
    client: AsyncClient, ready: Event, casey: User, notifier: FakeNotifier
) -> None:
    await confirm(client, casey, ready)

    assert notifier.confirmations == [
        {
            "email": "olivia.organiser@smu.edu.sg",
            "request_reference": "ER-2026-000042",
            "event_name": "Community design workshop",
            "starts_at": STARTS,
            "ends_at": STARTS + timedelta(hours=2),
            "venues": ["SCIS Seminar Room 2-1"],
        }
    ]


async def test_tc_us18_18_a_refused_confirmation_tells_no_one(
    client: AsyncClient, event: Event, casey: User, notifier: FakeNotifier
) -> None:
    await confirm(client, casey, event)

    assert notifier.confirmations == []


async def test_tc_us18_19_a_failing_notifier_does_not_undo_the_confirmation(
    client: AsyncClient, db: Session, ready: Event, casey: User, notifier: FakeNotifier, caplog: pytest.LogCaptureFixture
) -> None:
    notifier.fail = True

    with caplog.at_level(logging.ERROR):
        response = await confirm(client, casey, ready)

    assert response.status_code == 200
    db.refresh(ready)
    assert ready.status == EventStatus.CONFIRMED
    assert "could not send the confirmation notice" in caplog.text


# --- access (D48, widened D11) ---


async def test_tc_us18_20_only_the_assigned_coordinator_confirms(
    client: AsyncClient, db: Session, ready: Event, casey: User, organiser: User
) -> None:
    other = make_user(db, UserRole.COORDINATOR)
    lead = make_user(db, UserRole.COORDINATOR_LEAD)

    assert (await confirm(client, other, ready)).status_code == 404  # someone else's event
    assert (await readiness(client, other, ready)).status_code == 404
    assert (await confirm(client, lead, ready)).status_code == 403
    assert (await confirm(client, organiser, ready)).status_code == 403
    assert (await confirm(client, None, ready)).status_code == 401
    db.refresh(ready)
    assert ready.status == EventStatus.APPROVED


async def test_tc_us18_21_an_unassigned_event_and_a_draft_are_404(
    client: AsyncClient, db: Session, organiser: User, casey: User
) -> None:
    unassigned = make_request(db, organiser, EventStatus.APPROVED)
    draft = make_request(db, organiser, EventStatus.DRAFT, coordinator=casey)

    assert (await confirm(client, casey, unassigned)).status_code == 404
    assert (await confirm(client, casey, draft)).status_code == 404
    assert (await client.post(url(uuid.uuid4(), "confirmation"), headers=auth(casey))).status_code == 404


async def test_tc_us18_22_the_assigned_coordinator_opens_their_event_in_planning_and_later(
    client: AsyncClient, db: Session, ready: Event, casey: User
) -> None:
    other = make_user(db, UserRole.COORDINATOR)
    ready.start_at, ready.end_at, ready.capacity, ready.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    for status in (EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.PREPARATION):
        ready.status = status
        db.flush()

        opened = await client.get(f"/api/v1/event-requests/{ready.id}", headers=auth(casey))
        thread = await client.get(f"/api/v1/event-requests/{ready.id}/clarifications", headers=auth(casey))
        queue = await client.get("/api/v1/event-requests", headers=auth(casey))

        assert (opened.status_code, thread.status_code) == (200, 200), status
        assert str(ready.id) in [row["id"] for row in queue.json()["event_requests"]], status
        # Nobody else reaches it through these routes.
        assert (await client.get(f"/api/v1/event-requests/{ready.id}", headers=auth(other))).status_code == 404
        assert str(ready.id) not in [row["id"] for row in (await client.get("/api/v1/event-requests", headers=auth(other))).json()["event_requests"]]


async def test_tc_us18_23_the_lead_still_reads_only_request_stage_events_here(
    client: AsyncClient, db: Session, ready: Event
) -> None:
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    ready.status = EventStatus.PLANNING
    ready.start_at, ready.end_at, ready.capacity, ready.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    assert (await client.get(f"/api/v1/event-requests/{ready.id}", headers=auth(lead))).status_code == 404


# --- AC 6: Preparation ---


async def test_tc_us18_24_a_confirmed_event_moves_to_preparation(
    client: AsyncClient, db: Session, ready: Event, casey: User
) -> None:
    await confirm(client, casey, ready)

    response = await client.post(url(ready.id, "preparation"), headers=auth(casey))

    assert response.status_code == 200
    assert response.json()["status"] == "preparation"
    db.refresh(ready)
    assert ready.status == EventStatus.PREPARATION


@pytest.mark.parametrize("status", [EventStatus.APPROVED, EventStatus.PLANNING, EventStatus.PREPARATION, EventStatus.CANCELLED])
async def test_tc_us18_25_only_a_confirmed_event_can_start_preparation(
    client: AsyncClient, db: Session, ready: Event, casey: User, status: EventStatus
) -> None:
    ready.status = status
    ready.start_at, ready.end_at, ready.capacity, ready.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    response = await client.post(url(ready.id, "preparation"), headers=auth(casey))

    assert response.status_code == 409
    assert response.json() == {"code": "PREPARATION_NOT_ALLOWED", "status": status.value}


async def test_tc_us18_26_only_the_assigned_coordinator_starts_preparation(
    client: AsyncClient, db: Session, ready: Event, casey: User
) -> None:
    await confirm(client, casey, ready)
    other = make_user(db, UserRole.COORDINATOR)

    assert (await client.post(url(ready.id, "preparation"), headers=auth(other))).status_code == 404
    assert (await client.post(url(ready.id, "preparation"))).status_code == 401


async def test_tc_us18_27_registration_stays_open_through_preparation(client: AsyncClient, db: Session) -> None:
    event = make_event(db, status=EventStatus.PREPARATION)
    attendee = make_attendee(db)

    board = await client.get("/api/v1/events/available", headers={"X-Attendee-Id": str(attendee.id)})

    assert str(event.id) in [row["id"] for row in board.json()["events"]]


# --- schema ---


async def test_tc_us18_28_safety_approval_columns_are_set_together(db: Session, event: Event, safety_officer: User) -> None:
    event.safety_approved_at = NOW
    with pytest.raises(IntegrityError) as raised:
        db.flush()

    assert raised.value.orig.diag.constraint_name == "events_safety_approval_consistent"


# --- the seeded demo ---


async def test_tc_us18_29_the_seeded_demo_confirms_and_a_reseed_resets_it(client: AsyncClient, db: Session) -> None:
    from app.seed import CONFIRMATION_EVENT, EVENT_COORDINATOR_EMAIL, seed, seed_id
    from sqlalchemy import select

    seed(db, now=NOW)
    coordinator = db.scalars(select(User).where(User.email == EVENT_COORDINATOR_EMAIL)).one()
    demo = db.get(Event, seed_id("event", CONFIRMATION_EVENT.slug))

    assert (await readiness(client, coordinator, demo)).json()["ready"] is True
    assert (await confirm(client, coordinator, demo)).status_code == 200

    seed(db, now=NOW)
    db.refresh(demo)
    assert (demo.status, demo.start_at, demo.confirmed_at) == (EventStatus.APPROVED, None, None)
    assert (await confirm(client, coordinator, demo)).status_code == 200
