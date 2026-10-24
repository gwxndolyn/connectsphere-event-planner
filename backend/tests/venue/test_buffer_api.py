"""US13 setup and turnaround buffers, PR 2 (SCRUM-115, story SCRUM-16): the occupied window through
the API. Opening hours (AC 5), the overlap period and reference (AC 4), the reusable rule US4 calls,
buffer edits while Requested bookings exist (D31) and US2 search with each venue's own buffers.
The table and its guard are PR 1's (test_buffer_schema.py); see docs/testing/US13-buffers.md."""

import re
import threading
import uuid
from collections.abc import Generator
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, delete, func, inspect, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue import booking_service as booking_service_module
from app.venue.availability import evaluate_booking, evaluate_window
from app.venue.booking_service import booking_service
from app.venue.models import Venue, VenueBooking, VenueBookingStatus
from app.venue.schemas import VenueBookingWrite
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_block, make_venue_booking

pytestmark = pytest.mark.anyio

SINGAPORE = ZoneInfo("Asia/Singapore")
DAY = (NOW + timedelta(days=7)).date()
CREATE_URL = "/api/v1/venue-bookings"


def at(hour: int, minute: int = 0, second: int = 0, *, day_offset: int = 0) -> datetime:
    return datetime.combine(DAY + timedelta(days=day_offset), time(hour, minute, second), SINGAPORE)


def when(value: str) -> datetime:
    return datetime.fromisoformat(value)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def body(event: Event, venue: Venue, starts_at: datetime, ends_at: datetime, **overrides: object) -> dict[str, object]:
    return {
        "event_id": str(event.id),
        "venue_id": str(venue.id),
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "expected_attendees": 30,
        "room_layout": "theatre",
        **overrides,
    }


def booking_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(VenueBooking))


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def staff(db: Session) -> User:
    # DECISION-PENDING: D19 — operations_manager stands in for Venue Staff until US16b.
    return make_user(db, UserRole.OPERATIONS_MANAGER)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    # DECISION-PENDING: D24 — approved directly; assigned so the coordinator may book it (D20).
    return make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)


@pytest.fixture
def venue(db: Session) -> Venue:
    # AC 2's example buffers (30 min setup, 45 min turnaround), open 08:00-20:00.
    return make_venue(
        db, name="Buffered Hall", setup_minutes=30, turnaround_minutes=45, opens_at=time(8, 0), closes_at=time(20, 0)
    )


# --- TC-US13-06 create stores the occupied window and a reference ---


async def test_tc_us13_06_create_stores_the_occupied_window_and_returns_the_reference(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, at(10), at(12)))

    assert response.status_code == 201
    created = response.json()
    assert (when(created["occupied_starts_at"]), when(created["occupied_ends_at"])) == (at(9, 30), at(12, 45))
    assert re.fullmatch(r"VB-\d{4}-\d{6}", created["reference"])
    stored = db.get(VenueBooking, uuid.UUID(created["id"]))
    assert (stored.occupied_starts_at, stored.occupied_ends_at) == (at(9, 30), at(12, 45))


async def test_tc_us13_06_lists_carry_the_reference_and_occupied_window(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))
    db.refresh(booking)

    pending = (await client.get("/api/v1/venue-bookings/pending", headers=auth(staff))).json()["bookings"]

    [row] = [row for row in pending if row["id"] == str(booking.id)]
    assert row["reference"] == booking.reference
    assert (when(row["occupied_starts_at"]), when(row["occupied_ends_at"])) == (at(9, 30), at(12, 45))


# --- TC-US13-07 overlap with another booking's occupied window ---


@pytest.mark.parametrize("existing", [VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED])
async def test_tc_us13_07_setup_overlapping_a_turnaround_by_one_second_is_refused_with_the_overlap(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue, existing: VenueBookingStatus
) -> None:
    """The earlier booking occupies 09:30-12:45. A request for 13:14:59 has its setup start at
    12:44:59: one second of overlap (AC 3), reported exactly (AC 4)."""
    other = make_venue_booking(
        db, event=event, venue=venue, user=make_user(db, UserRole.COORDINATOR), status=existing, starts_at=at(10), ends_at=at(12)
    )
    db.refresh(other)

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, at(13, 14, 59), at(14)))

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == "VENUE_UNAVAILABLE"
    conflict = payload["conflict"]
    assert conflict["kind"] == "booking"
    assert (when(conflict["starts_at"]), when(conflict["ends_at"])) == (at(10), at(12))
    assert (when(conflict["occupied"]["starts_at"]), when(conflict["occupied"]["ends_at"])) == (at(9, 30), at(12, 45))
    assert (when(conflict["overlap"]["starts_at"]), when(conflict["overlap"]["ends_at"])) == (at(12, 44, 59), at(12, 45))
    assert (when(payload["occupied"]["starts_at"]), when(payload["occupied"]["ends_at"])) == (at(12, 44, 59), at(14, 45))
    # D35: a coordinator isn't shown the other booking's reference; Venue Staff see it (TC-US13-11).
    assert other.reference not in response.text
    assert "reference" not in conflict
    assert booking_count(db) == 1


async def test_tc_us13_07_setup_starting_as_the_turnaround_ends_is_accepted(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, at(13, 15), at(14)))

    assert response.status_code == 201
    assert when(response.json()["occupied_starts_at"]) == at(12, 45)


async def test_tc_us13_07_a_refused_request_notifies_nobody(
    client: AsyncClient, db: Session, notifier: FakeNotifier, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, at(12, 30), at(13, 30)))

    assert response.status_code == 409
    assert notifier.venue_bookings == []


# --- TC-US13-08 overlap with a venue block ---


@pytest.mark.parametrize(
    ("block_starts", "block_ends", "overlap"),
    [
        (at(8), at(9, 45), (at(9, 30), at(9, 45))),  # the setup runs into a closure
        (at(12, 30), at(13), (at(12, 30), at(12, 45))),  # the turnaround runs into one
    ],
    ids=["setup", "turnaround"],
)
async def test_tc_us13_08_setup_or_turnaround_inside_a_block_is_refused(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    venue: Venue,
    block_starts: datetime,
    block_ends: datetime,
    overlap: tuple[datetime, datetime],
) -> None:
    make_venue_block(db, venue, block_starts, block_ends, note="AV maintenance")

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, at(10), at(12)))

    assert response.status_code == 409
    conflict = response.json()["conflict"]
    assert conflict["kind"] == "block"
    assert (when(conflict["starts_at"]), when(conflict["ends_at"])) == (block_starts, block_ends)
    assert (when(conflict["overlap"]["starts_at"]), when(conflict["overlap"]["ends_at"])) == overlap
    assert "unavailable" in response.json()["message"]
    assert booking_count(db) == 0


async def test_tc_us13_08_a_block_touching_the_occupied_window_is_fine(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    make_venue_block(db, venue, at(8), at(9, 30))
    make_venue_block(db, venue, at(12, 45), at(14))

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, at(10), at(12)))

    assert response.status_code == 201


# --- TC-US13-09 opening hours (AC 5) ---


@pytest.mark.parametrize(
    ("starts_at", "ends_at", "fields"),
    [
        (at(8, 15), at(10), ["starts_at"]),  # setup from 07:45, before 08:00
        (at(18), at(19, 30), ["ends_at"]),  # turnaround to 20:15, after 20:00
        (at(7, 50), at(19, 30), ["starts_at", "ends_at"]),  # both
        (at(19), at(1, day_offset=1), ["ends_at"]),  # crosses midnight
    ],
    ids=["setup before opening", "turnaround after closing", "both", "crosses midnight"],
)
async def test_tc_us13_09_an_occupied_window_outside_opening_hours_is_refused(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    venue: Venue,
    starts_at: datetime,
    ends_at: datetime,
    fields: list[str],
) -> None:
    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, starts_at, ends_at))

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "VENUE_OUTSIDE_HOURS"
    assert payload["fields"] == fields
    assert (payload["opens_at"], payload["closes_at"]) == ("08:00:00", "20:00:00")
    assert when(payload["occupied"]["starts_at"]) == starts_at - timedelta(minutes=30)
    assert when(payload["occupied"]["ends_at"]) == ends_at + timedelta(minutes=45)
    assert "08:00" in payload["message"] and "20:00" in payload["message"]
    assert booking_count(db) == 0


async def test_tc_us13_09_exactly_opening_to_closing_is_accepted(
    client: AsyncClient, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, at(8, 30), at(19, 15)))

    assert response.status_code == 201
    created = response.json()
    assert (when(created["occupied_starts_at"]), when(created["occupied_ends_at"])) == (at(8), at(20))


async def test_tc_us13_09_hours_are_checked_before_overlaps(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(8, 30), ends_at=at(10))

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body(event, venue, at(8, 15), at(9)))

    assert response.json()["code"] == "VENUE_OUTSIDE_HOURS"


# --- TC-US13-10 the reusable rule US4 calls ---


def test_tc_us13_10_evaluate_booking_lists_conflicts_and_an_hours_breach(
    db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    """US4's contract: what stops this booking being approved now, from the venue as it is now.
    The stored windows were fine when made; a later block, a later hours edit and buffers changed
    outside the API (so nothing recomputed them) all show up."""
    earlier = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, status=VenueBookingStatus.APPROVED, starts_at=at(10), ends_at=at(12)
    )
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(13, 15), ends_at=at(14))
    db.refresh(earlier)
    block = make_venue_block(db, venue, at(14, 30), at(15), note="Closed for cleaning")
    venue.setup_minutes = 45  # 12:30 setup now runs into the earlier booking's 12:45 turnaround
    venue.closes_at = time(14, 40)  # and the 14:45 turnaround end is now after closing
    db.flush()

    evaluation = evaluate_booking(db, booking)

    assert (evaluation.occupied.starts_at, evaluation.occupied.ends_at) == (at(12, 30), at(14, 45))
    assert [(c.kind, c.reference, c.overlap.starts_at, c.overlap.ends_at) for c in evaluation.conflicts] == [
        ("booking", earlier.reference, at(12, 30), at(12, 45)),
        ("block", None, at(14, 30), at(14, 45)),
    ]
    assert evaluation.conflicts[1].note == block.note
    assert evaluation.outside_hours is not None
    assert evaluation.outside_hours.closes_at == time(14, 40)
    assert evaluation.outside_hours.fields == ["ends_at"]
    assert evaluation.clear is False


def test_tc_us13_10_a_clear_booking_has_nothing_against_it_and_ignores_itself(
    db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))
    make_venue_booking(
        db, event=event, venue=venue, user=coordinator, status=VenueBookingStatus.WITHDRAWN, starts_at=at(10), ends_at=at(12)
    )

    evaluation = evaluate_booking(db, booking)

    assert evaluation.conflicts == []
    assert evaluation.outside_hours is None
    assert evaluation.clear is True


def test_tc_us13_10_evaluate_window_checks_a_window_before_any_booking_exists(db: Session, venue: Venue) -> None:
    make_venue_block(db, venue, at(10, 30), at(11))

    evaluation = evaluate_window(db, venue, at(13), at(14))  # occupies 12:30-14:45
    blocked = evaluate_window(db, venue, at(9), at(10))  # turnaround to 10:45 runs into the block

    assert evaluation.clear is True
    assert [c.kind for c in blocked.conflicts] == ["block"]


# --- TC-US13-11 Venue Staff see the evaluation (AC 4, D36) ---


def evaluation_url(booking_id: uuid.UUID) -> str:
    return f"/api/v1/venue-bookings/{booking_id}/evaluation"


async def test_tc_us13_11_venue_staff_see_a_block_added_after_the_request(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))
    db.refresh(booking)
    make_venue_block(db, venue, at(12, 30), at(13), note="Fire drill")

    response = await client.get(evaluation_url(booking.id), headers=auth(staff))

    assert response.status_code == 200
    payload = response.json()
    assert payload["booking_id"] == str(booking.id)
    assert payload["reference"] == booking.reference
    assert (when(payload["occupied"]["starts_at"]), when(payload["occupied"]["ends_at"])) == (at(9, 30), at(12, 45))
    assert payload["clear"] is False
    [conflict] = payload["conflicts"]
    assert conflict["kind"] == "block"
    assert conflict["note"] == "Fire drill"
    assert (when(conflict["overlap"]["starts_at"]), when(conflict["overlap"]["ends_at"])) == (at(12, 30), at(12, 45))
    assert payload["outside_hours"] is None


async def test_tc_us13_11_venue_staff_see_the_clashing_bookings_reference(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    earlier = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(13, 15), ends_at=at(14))
    db.refresh(earlier)
    venue.setup_minutes = 45
    db.flush()

    payload = (await client.get(evaluation_url(booking.id), headers=auth(staff))).json()

    assert [(c["kind"], c["reference"]) for c in payload["conflicts"]] == [("booking", earlier.reference)]


@pytest.mark.parametrize("role", [UserRole.COORDINATOR, UserRole.ORGANISER, UserRole.ATTENDEE])
async def test_tc_us13_11_only_venue_staff_may_evaluate(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue, role: UserRole
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))

    response = await client.get(evaluation_url(booking.id), headers=auth(make_user(db, role)))

    assert response.status_code == 403


async def test_tc_us13_11_unknown_booking_and_no_identity(client: AsyncClient, staff: User) -> None:
    assert (await client.get(evaluation_url(uuid.uuid4()), headers=auth(staff))).status_code == 404
    assert (await client.get(evaluation_url(uuid.uuid4()))).status_code == 401


# --- TC-US13-12 buffer edits while Requested bookings exist (D31, AC 6) ---


def venue_url(venue: Venue) -> str:
    return f"/api/v1/venues/{venue.id}"


async def test_tc_us13_12_a_buffer_edit_recomputes_requested_bookings_windows(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    first = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))
    second = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(13, 15), ends_at=at(14))

    response = await client.patch(venue_url(venue), headers=auth(staff), json={"setup_minutes": 15, "turnaround_minutes": 30})

    assert response.status_code == 200
    db.expire_all()
    assert (db.get(VenueBooking, first.id).occupied_starts_at, db.get(VenueBooking, first.id).occupied_ends_at) == (
        at(9, 45),
        at(12, 30),
    )
    assert db.get(VenueBooking, second.id).occupied_starts_at == at(13)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"turnaround_minutes": 60}, "overlap"),  # 12:00 + 60 = 13:00, past the next setup at 12:45
        ({"setup_minutes": 150}, "hours"),  # 10:00 - 150 = 07:30, before the 08:00 opening
    ],
    ids=["overlap", "hours"],
)
async def test_tc_us13_12_an_edit_that_would_clash_is_refused_and_nothing_changes(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    staff: User,
    event: Event,
    venue: Venue,
    change: dict[str, int],
    reason: str,
) -> None:
    first = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))
    second = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(13, 15), ends_at=at(14))
    db.refresh(first)
    db.refresh(second)

    response = await client.patch(venue_url(venue), headers=auth(staff), json=change)

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == "VENUE_BUFFERS_CONFLICT"
    assert payload["fields"] == list(change)
    assert first.reference in [b["reference"] for b in payload["bookings"]]
    if reason == "overlap":
        assert {b["reference"] for b in payload["bookings"]} == {first.reference, second.reference}
    assert payload["message"]
    db.expire_all()
    assert (db.get(Venue, venue.id).setup_minutes, db.get(Venue, venue.id).turnaround_minutes) == (30, 45)
    assert db.get(VenueBooking, first.id).occupied_starts_at == at(9, 30)


async def test_tc_us13_12_past_and_ended_bookings_keep_their_windows(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    past = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=NOW - timedelta(days=2), ends_at=NOW - timedelta(days=2, hours=-2)
    )
    withdrawn = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, status=VenueBookingStatus.WITHDRAWN, starts_at=at(10), ends_at=at(12)
    )
    before = {b.id: (b.occupied_starts_at, b.occupied_ends_at) for b in (past, withdrawn)}

    response = await client.patch(venue_url(venue), headers=auth(staff), json={"setup_minutes": 10})

    assert response.status_code == 200
    db.expire_all()
    for booking_id, window in before.items():
        stored = db.get(VenueBooking, booking_id)
        assert (stored.occupied_starts_at, stored.occupied_ends_at) == window


async def test_tc_us13_12_approved_future_bookings_still_lock_the_buffers(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    """AC 6 is US20's lock: it still wins over the recompute (TC-US20-02, TC-US22-03)."""
    make_venue_booking(
        db, event=event, venue=venue, user=coordinator, status=VenueBookingStatus.APPROVED, starts_at=at(10), ends_at=at(12)
    )

    response = await client.patch(venue_url(venue), headers=auth(staff), json={"setup_minutes": 10})

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_BUFFERS_LOCKED"


# --- TC-US13-13 US2 search with each venue's own buffers (D26) ---


async def search(client: AsyncClient, user: User, start: str, end: str):
    params = {"date": DAY.isoformat(), "start_time": start, "end_time": end, "attendees": 20}
    response = await client.get("/api/v1/venues/available", headers=auth(user), params=params)
    assert response.status_code == 200, response.text
    return [venue["name"] for venue in response.json()["venues"]]


async def test_tc_us13_13_search_hides_a_venue_whose_occupied_window_clashes(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    """A booking at 13:15 occupies from 12:45; a search for 10:00-12:00 occupies to 12:45 there. They
    touch, so the venue shows. One minute later and its turnaround runs into the setup."""
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(13, 15), ends_at=at(14))

    assert await search(client, coordinator, "10:00", "12:00") == ["Buffered Hall"]
    assert await search(client, coordinator, "10:00", "12:01") == []


async def test_tc_us13_13_search_hides_a_venue_whose_buffers_run_into_a_block(
    client: AsyncClient, db: Session, coordinator: User, venue: Venue
) -> None:
    make_venue_block(db, venue, at(9), at(9, 30))

    assert await search(client, coordinator, "10:00", "12:00") == ["Buffered Hall"]
    assert await search(client, coordinator, "09:59", "12:00") == []


@pytest.mark.parametrize(
    ("start", "end", "shown"),
    [("08:30", "19:15", True), ("08:29", "12:00", False), ("10:00", "19:16", False)],
    ids=["exactly opening to closing", "setup before opening", "turnaround after closing"],
)
async def test_tc_us13_13_search_needs_the_occupied_window_inside_opening_hours(
    client: AsyncClient, db: Session, coordinator: User, venue: Venue, start: str, end: str, shown: bool
) -> None:
    assert await search(client, coordinator, start, end) == (["Buffered Hall"] if shown else [])


async def test_tc_us13_13_each_venue_uses_its_own_buffers(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_venue(db, name="No buffers", setup_minutes=0, turnaround_minutes=0, opens_at=time(10), closes_at=time(12))
    make_venue(db, name="Ten minute buffers", setup_minutes=10, turnaround_minutes=10, opens_at=time(10), closes_at=time(12))

    assert await search(client, coordinator, "10:00", "12:00") == ["No buffers"]


# --- TC-US13-14 the race on occupied windows ---


@pytest.fixture
def committed(engine: Engine) -> Generator[dict[str, object], None, None]:
    """Committed rows, so separate sessions can see them: two coordinators, each with their own
    assigned event, and one 30/45 venue. Deleted afterwards."""
    with Session(engine) as setup:
        coordinators = [User(email=f"{uuid.uuid4().hex}@smu.edu.sg", role=UserRole.COORDINATOR) for _ in range(2)]
        setup.add_all(coordinators)
        setup.flush()
        events = {
            user.id: make_event(setup, status=EventStatus.APPROVED, coordinator_id=user.id).id for user in coordinators
        }
        venue = make_venue(setup, setup_minutes=30, turnaround_minutes=45, opens_at=time(8), closes_at=time(20))
        setup.commit()
        rows = {"coordinators": [user.id for user in coordinators], "events": events, "venue": venue.id}
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(VenueBooking).where(VenueBooking.venue_id == rows["venue"]))
            cleanup.execute(delete(Venue).where(Venue.id == rows["venue"]))
            cleanup.execute(delete(Event).where(Event.id.in_(list(rows["events"].values()))))
            cleanup.execute(delete(User).where(User.id.in_(rows["coordinators"])))
            cleanup.commit()


def test_tc_us13_14_simultaneous_requests_clashing_only_through_buffers(
    engine: Engine, committed: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """10:00-12:00 and 12:30-13:30 don't overlap, but with 30/45 buffers 09:30-12:45 and 12:00-14:15
    do. Both pass the pre-check at a barrier; the database lets only one in."""
    barrier = threading.Barrier(2, timeout=10)
    held = threading.local()
    original = booking_service_module.evaluate_window

    def evaluate_then_wait(*args: object, **kwargs: object):
        evaluation = original(*args, **kwargs)
        if not getattr(held, "done", False):  # only the first pre-check waits
            held.done = True
            barrier.wait()
        return evaluation

    monkeypatch.setattr(booking_service_module, "evaluate_window", evaluate_then_wait)
    notifier = FakeNotifier()
    outcomes: list[object] = []

    def request(user_id: uuid.UUID, starts_at: datetime, ends_at: datetime) -> None:
        with Session(engine) as session:
            write = VenueBookingWrite(
                event_id=committed["events"][user_id],
                venue_id=committed["venue"],
                starts_at=starts_at,
                ends_at=ends_at,
                expected_attendees=20,
                room_layout="theatre",
            )
            try:
                booking_service.create(session, session.get(User, user_id), write, NOW, notifier)
                outcomes.append(201)
            except DomainError as error:
                outcomes.append((error.status_code, error.code))

    first, second = committed["coordinators"]
    threads = [
        threading.Thread(target=request, args=(first, at(10), at(12))),
        threading.Thread(target=request, args=(second, at(12, 30), at(13, 30))),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(map(str, outcomes)) == sorted(["201", str((409, "VENUE_UNAVAILABLE"))])
    with Session(engine) as check:
        assert check.scalar(select(func.count()).where(VenueBooking.venue_id == committed["venue"])) == 1


# --- TC-US13-15 buffers are for venue bookings only (AC 7) ---


def test_tc_us13_15_buffers_apply_to_venue_bookings_only_not_equipment(engine: Engine) -> None:
    """AC 7: equipment reservations use the event's own times. US26 (SCRUM-108) added them as
    request lines on an event, with no times of their own, so no buffer, occupied window or own
    window can apply to them. Fails if a later story adds buffers or a window to equipment."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with_buffers = {
        table
        for table in tables
        if {"setup_minutes", "turnaround_minutes"} & {column["name"] for column in inspector.get_columns(table)}
    }

    assert with_buffers == {"venues"}
    equipment = [table for table in tables if table.startswith("equipment")]
    assert {"equipment_types", "equipment_request_lines"} <= set(equipment)
    windowed = {"starts_at", "ends_at", "occupied_starts_at", "occupied_ends_at", "setup_minutes", "turnaround_minutes"}
    for table in equipment:
        assert not windowed & {column["name"] for column in inspector.get_columns(table)}, table
