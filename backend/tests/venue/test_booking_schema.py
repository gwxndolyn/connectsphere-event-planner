"""US22 venue booking request, PR 1 (SCRUM-111, story SCRUM-89): the `venue_bookings` table, its
overlap guard and the real buffer-lock query. The API checks come in PR 2; see
docs/testing/US22-venue-booking.md."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue import service as venue_service_module
from app.venue.models import Venue, VenueBooking, VenueBookingStatus
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

AGREED_COLUMNS = {
    "id",
    "event_id",
    "venue_id",
    "requested_by_user_id",
    "starts_at",
    "ends_at",
    "expected_attendees",
    "room_layout",
    "required_facilities",
    "required_accessibility_features",
    "special_requirements",
    "status",
    "created_at",
    "updated_at",
    "withdrawn_at",
    # US4 (SCRUM-8): Venue Staff's decision.
    "decided_at",
    "decided_by_user_id",
    "rejection_reason",
    "alternative_suggestion",
}
# Every refused overlap names this constraint (AC 3 and 7).
NO_OVERLAP = "venue_bookings_no_overlap"
START = NOW + timedelta(days=7)
END = START + timedelta(hours=2)


@pytest.fixture
def event(db: Session) -> Event:
    # DECISION-PENDING: D24 — nothing approves a request until US17 (SCRUM-84), so tests create
    # the event straight in `approved`.
    return make_event(db, status=EventStatus.APPROVED)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db)


def refused_constraint(db: Session, **booking: object) -> str:
    """Adds a booking that the database must refuse, and returns the constraint it broke."""
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_venue_booking(db, **booking)
    return raised.value.orig.diag.constraint_name


# --- TC-US22-01 schema ---


def test_tc_us22_01_a_booking_with_every_field_round_trips(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    booking = make_venue_booking(
        db,
        event=event,
        venue=venue,
        user=coordinator,
        expected_attendees=35,
        room_layout="classroom",
        required_facilities=["projector", "wifi"],
        required_accessibility_features=["wheelchair"],
        special_requirements="Lectern at the front, please.",
    )
    db.expire(booking)

    stored = db.get(VenueBooking, booking.id)
    assert (stored.event_id, stored.venue_id, stored.requested_by_user_id) == (event.id, venue.id, coordinator.id)
    assert (stored.starts_at, stored.ends_at) == (START, END)
    assert stored.expected_attendees == 35
    assert stored.room_layout == "classroom"
    assert stored.required_facilities == ["projector", "wifi"]
    assert stored.required_accessibility_features == ["wheelchair"]
    assert stored.special_requirements == "Lectern at the front, please."
    assert stored.status == VenueBookingStatus.REQUESTED
    assert stored.created_at is not None and stored.updated_at is not None
    assert stored.withdrawn_at is None


def test_tc_us22_01_tags_and_requirements_are_optional(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator)
    db.expire(booking)

    stored = db.get(VenueBooking, booking.id)
    assert stored.required_facilities == []
    assert stored.required_accessibility_features == []
    assert stored.special_requirements is None


def test_tc_us22_01_new_bookings_start_as_requested(db: Session, event: Event, venue: Venue, coordinator: User) -> None:
    booking = VenueBooking(
        event_id=event.id,
        venue_id=venue.id,
        requested_by_user_id=coordinator.id,
        starts_at=START,
        ends_at=END,
        expected_attendees=10,
        room_layout="theatre",
    )
    db.add(booking)
    db.flush()
    db.refresh(booking)

    assert booking.status == VenueBookingStatus.REQUESTED


def test_tc_us22_01_booking_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("venue_bookings")} == AGREED_COLUMNS
    assert {constraint["name"] for constraint in inspector.get_check_constraints("venue_bookings")} == {
        "venue_bookings_window_valid",
        "venue_bookings_expected_attendees_positive",
        "venue_bookings_room_layout_known",
        "venue_bookings_required_facilities_known",
        "venue_bookings_required_accessibility_features_known",
        "venue_bookings_withdrawn_consistent",
        "venue_bookings_decided_consistent",  # US4
        "venue_bookings_rejection_notes_only_when_rejected",  # US4
    }
    exclusions = db.scalars(
        text("select conname from pg_constraint where conrelid = 'venue_bookings'::regclass and contype = 'x'")
    ).all()
    assert exclusions == [NO_OVERLAP]
    assert (
        db.execute(text("select relrowsecurity from pg_class where oid = 'venue_bookings'::regclass")).scalar_one()
        is True
    )


@pytest.mark.parametrize(
    ("status", "withdrawn_at"),
    [
        (VenueBookingStatus.WITHDRAWN, None),
        (VenueBookingStatus.REQUESTED, NOW),
        (VenueBookingStatus.APPROVED, NOW),
        (VenueBookingStatus.REJECTED, NOW),
    ],
    ids=["withdrawn without a timestamp", "requested with one", "approved with one", "rejected with one"],
)
def test_tc_us22_01_withdrawn_at_is_set_exactly_when_withdrawn(
    db: Session, event: Event, venue: Venue, coordinator: User, status: VenueBookingStatus, withdrawn_at: datetime | None
) -> None:
    constraint = refused_constraint(
        db, event=event, venue=venue, user=coordinator, status=status, withdrawn_at=withdrawn_at
    )

    assert constraint == "venue_bookings_withdrawn_consistent"


def test_tc_us22_01_withdrawing_without_a_timestamp_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    """The rule holds on update too, so a withdraw can't forget to say when."""
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator)

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            booking.status = VenueBookingStatus.WITHDRAWN
            db.flush()

    assert raised.value.orig.diag.constraint_name == "venue_bookings_withdrawn_consistent"


def test_tc_us22_01_updated_at_changes_on_update(db: Session, event: Event, venue: Venue, coordinator: User) -> None:
    """PR #64 review: any update stamps updated_at. The test transaction's now() is the same at
    insert and update, so the booking starts with an older updated_at to see it move."""
    earlier = NOW - timedelta(days=1)
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, updated_at=earlier)
    assert booking.updated_at == earlier

    booking.expected_attendees = 35
    db.flush()
    db.refresh(booking)

    assert booking.updated_at == db.scalar(select(func.now()))
    assert booking.updated_at > earlier


def test_tc_us22_01_bookings_have_no_buffer_columns(engine) -> None:
    """TC-US20-07's booking half: setup and turnaround belong to the venue, so a booking can't
    carry its own."""
    columns = {column["name"] for column in inspect(engine).get_columns("venue_bookings")}

    assert not {"setup_minutes", "turnaround_minutes"} & columns


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"ends_at": START}, "venue_bookings_window_valid"),
        ({"ends_at": START - timedelta(minutes=1)}, "venue_bookings_window_valid"),
        ({"expected_attendees": 0}, "venue_bookings_expected_attendees_positive"),
        ({"room_layout": "amphitheatre"}, "venue_bookings_room_layout_known"),
        ({"required_facilities": ["projector", "jacuzzi"]}, "venue_bookings_required_facilities_known"),
        ({"required_accessibility_features": ["ramp"]}, "venue_bookings_required_accessibility_features_known"),
    ],
    ids=[
        "ends when it starts",
        "ends before it starts",
        "no attendees",
        "unknown layout",
        "unknown facility",
        "unknown accessibility feature",
    ],
)
def test_tc_us22_01_database_rejects_invalid_bookings(
    db: Session, event: Event, venue: Venue, coordinator: User, overrides: dict, constraint: str
) -> None:
    assert refused_constraint(db, event=event, venue=venue, user=coordinator, **overrides) == constraint


# --- TC-US22-02 the overlap guard ---


@pytest.mark.parametrize("existing", [VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED])
def test_tc_us22_02_overlapping_live_booking_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User, existing: VenueBookingStatus
) -> None:
    # D21 (decided): a Requested booking blocks the window too, so AC 7's first request wins.
    make_venue_booking(db, event=event, venue=venue, user=coordinator, status=existing)

    constraint = refused_constraint(
        db,
        event=event,
        venue=venue,
        user=make_user(db, UserRole.COORDINATOR),
        starts_at=START + timedelta(minutes=30),
        ends_at=END + timedelta(minutes=30),
    )

    assert constraint == NO_OVERLAP


@pytest.mark.parametrize(
    ("starts_at", "ends_at"),
    [
        (END - timedelta(seconds=1), END + timedelta(hours=1)),
        (START - timedelta(hours=1), START + timedelta(seconds=1)),
        (START + timedelta(minutes=15), END - timedelta(minutes=15)),
        (START - timedelta(hours=1), END + timedelta(hours=1)),
    ],
    ids=["one second into the end", "one second into the start", "inside", "around"],
)
def test_tc_us22_02_any_overlap_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User, starts_at: datetime, ends_at: datetime
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator)

    constraint = refused_constraint(
        db, event=event, venue=venue, user=coordinator, starts_at=starts_at, ends_at=ends_at
    )

    assert constraint == NO_OVERLAP


def test_tc_us22_02_back_to_back_bookings_are_allowed(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator)

    after = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=END, ends_at=END + timedelta(hours=1))
    before = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=START - timedelta(hours=1), ends_at=START
    )

    assert after.id and before.id


@pytest.mark.parametrize("existing", [VenueBookingStatus.WITHDRAWN, VenueBookingStatus.REJECTED])
def test_tc_us22_02_withdrawn_and_rejected_bookings_do_not_block(
    db: Session, event: Event, venue: Venue, coordinator: User, existing: VenueBookingStatus
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, status=existing)

    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator)

    assert booking.status == VenueBookingStatus.REQUESTED


def test_tc_us22_02_withdrawing_frees_the_window(db: Session, event: Event, venue: Venue, coordinator: User) -> None:
    first = make_venue_booking(db, event=event, venue=venue, user=coordinator)
    first.status = VenueBookingStatus.WITHDRAWN
    first.withdrawn_at = NOW
    db.flush()

    second = make_venue_booking(db, event=event, venue=venue, user=coordinator)

    assert second.status == VenueBookingStatus.REQUESTED


def test_tc_us22_02_another_venue_at_the_same_time_is_fine(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator)

    elsewhere = make_venue_booking(db, event=event, venue=make_venue(db, name="Other Room"), user=coordinator)

    assert elsewhere.status == VenueBookingStatus.REQUESTED


# --- TC-US22-03 the buffer lock reads real bookings ---


def test_tc_us22_03_approved_future_booking_locks_the_buffers(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, status=VenueBookingStatus.APPROVED)

    assert venue_service_module.has_approved_future_bookings(db, venue.id, NOW) is True


def test_tc_us22_03_booking_under_way_still_locks_the_buffers(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    make_venue_booking(
        db,
        event=event,
        venue=venue,
        user=coordinator,
        status=VenueBookingStatus.APPROVED,
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(hours=1),
    )

    assert venue_service_module.has_approved_future_bookings(db, venue.id, NOW) is True


@pytest.mark.parametrize(
    ("status", "starts_at", "ends_at"),
    [
        (VenueBookingStatus.REQUESTED, START, END),
        (VenueBookingStatus.WITHDRAWN, START, END),
        (VenueBookingStatus.REJECTED, START, END),
        (VenueBookingStatus.APPROVED, NOW - timedelta(hours=3), NOW - timedelta(hours=1)),
        (VenueBookingStatus.APPROVED, NOW - timedelta(hours=2), NOW),
    ],
    ids=["requested", "withdrawn", "rejected", "approved but past", "approved and ending now"],
)
def test_tc_us22_03_other_bookings_do_not_lock_the_buffers(
    db: Session,
    event: Event,
    venue: Venue,
    coordinator: User,
    status: VenueBookingStatus,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    make_venue_booking(
        db, event=event, venue=venue, user=coordinator, status=status, starts_at=starts_at, ends_at=ends_at
    )

    assert venue_service_module.has_approved_future_bookings(db, venue.id, NOW) is False


def test_tc_us22_03_approved_booking_elsewhere_does_not_lock_this_venue(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    other = make_venue(db, name="Other Room")
    make_venue_booking(db, event=event, venue=other, user=coordinator, status=VenueBookingStatus.APPROVED)

    assert venue_service_module.has_approved_future_bookings(db, venue.id, NOW) is False


@pytest.mark.anyio
async def test_tc_us22_03_buffer_lock_triggers_without_forcing_it(
    client: AsyncClient, db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    """TC-US20-02 against a real Approved booking, not the forced stub."""
    make_venue_booking(db, event=event, venue=venue, user=coordinator, status=VenueBookingStatus.APPROVED)
    staff = make_user(db, UserRole.OPERATIONS_MANAGER)  # D19: stands in for Venue Staff until US16b

    response = await client.patch(
        f"/api/v1/venues/{venue.id}", headers={"X-User-Id": str(staff.id)}, json={"setup_minutes": 45}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_BUFFERS_LOCKED"
    assert response.json()["fields"] == ["setup_minutes"]
    db.expire_all()
    assert db.get(Venue, venue.id).setup_minutes == 30
