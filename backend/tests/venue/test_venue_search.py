"""US2 search for suitable venues (SCRUM-7): GET /api/v1/venues/available, which leaves out venues
with a live US22 booking (venue_bookings, LIVE_BOOKING_STATUSES) or a block (venue_blocks).
Test cases: docs/testing/US2-venue-search.md. venue_bookings' own schema is US22's
(tests/venue/test_booking_schema.py)."""

import time as clock
import uuid
from datetime import date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.seed import VENUE_BLOCKS, VENUE_BOOKINGS, VENUE_SLOT_IN_DAYS, VENUES, seed, seed_id
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus
from app.venue.service import VENUE_TIMEZONE, venue_service
from tests.factories import NOW, make_event, make_user

pytestmark = pytest.mark.anyio

# NOW is 1 Oct 2026, 09:00 in Singapore; search a day comfortably ahead of it.
DAY = date(2026, 10, 10)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def make_venue(db: Session, **overrides: object) -> Venue:
    fields: dict[str, object] = {
        "name": f"Room {uuid.uuid4().hex[:6]}",
        "location": "SCIS Building, Level 2",
        "capacity": 40,
        "facilities": ["projector", "wifi"],
        "accessibility_features": ["wheelchair"],
        "room_layouts": ["classroom"],
        "opens_at": time(8, 0),
        "closes_at": time(22, 0),
        "setup_minutes": 15,
        "turnaround_minutes": 15,
    }
    venue = Venue(**(fields | overrides))
    db.add(venue)
    db.flush()
    return venue


def at(on: date, clock_time: time) -> datetime:
    return datetime.combine(on, clock_time, VENUE_TIMEZONE)


def book(
    db: Session,
    venue: Venue,
    status: VenueBookingStatus,
    starts: time,
    ends: time,
    on: date = DAY,
) -> VenueBooking:
    """A US22 booking for a fresh approved event, requested by a fresh coordinator."""
    booking = VenueBooking(
        event_id=make_event(db, status=EventStatus.APPROVED).id,
        venue_id=venue.id,
        requested_by_user_id=make_user(db, UserRole.COORDINATOR).id,
        starts_at=at(on, starts),
        ends_at=at(on, ends),
        expected_attendees=20,
        room_layout="classroom",
        status=status,
        withdrawn_at=NOW if status == VenueBookingStatus.WITHDRAWN else None,
        # US4's venue_bookings_decided_consistent: a decided booking carries its decision time.
        decided_at=NOW if status in (VenueBookingStatus.APPROVED, VenueBookingStatus.REJECTED) else None,
    )
    db.add(booking)
    db.flush()
    return booking


def block(db: Session, venue: Venue, starts_at: datetime, ends_at: datetime, note: str | None = None) -> VenueBlock:
    venue_block = VenueBlock(venue_id=venue.id, starts_at=starts_at, ends_at=ends_at, note=note)
    db.add(venue_block)
    db.flush()
    return venue_block


def params(**overrides: object) -> dict[str, object]:
    query: dict[str, object] = {"date": DAY.isoformat(), "start_time": "10:00", "end_time": "12:00", "attendees": 30}
    query.update(overrides)
    return {key: value for key, value in query.items() if value is not None}


async def search(client: AsyncClient, user: User, **overrides: object):
    return await client.get("/api/v1/venues/available", headers=auth(user), params=params(**overrides))


def names(response) -> list[str]:
    return [venue["name"] for venue in response.json()["venues"]]


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


# --- TC-US2-01: search by date, start and end time, and expected attendance (AC 1) ---


async def test_tc_us2_01_returns_suitable_venues_with_the_criteria_applied(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    venue = make_venue(db, name="SCIS Seminar Room 2-1")

    response = await search(client, coordinator)

    assert response.status_code == 200
    assert names(response) == ["SCIS Seminar Room 2-1"]
    assert response.json()["criteria"] == {
        "date": "2026-10-10",
        "start_time": "10:00:00",
        "end_time": "12:00:00",
        "attendees": 30,
        "location": None,
        "facilities": [],
        "accessibility": [],
    }
    assert response.json()["venues"][0]["id"] == str(venue.id)


@pytest.mark.parametrize("missing", ["date", "start_time", "end_time", "attendees"])
async def test_tc_us2_01_each_core_criterion_is_required(
    client: AsyncClient, coordinator: User, missing: str
) -> None:
    response = await search(client, coordinator, **{missing: None})

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": [missing]}


async def test_tc_us2_01_lists_every_missing_criterion_at_once(client: AsyncClient, coordinator: User) -> None:
    response = await client.get("/api/v1/venues/available", headers=auth(coordinator))

    assert response.status_code == 422
    assert response.json()["fields"] == ["date", "start_time", "end_time", "attendees"]


async def test_tc_us2_01_an_empty_attendance_counts_as_missing(client: AsyncClient, coordinator: User) -> None:
    response = await search(client, coordinator, attendees="")

    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": ["attendees"]}


# --- TC-US2-02: filter by location, accessibility and facilities (AC 2) ---


async def test_tc_us2_02_location_is_a_case_insensitive_substring(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_venue(db, name="In SCIS", location="SCIS Building, Level 2")
    make_venue(db, name="In Library", location="Li Ka Shing Library, Level 3")

    response = await search(client, coordinator, location="  library ")

    assert names(response) == ["In Library"]
    assert response.json()["criteria"]["location"] == "library"


@pytest.mark.parametrize("blank", ["   ", "\t"])
async def test_tc_us2_02_a_whitespace_location_is_no_filter(
    client: AsyncClient, db: Session, coordinator: User, blank: str
) -> None:
    make_venue(db, name="Anywhere", location="SCIS Building")

    response = await search(client, coordinator, location=blank)

    assert names(response) == ["Anywhere"]
    assert response.json()["criteria"]["location"] is None


async def test_tc_us2_02_location_wildcards_are_literal(client: AsyncClient, db: Session, coordinator: User) -> None:
    make_venue(db, name="Plain", location="Level 2")

    response = await search(client, coordinator, location="%")

    assert names(response) == []


async def test_tc_us2_02_a_venue_needs_every_required_facility_and_feature(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_venue(db, name="Both", facilities=["projector", "wifi", "stage"], accessibility_features=["wheelchair", "lift"])
    make_venue(db, name="No stage", facilities=["projector", "wifi"], accessibility_features=["wheelchair", "lift"])
    make_venue(db, name="No lift", facilities=["projector", "stage"], accessibility_features=["wheelchair"])

    response = await client.get(
        "/api/v1/venues/available",
        headers=auth(coordinator),
        params=[*params().items(), ("facilities", "stage"), ("facilities", "projector"), ("accessibility", "lift")],
    )

    assert names(response) == ["Both"]
    # Echoed in D18's order, whatever order they were sent in.
    assert response.json()["criteria"]["facilities"] == ["projector", "stage"]
    assert response.json()["criteria"]["accessibility"] == ["lift"]


async def test_tc_us2_02_filters_combine_with_the_core_criteria(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_venue(db, name="Small with stage", capacity=10, facilities=["stage"])
    make_venue(db, name="Big with stage", capacity=100, facilities=["stage"])

    response = await search(client, coordinator, facilities="stage", attendees=50)

    assert names(response) == ["Big with stage"]


# --- TC-US2-03: each result shows capacity, facilities and accessibility (AC 3) ---


async def test_tc_us2_03_results_carry_capacity_facilities_and_accessibility(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_venue(db, capacity=60, facilities=["projector", "screen"], accessibility_features=["wheelchair", "lift"])

    [result] = (await search(client, coordinator)).json()["venues"]

    assert result["capacity"] == 60
    assert result["facilities"] == ["projector", "screen"]
    assert result["accessibility_features"] == ["wheelchair", "lift"]
    assert {"name", "location", "opens_at", "closes_at", "room_layouts"} <= result.keys()


# --- TC-US2-04: only venues with capacity >= expected attendance (AC 4) ---


async def test_tc_us2_04_capacity_must_cover_the_attendance(client: AsyncClient, db: Session, coordinator: User) -> None:
    make_venue(db, name="Exactly 30", capacity=30)
    make_venue(db, name="29 seats", capacity=29)
    make_venue(db, name="200 seats", capacity=200)

    response = await search(client, coordinator, attendees=30)

    # Equal capacity counts; smallest suitable venue first.
    assert names(response) == ["Exactly 30", "200 seats"]


# --- TC-US2-05: booked, held (requested) or blocked venues are left out (AC 5) ---


@pytest.mark.parametrize("status", [VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED])
async def test_tc_us2_05_an_overlapping_live_booking_hides_the_venue(
    client: AsyncClient, db: Session, coordinator: User, status: VenueBookingStatus
) -> None:
    """AC 5's "tentatively held" is US22's requested; "booked" is approved (LIVE_BOOKING_STATUSES)."""
    taken = make_venue(db, name="Taken")
    make_venue(db, name="Free")
    book(db, taken, status, time(11, 0), time(13, 0))

    response = await search(client, coordinator)

    assert names(response) == ["Free"]


@pytest.mark.parametrize("status", [VenueBookingStatus.REJECTED, VenueBookingStatus.WITHDRAWN])
async def test_tc_us2_05_rejected_and_withdrawn_bookings_dont_count(
    client: AsyncClient, db: Session, coordinator: User, status: VenueBookingStatus
) -> None:
    venue = make_venue(db, name="Was booked")
    book(db, venue, status, time(10, 0), time(12, 0))

    assert names(await search(client, coordinator)) == ["Was booked"]


async def test_tc_us2_05_an_overlapping_block_hides_the_venue(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    closed = make_venue(db, name="Closed")
    make_venue(db, name="Open", capacity=50)
    block(db, closed, at(DAY, time(11, 0)), at(DAY, time(15, 0)), "Maintenance")

    assert names(await search(client, coordinator)) == ["Open"]


async def test_tc_us2_05_a_multi_day_block_hides_the_venue_on_a_middle_day(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    """A block's main real use: a venue closed for days (PR #65 review)."""
    venue = make_venue(db, name="Closed for refurbishment")
    block(db, venue, at(DAY - timedelta(days=2), time(0, 0)), at(DAY + timedelta(days=2), time(0, 0)))

    assert names(await search(client, coordinator)) == []
    # The day it ends (at midnight), the venue is back.
    after = await search(client, coordinator, date=(DAY + timedelta(days=2)).isoformat())
    assert names(after) == ["Closed for refurbishment"]


@pytest.mark.parametrize(
    ("starts", "ends", "clashes"),
    [
        (time(8, 0), time(10, 0), False),  # ends as the search starts
        (time(12, 0), time(14, 0), False),  # starts as the search ends
        (time(9, 0), time(10, 1), True),  # overlaps the start by a minute
        (time(11, 59), time(13, 0), True),  # overlaps the end by a minute
        (time(10, 30), time(11, 30), True),  # inside the search
        (time(8, 0), time(18, 0), True),  # covers the whole search
    ],
    ids=["back-to-back before", "back-to-back after", "overlaps start", "overlaps end", "inside", "covers"],
)
@pytest.mark.parametrize("kind", ["booking", "block"])
async def test_tc_us2_05_overlap_is_half_open(
    client: AsyncClient, db: Session, coordinator: User, starts: time, ends: time, clashes: bool, kind: str
) -> None:
    """Half-open like US22's venue_bookings_no_overlap, for bookings and blocks alike."""
    venue = make_venue(db, name="Venue")
    if kind == "booking":
        book(db, venue, VenueBookingStatus.APPROVED, starts, ends)
    else:
        block(db, venue, at(DAY, starts), at(DAY, ends))

    assert names(await search(client, coordinator)) == ([] if clashes else ["Venue"])


async def test_tc_us2_05_a_booking_or_block_on_another_day_or_venue_doesnt_count(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    venue = make_venue(db, name="Venue")
    other = make_venue(db, name="Other", capacity=500)
    book(db, venue, VenueBookingStatus.APPROVED, time(10, 0), time(12, 0), on=DAY + timedelta(days=1))
    block(db, venue, at(DAY - timedelta(days=1), time(10, 0)), at(DAY - timedelta(days=1), time(12, 0)))
    book(db, other, VenueBookingStatus.APPROVED, time(10, 0), time(12, 0))

    assert names(await search(client, coordinator)) == ["Venue"]


async def test_tc_us2_05_inactive_venues_never_appear(client: AsyncClient, db: Session, coordinator: User) -> None:
    """US20 AC 3: a deactivated venue leaves search."""
    make_venue(db, name="Closed for good", is_active=False)

    assert names(await search(client, coordinator)) == []


# --- TC-US2-06: the requested time must fall inside operating hours (AC 6) ---


@pytest.mark.parametrize(
    ("start", "end", "inside"),
    [
        ("09:00", "18:00", True),  # exactly the opening hours
        ("08:59", "12:00", False),  # starts before opening
        ("12:00", "18:01", False),  # ends after closing
        ("07:00", "08:30", False),  # entirely before opening
    ],
    ids=["exactly the hours", "starts before opening", "ends after closing", "before opening"],
)
async def test_tc_us2_06_operating_hours_must_cover_the_whole_time(
    client: AsyncClient, db: Session, coordinator: User, start: str, end: str, inside: bool
) -> None:
    make_venue(db, name="Nine to six", opens_at=time(9, 0), closes_at=time(18, 0))

    response = await search(client, coordinator, start_time=start, end_time=end)

    assert names(response) == (["Nine to six"] if inside else [])


# --- TC-US2-07: nothing matches → empty list with the criteria applied (AC 7) ---


async def test_tc_us2_07_no_match_is_an_empty_list_with_the_criteria(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_venue(db, capacity=20)

    response = await client.get(
        "/api/v1/venues/available",
        headers=auth(coordinator),
        params=[*params(attendees=500, location="Library").items(), ("facilities", "stage")],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["venues"] == []
    assert body["criteria"]["attendees"] == 500
    assert body["criteria"]["location"] == "Library"
    assert body["criteria"]["facilities"] == ["stage"]


# --- TC-US2-08: results within 3 seconds (AC 8) ---


def _fill_calendar(db: Session, venue_count: int, days: int) -> list[Venue]:
    """Many venues, an approved booking on every other venue each day and a block on every fifth,
    inserted in bulk so the setup stays fast. One event and requester serve every booking."""
    venues = [make_venue(db, name=f"Bulk {i:04}", capacity=20 + i) for i in range(venue_count)]
    event_id = make_event(db, status=EventStatus.APPROVED).id
    requester_id = make_user(db, UserRole.COORDINATOR).id
    db.add_all(
        VenueBooking(
            event_id=event_id,
            venue_id=venue.id,
            requested_by_user_id=requester_id,
            starts_at=at(DAY + timedelta(days=d), time(10, 0)),
            ends_at=at(DAY + timedelta(days=d), time(12, 0)),
            expected_attendees=20,
            room_layout="classroom",
            status=VenueBookingStatus.APPROVED,
            decided_at=NOW,
        )
        for venue in venues[::2]
        for d in range(days)
    )
    db.add_all(
        VenueBlock(
            venue_id=venue.id,
            starts_at=at(DAY + timedelta(days=d), time(14, 0)),
            ends_at=at(DAY + timedelta(days=d), time(16, 0)),
        )
        for venue in venues[::5]
        for d in range(days)
    )
    db.flush()
    return venues


async def test_tc_us2_08_searches_a_large_catalogue_well_within_3_seconds(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    """500 venues, 5,000 bookings and 1,000 blocks, far beyond the real catalogue."""
    venues = _fill_calendar(db, 500, 10)

    started = clock.perf_counter()
    response = await search(client, coordinator, attendees=100)
    elapsed = clock.perf_counter() - started

    assert response.status_code == 200
    # Every other venue is booked 10:00-12:00 on DAY; of the rest, capacity 100 or more.
    assert len(response.json()["venues"]) == len([v for v in venues[1::2] if v.capacity >= 100])
    assert elapsed < 3


def test_tc_us2_08_bookings_and_blocks_are_reached_through_an_index(db: Session) -> None:
    """Backs AC 8's "one indexed query" with the plan, not just a timing: a few thousand rows are
    fast on a sequential scan too (PR #65 review). 2,000 venues, 50,000 bookings, 20,000 blocks.
    Runs the service's own statement with its bind parameters."""
    _fill_calendar(db, 2_000, 50)
    db.execute(text("analyze venue_bookings"))
    db.execute(text("analyze venue_blocks"))
    db.execute(text("analyze venues"))

    captured: list = []
    real_scalars = db.scalars

    def capture(statement, *args, **kwargs):
        captured.append(statement)
        return real_scalars(statement, *args, **kwargs)

    db.scalars = capture  # type: ignore[method-assign]
    try:
        venue_service.find_available(db, NOW, on=DAY, start_time=time(10, 0), end_time=time(12, 0), attendees=30)
    finally:
        db.scalars = real_scalars  # type: ignore[method-assign]

    # Bound values inlined, so the planner sees the real statuses, times and attendance.
    compiled = captured[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    plan = "\n".join(row[0] for row in db.execute(text(f"explain {compiled}".replace(":", "\\:"))))

    for table in ("venue_bookings", "venue_blocks"):
        nodes = [line for line in plan.splitlines() if f" on {table}" in line]
        assert nodes, plan
        assert all("Seq Scan" not in line for line in nodes), plan


# --- TC-US2-09: invalid criteria ---


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"date": "2026-09-30"}, "date"),
        ({"start_time": "12:00", "end_time": "12:00"}, "end_time"),
        ({"start_time": "14:00", "end_time": "12:00"}, "end_time"),
        ({"attendees": 0}, "attendees"),
        ({"facilities": "jacuzzi"}, "facilities"),
        ({"accessibility": "ramp"}, "accessibility"),
    ],
    ids=["past date", "zero length", "ends before it starts", "no attendees", "unknown facility", "unknown feature"],
)
async def test_tc_us2_09_invalid_criteria_are_refused_naming_the_field(
    client: AsyncClient, coordinator: User, overrides: dict, field: str
) -> None:
    response = await search(client, coordinator, **overrides)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_VENUE_SEARCH"
    assert body["fields"] == [field]
    assert body["errors"][field]


@pytest.mark.parametrize("attendees", ["lots", "1.5", "1e3", "-"])
async def test_tc_us2_09_a_non_whole_attendance_is_a_field_error(
    client: AsyncClient, coordinator: User, attendees: str
) -> None:
    """Named on `attendees`, so the form marks it, not FastAPI's generic 422 (PR #65 review)."""
    response = await search(client, coordinator, attendees=attendees)

    assert response.status_code == 422
    assert response.json() == {
        "code": "INVALID_VENUE_SEARCH",
        "fields": ["attendees"],
        "errors": {"attendees": "Expected attendance must be a whole number."},
    }


async def test_tc_us2_09_attendance_takes_surrounding_spaces(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_venue(db, name="Venue", capacity=40)

    response = await search(client, coordinator, attendees=" 30 ")

    assert names(response) == ["Venue"]
    assert response.json()["criteria"]["attendees"] == 30


async def test_tc_us2_09_today_counts_as_not_past(client: AsyncClient, db: Session, coordinator: User) -> None:
    make_venue(db, name="Today")

    response = await search(client, coordinator, date=NOW.date().isoformat(), start_time="18:00", end_time="19:00")

    assert response.status_code == 200
    assert names(response) == ["Today"]


# --- TC-US2-10: who may search (D25) ---


async def test_tc_us2_10_coordinators_and_operations_managers_may_search(client: AsyncClient, db: Session) -> None:
    make_venue(db, name="Venue")
    for role in (UserRole.COORDINATOR, UserRole.OPERATIONS_MANAGER):
        response = await search(client, make_user(db, role))
        assert response.status_code == 200, role
        assert names(response) == ["Venue"]


@pytest.mark.parametrize("role", [UserRole.ORGANISER, UserRole.ATTENDEE])
async def test_tc_us2_10_other_roles_get_403(client: AsyncClient, db: Session, role: UserRole) -> None:
    response = await search(client, make_user(db, role))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_tc_us2_10_no_identity_is_401_and_inactive_is_403(client: AsyncClient, db: Session) -> None:
    anonymous = await client.get("/api/v1/venues/available", params=params())
    inactive = await search(client, make_user(db, UserRole.COORDINATOR, active=False))

    assert anonymous.status_code == 401
    assert inactive.status_code == 403


async def test_tc_us2_10_available_isnt_read_as_a_venue_id(client: AsyncClient, coordinator: User) -> None:
    """The route is declared before /{venue_id}; otherwise "available" would be a 422 bad uuid."""
    response = await client.get("/api/v1/venues/available", headers=auth(coordinator))

    assert response.json()["code"] == "MISSING_REQUIRED_FIELD"


# --- TC-US2-11: the venue_blocks table ---


def test_tc_us2_11_blocks_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("venue_blocks")} == {
        "id",
        "venue_id",
        "starts_at",
        "ends_at",
        "note",
        "created_at",
    }
    assert {c["name"] for c in inspector.get_check_constraints("venue_blocks")} == {"venue_blocks_window_valid"}
    assert "venue_blocks_venue_window" in {index["name"] for index in inspector.get_indexes("venue_blocks")}
    assert {fk["referred_table"] for fk in inspector.get_foreign_keys("venue_blocks")} == {"venues"}
    assert (
        db.execute(text("select relrowsecurity from pg_class where oid = 'venue_blocks'::regclass")).scalar_one()
        is True
    )


@pytest.mark.parametrize(
    ("starts", "ends"),
    [(time(12, 0), time(12, 0)), (time(13, 0), time(12, 0))],
    ids=["zero length", "ends before it starts"],
)
def test_tc_us2_11_database_rejects_an_empty_or_reversed_block(db: Session, starts: time, ends: time) -> None:
    venue = make_venue(db)
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            block(db, venue, at(DAY, starts), at(DAY, ends))

    assert raised.value.orig.diag.constraint_name == "venue_blocks_window_valid"


def test_tc_us2_11_blocks_may_overlap_each_other_and_bookings(db: Session) -> None:
    """Only bookings are kept apart (US22's venue_bookings_no_overlap); a block just closes the venue."""
    venue = make_venue(db)
    block(db, venue, at(DAY, time(9, 0)), at(DAY, time(12, 0)))
    block(db, venue, at(DAY, time(10, 0)), at(DAY, time(14, 0)))
    book(db, venue, VenueBookingStatus.APPROVED, time(10, 0), time(12, 0))


def test_tc_us2_11_blocks_have_no_buffer_columns(engine) -> None:
    """US20 AC 7 still holds: buffers belong to the venue only."""
    columns = {column["name"] for column in inspect(engine).get_columns("venue_blocks")}

    assert not {"setup_minutes", "turnaround_minutes"} & columns


# --- TC-US2-12: the seed shows AC 5 ---


def test_tc_us2_12_seed_books_and_blocks_three_venues_on_one_slot(db: Session) -> None:
    seed(db, now=NOW)
    seed(db, now=NOW)  # idempotent

    bookings = db.scalars(select(VenueBooking)).all()
    blocks = db.scalars(select(VenueBlock)).all()
    assert len(bookings) == len(VENUE_BOOKINGS) == 2
    assert len(blocks) == len(VENUE_BLOCKS) == 1
    assert {booking.status for booking in bookings} == {VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED}

    # Each booking is for an approved event and requested by the seeded coordinator (US22's rules).
    coordinator_id = seed_id("user", "event-coordinator")
    for booking in bookings:
        assert db.get(Event, booking.event_id).status == EventStatus.APPROVED
        assert booking.requested_by_user_id == coordinator_id

    # All three cover 10:00-12:00 Singapore time on the slot day, at active seeded venues.
    day = NOW.date() + timedelta(days=VENUE_SLOT_IN_DAYS)
    active_seeded = {seed_id("venue", spec.slug) for spec in VENUES if spec.is_active}
    for row in [*bookings, *blocks]:
        assert row.starts_at <= at(day, time(10, 0)) and row.ends_at >= at(day, time(12, 0))
        assert row.venue_id in active_seeded


async def test_tc_us2_12_seeded_slot_leaves_the_booked_and_blocked_venues_out(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    seed(db, now=NOW)

    response = await search(
        client, coordinator, date=(NOW.date() + timedelta(days=VENUE_SLOT_IN_DAYS)).isoformat(), attendees=20
    )

    assert names(response) == ["Li Ka Shing Library Seminar Room 3-4", "Campus Green, Lawn C"]
