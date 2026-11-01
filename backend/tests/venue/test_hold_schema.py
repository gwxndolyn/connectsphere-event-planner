"""US25 (SCRUM-93) PR 1: the held and expired statuses, the hold columns and the widened overlap guard.
See docs/testing/US25-venue-holds.md."""

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.availability import evaluate_window
from app.venue.models import BLOCKING_STATUSES, LIVE_BOOKING_STATUSES, Venue, VenueBookingStatus
from tests.conftest import assert_one_head_including
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

REVISION = "20261115_1200_us25_holds"
START = NOW + timedelta(days=7)


@pytest.fixture
def staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    return make_event(db, status=EventStatus.PLANNING, coordinator_id=coordinator.id)


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db)


def hold(db: Session, event: Event, venue: Venue, staff: User, **overrides: object):
    fields: dict[str, object] = {
        "status": VenueBookingStatus.HELD,
        "hold_expires_at": NOW + timedelta(days=3),
        "held_by_user_id": staff.id,
        "is_primary": False,
        "starts_at": START,
    }
    fields.update(overrides)
    return make_venue_booking(db, event=event, venue=venue, user=staff, **fields)


def refused(db: Session, constraint: str, **kwargs: object) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        hold(db, **kwargs)
    db.rollback()


def test_tc_us25_01_statuses_and_columns_are_installed(db: Session) -> None:
    statuses = db.scalars(
        text(
            "select enumlabel from pg_enum join pg_type on pg_type.oid = pg_enum.enumtypid "
            "where pg_type.typname = 'venue_booking_status' order by enumsortorder"
        )
    ).all()
    assert statuses == ["requested", "approved", "rejected", "withdrawn", "held", "expired"]
    # A hold blocks the window (AC 2) but is no booking anywhere else (AC 6).
    assert set(BLOCKING_STATUSES) - set(LIVE_BOOKING_STATUSES) == {VenueBookingStatus.HELD}


def test_tc_us25_01_migrations_have_one_head() -> None:
    assert_one_head_including(REVISION)


def test_tc_us25_02_a_hold_blocks_an_overlapping_request(
    db: Session, event: Event, venue: Venue, staff: User, coordinator: User
) -> None:
    hold(db, event, venue, staff)

    with pytest.raises(IntegrityError, match="venue_bookings_no_overlap"):
        make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START, is_primary=False)
    db.rollback()


def test_tc_us25_02_an_expired_hold_blocks_nothing(
    db: Session, event: Event, venue: Venue, staff: User, coordinator: User
) -> None:
    hold(db, event, venue, staff, status=VenueBookingStatus.EXPIRED, expired_at=NOW + timedelta(days=3))

    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START)


@pytest.mark.parametrize(
    "overrides",
    [
        {"hold_expires_at": None, "held_by_user_id": None},  # held, with no expiry (AC 1)
        {"held_by_user_id": None},  # an expiry, but nobody placed it
        # warned, but no hold
        {"status": VenueBookingStatus.REQUESTED, "hold_expires_at": None, "held_by_user_id": None, "hold_warned_at": NOW},
    ],
    ids=["held without an expiry", "expiry without who", "warning without a hold"],
)
def test_tc_us25_03_hold_fields_follow_the_status(
    db: Session, event: Event, venue: Venue, staff: User, overrides: dict[str, object]
) -> None:
    refused(db, "venue_bookings_hold_consistent", event=event, venue=venue, staff=staff, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [{"status": VenueBookingStatus.EXPIRED}, {"expired_at": NOW}],
    ids=["expired without a time", "a time while still held"],
)
def test_tc_us25_03_expired_at_is_set_exactly_when_expired(
    db: Session, event: Event, venue: Venue, staff: User, overrides: dict[str, object]
) -> None:
    refused(db, "venue_bookings_expired_consistent", event=event, venue=venue, staff=staff, **overrides)


def test_tc_us25_03_a_hold_is_warned_before_its_expiry(db: Session, event: Event, venue: Venue, staff: User) -> None:
    refused(
        db, "venue_bookings_hold_consistent", event=event, venue=venue, staff=staff,
        hold_warned_at=NOW + timedelta(days=3),
    )


def test_tc_us25_03_a_hold_is_requested_by_whoever_placed_it(
    db: Session, event: Event, venue: Venue, staff: User, coordinator: User
) -> None:
    refused(
        db, "venue_bookings_hold_consistent", event=event, venue=venue, staff=staff,
        requested_by_user_id=coordinator.id,
    )


def test_tc_us25_03_a_hold_lapses_at_its_expiry_not_before(db: Session, event: Event, venue: Venue, staff: User) -> None:
    refused(
        db, "venue_bookings_expired_consistent", event=event, venue=venue, staff=staff,
        status=VenueBookingStatus.EXPIRED, expired_at=NOW + timedelta(days=2),
    )


def test_tc_us25_04_a_hold_is_never_the_primary_venue(db: Session, event: Event, venue: Venue, staff: User) -> None:
    refused(db, "venue_bookings_hold_not_primary", event=event, venue=venue, staff=staff, is_primary=True)


def test_tc_us25_04_a_hold_has_no_decision(db: Session, event: Event, venue: Venue, staff: User) -> None:
    refused(
        db, "venue_bookings_decided_consistent", event=event, venue=venue, staff=staff, decided_at=NOW,
        decided_by_user_id=make_user(db, UserRole.VENUE_STAFF).id,
    )


def test_tc_us25_05_a_confirmed_hold_keeps_its_expiry_and_who_held_it(
    db: Session, event: Event, venue: Venue, staff: User, coordinator: User
) -> None:
    booking = hold(db, event, venue, staff)

    booking.status = VenueBookingStatus.REQUESTED
    booking.requested_by_user_id = coordinator.id
    db.flush()
    db.refresh(booking)

    assert (booking.hold_expires_at, booking.held_by_user_id) == (NOW + timedelta(days=3), staff.id)


def test_tc_us25_06_the_availability_check_reports_a_hold_as_the_guard_refuses_it(
    db: Session, event: Event, venue: Venue, staff: User
) -> None:
    """The app's copy of the guard's rule (BLOCKING_STATUSES), so a refused request names the hold (US13 AC 4)."""
    held = hold(db, event, venue, staff)

    evaluation = evaluate_window(db, venue, START + timedelta(minutes=30), START + timedelta(hours=1))
    expired = hold(db, event, make_venue(db), staff, status=VenueBookingStatus.EXPIRED, expired_at=NOW + timedelta(days=3))
    free = evaluate_window(db, db.get(Venue, expired.venue_id), START, START + timedelta(hours=1))

    assert [conflict.reference for conflict in evaluation.conflicts] == [held.reference]
    assert free.conflicts == []
