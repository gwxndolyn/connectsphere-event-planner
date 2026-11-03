"""US23a (SCRUM-90) PR 1: a venue block's reason and who recorded it, and the "Needs rearrangement" marker on the
bookings and holds a block overlaps. See docs/testing/US23a-venue-unavailability.md."""

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.seed import VENUE_BLOCKS
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBlock, VenueBlockReason, VenueBookingStatus
from tests.conftest import assert_one_head_including
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_block, make_venue_booking

REVISION = "20261116_1200_us23a_blocks"
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


@pytest.fixture
def block(db: Session, venue: Venue, staff: User) -> VenueBlock:
    return make_venue_block(db, venue, START, START + timedelta(hours=4), created_by_user_id=staff.id)


def test_tc_us23a_01_migrations_have_one_head() -> None:
    assert_one_head_including(REVISION)


def test_tc_us23a_01_a_block_has_one_of_the_five_reasons(db: Session, venue: Venue, staff: User) -> None:
    for reason in VenueBlockReason:
        make_venue_block(db, venue, START, START + timedelta(hours=1), reason=reason, created_by_user_id=staff.id)

    assert [reason.value for reason in VenueBlockReason] == [
        "maintenance", "equipment_failure", "renovation", "safety", "other",
    ]
    with pytest.raises(IntegrityError, match="venue_blocks_reason_known"):
        make_venue_block(db, venue, START, START + timedelta(hours=1), reason="flooding")
    db.rollback()


def test_tc_us23a_01_a_block_needs_a_reason(db: Session, venue: Venue) -> None:
    with pytest.raises(IntegrityError, match='null value in column "reason"'):
        make_venue_block(db, venue, START, START + timedelta(hours=1), reason=None)
    db.rollback()


def test_tc_us23a_01_the_seeded_block_is_for_maintenance() -> None:
    assert [spec.reason for spec in VENUE_BLOCKS] == [VenueBlockReason.MAINTENANCE]


@pytest.mark.parametrize("hours", [0, -1], ids=["end at the start", "end before the start"])
def test_tc_us23a_02_a_block_ends_after_it_starts(db: Session, venue: Venue, hours: int) -> None:
    with pytest.raises(IntegrityError, match="venue_blocks_window_valid"):
        make_venue_block(db, venue, START, START + timedelta(hours=hours))
    db.rollback()


@pytest.mark.parametrize(
    "status", [VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED], ids=["requested", "approved"]
)
def test_tc_us23a_03_a_marked_booking_keeps_its_status_and_window(
    db: Session, event: Event, venue: Venue, coordinator: User, block: VenueBlock, status: VenueBookingStatus
) -> None:
    """D113: "Needs rearrangement" names the block and leaves the booking as it was, still holding its window."""
    booking = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=START, status=status,
        rearrangement_block_id=block.id, rearrangement_flagged_at=NOW,
        **({"decided_at": NOW} if status == VenueBookingStatus.APPROVED else {}),
    )
    db.refresh(booking)

    assert (booking.status, booking.rearrangement_block_id) == (status, block.id)
    with pytest.raises(IntegrityError, match="venue_bookings_no_overlap"):
        make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START, is_primary=False)
    db.rollback()


def test_tc_us23a_03_a_hold_can_be_marked(
    db: Session, event: Event, venue: Venue, staff: User, block: VenueBlock
) -> None:
    hold = make_venue_booking(
        db, event=event, venue=venue, user=staff, starts_at=START, status=VenueBookingStatus.HELD, is_primary=False,
        hold_expires_at=NOW + timedelta(days=3), held_by_user_id=staff.id,
        rearrangement_block_id=block.id, rearrangement_flagged_at=NOW,
    )

    assert hold.rearrangement_block_id == block.id


@pytest.mark.parametrize(
    "marker",
    [{"rearrangement_block_id": "block"}, {"rearrangement_flagged_at": NOW}],
    ids=["block without a time", "time without a block"],
)
def test_tc_us23a_03_the_marker_is_whole(
    db: Session, event: Event, venue: Venue, coordinator: User, block: VenueBlock, marker: dict[str, object]
) -> None:
    fields = {key: block.id if value == "block" else value for key, value in marker.items()}
    with pytest.raises(IntegrityError, match="venue_bookings_rearrangement_consistent"):
        make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START, **fields)
    db.rollback()


def test_tc_us23a_03_a_blocks_bookings_are_found_by_an_index(db: Session) -> None:
    definition = db.scalar(
        text(
            "select indexdef from pg_indexes where tablename = 'venue_bookings' "
            "and indexname = 'ix_venue_bookings_rearrangement_block_id'"
        )
    )
    assert definition is not None
    assert "(rearrangement_block_id)" in definition and "WHERE (rearrangement_block_id IS NOT NULL)" in definition
