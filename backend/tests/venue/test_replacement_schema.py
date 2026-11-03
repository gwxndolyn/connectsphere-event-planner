"""US23b (SCRUM-91) PR 1: a booking's replacement and its Replaced status, a request to restore a booking that needs
rearrangement, and a venue block ended early. See docs/testing/US23b-replacement-venue.md."""

from datetime import timedelta

import pytest
from sqlalchemy import func, literal, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus
from tests.conftest import assert_one_head_including
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_block, make_venue_booking

REVISION = "20261117_1200_us23b_replacement"
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
    return make_venue_block(db, venue, START - timedelta(hours=2), START + timedelta(hours=6), created_by_user_id=staff.id)


@pytest.fixture
def original(db: Session, event: Event, venue: Venue, coordinator: User, block: VenueBlock) -> VenueBooking:
    """An approved primary booking a block marked as needing rearrangement (US23a)."""
    return make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=START, status=VenueBookingStatus.APPROVED,
        is_primary=True, rearrangement_block_id=block.id, rearrangement_flagged_at=NOW,
    )


def _replacement(db: Session, original: VenueBooking, coordinator: User, **fields: object) -> VenueBooking:
    event = db.get(Event, original.event_id)
    return make_venue_booking(
        db, event=event, venue=make_venue(db), user=coordinator, starts_at=START, is_primary=False,
        replaces_booking_id=original.id, **fields,
    )


def test_tc_us23b_01_migrations_have_one_head() -> None:
    assert_one_head_including(REVISION)


def test_tc_us23b_01_a_replaced_booking_frees_its_window_and_keeps_its_details(
    db: Session, event: Event, venue: Venue, coordinator: User, block: VenueBlock, original: VenueBooking
) -> None:
    """AC 4 (D116): Replaced is a status with its time; like withdrawn, it no longer holds the venue, and the
    booking keeps its reference, window, decision and the block that marked it."""
    reference, window = original.reference, (original.starts_at, original.ends_at)
    original.status = VenueBookingStatus.REPLACED
    original.replaced_at = NOW
    db.flush()
    db.refresh(original)

    assert (original.status, original.replaced_at) == (VenueBookingStatus.REPLACED, NOW)
    assert (original.reference, (original.starts_at, original.ends_at)) == (reference, window)
    assert (original.decided_at, original.rearrangement_block_id) == (NOW, block.id)
    freed = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START, is_primary=False)
    assert freed.venue_id == venue.id


@pytest.mark.parametrize(
    ("status", "replaced_at"),
    [(VenueBookingStatus.REPLACED, None), (VenueBookingStatus.APPROVED, NOW)],
    ids=["replaced without a time", "time without replaced"],
)
def test_tc_us23b_01_replaced_and_its_time_go_together(
    db: Session, event: Event, venue: Venue, coordinator: User, status: VenueBookingStatus, replaced_at: object
) -> None:
    with pytest.raises(IntegrityError, match="venue_bookings_replaced_consistent"):
        make_venue_booking(
            db, event=event, venue=venue, user=coordinator, starts_at=START, status=status, replaced_at=replaced_at,
            decided_at=NOW,
        )
    db.rollback()


def test_tc_us23b_02_a_replacement_names_the_booking_it_replaces(
    db: Session, original: VenueBooking, coordinator: User
) -> None:
    replacement = _replacement(db, original, coordinator)

    assert replacement.replaces_booking_id == original.id
    assert db.scalars(select(VenueBooking.id).where(VenueBooking.replaces_booking_id == original.id)).all() == [
        replacement.id
    ]


def test_tc_us23b_02_a_booking_doesnt_replace_itself(db: Session, original: VenueBooking) -> None:
    original.replaces_booking_id = original.id
    with pytest.raises(IntegrityError, match="venue_bookings_replaces_another"):
        db.flush()
    db.rollback()


@pytest.mark.parametrize(
    "first", [VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED], ids=["requested", "approved"]
)
def test_tc_us23b_02_one_live_replacement_at_a_time(
    db: Session, original: VenueBooking, coordinator: User, first: VenueBookingStatus
) -> None:
    """D116: a second replacement waits until the first is rejected or withdrawn."""
    _replacement(db, original, coordinator, status=first)

    with pytest.raises(IntegrityError, match="venue_bookings_one_live_replacement"):
        _replacement(db, original, coordinator)
    db.rollback()


def test_tc_us23b_02_a_held_replacement_counts_as_live(
    db: Session, original: VenueBooking, coordinator: User, staff: User
) -> None:
    """Matt's #134 review: a hold holds a window too, so one couldn't sit beside a live replacement."""
    _replacement(
        db, original, staff, status=VenueBookingStatus.HELD, hold_expires_at=NOW + timedelta(days=2),
        held_by_user_id=staff.id,
    )

    with pytest.raises(IntegrityError, match="venue_bookings_one_live_replacement"):
        _replacement(db, original, coordinator)
    db.rollback()


@pytest.mark.parametrize(
    "first", [VenueBookingStatus.REJECTED, VenueBookingStatus.WITHDRAWN], ids=["rejected", "withdrawn"]
)
def test_tc_us23b_02_a_closed_replacement_makes_way_for_another(
    db: Session, original: VenueBooking, coordinator: User, first: VenueBookingStatus
) -> None:
    _replacement(db, original, coordinator, status=first)

    assert _replacement(db, original, coordinator).replaces_booking_id == original.id


def test_tc_us23b_03_a_marked_booking_can_be_asked_to_be_restored(
    db: Session, original: VenueBooking, coordinator: User
) -> None:
    """AC 5 (D117): who asked and when, until Venue staff decide."""
    original.restore_requested_at = NOW
    original.restore_requested_by_user_id = coordinator.id
    db.flush()
    db.refresh(original)

    assert (original.restore_requested_at, original.restore_requested_by_user_id) == (NOW, coordinator.id)


@pytest.mark.parametrize(
    "fields",
    [
        {"restore_requested_at": NOW},
        {"restore_requested_by_user_id": "coordinator"},
        {"restore_requested_at": NOW, "restore_requested_by_user_id": "coordinator", "unmarked": True},
    ],
    ids=["time without who", "who without a time", "booking not marked"],
)
def test_tc_us23b_03_a_restore_request_is_whole_and_only_on_a_marked_booking(
    db: Session, original: VenueBooking, coordinator: User, fields: dict[str, object]
) -> None:
    if fields.pop("unmarked", False):
        original.rearrangement_block_id = None
        original.rearrangement_flagged_at = None
    for key, value in fields.items():
        setattr(original, key, coordinator.id if value == "coordinator" else value)
    with pytest.raises(IntegrityError, match="venue_bookings_restore_consistent"):
        db.flush()
    db.rollback()


def test_tc_us23b_03_a_declined_restore_keeps_who_when_and_why(db: Session, original: VenueBooking, staff: User) -> None:
    """Matt's #134 review: the coordinator sees Venue staff's last decline until they ask again."""
    original.restore_declined_at = NOW
    original.restore_declined_by_user_id = staff.id
    original.restore_decline_reason = "Still testing the aircon"
    db.flush()
    db.refresh(original)

    assert (original.restore_declined_by_user_id, original.restore_decline_reason) == (staff.id, "Still testing the aircon")


@pytest.mark.parametrize(
    "fields",
    [
        {"restore_declined_at": NOW},
        {"restore_declined_by_user_id": "staff"},
        {"restore_decline_reason": "No"},
    ],
    ids=["time without who", "who without a time", "reason without a decline"],
)
def test_tc_us23b_03_a_decline_is_whole(
    db: Session, original: VenueBooking, staff: User, fields: dict[str, object]
) -> None:
    for key, value in fields.items():
        setattr(original, key, staff.id if value == "staff" else value)
    with pytest.raises(IntegrityError, match="venue_bookings_restore_decline_consistent"):
        db.flush()
    db.rollback()


def test_tc_us23b_04_a_block_ended_early_keeps_its_scheduled_end(db: Session, block: VenueBlock, staff: User) -> None:
    """AC 5 (D117): ends_at moves to when it was ended; scheduled_ends_at keeps the end it had."""
    scheduled = block.ends_at
    block.scheduled_ends_at = scheduled
    block.ends_at = START
    block.ended_early_at = START
    block.ended_early_by_user_id = staff.id
    db.flush()
    db.refresh(block)

    assert (block.ends_at, block.scheduled_ends_at, block.ended_early_by_user_id) == (START, scheduled, staff.id)


def test_tc_us23b_04_a_block_ended_before_it_began_overlaps_nothing(
    db: Session, venue: Venue, staff: User
) -> None:
    """An empty block is allowed only once ended early, and no window overlaps it."""
    block = make_venue_block(
        db, venue, START, START, scheduled_ends_at=START + timedelta(hours=4), ended_early_at=NOW,
        ended_early_by_user_id=staff.id,
    )
    overlapping = db.scalar(
        select(func.count()).where(
            VenueBlock.id == block.id,
            func.tstzrange(VenueBlock.starts_at, VenueBlock.ends_at, literal("[)")).op("&&")(
                func.tstzrange(START - timedelta(hours=1), START + timedelta(hours=5), literal("[)"))
            ),
        )
    )

    assert overlapping == 0
    with pytest.raises(IntegrityError, match="venue_blocks_window_valid"):
        make_venue_block(db, venue, START, START)
    db.rollback()


@pytest.mark.parametrize(
    "fields",
    [
        {"ended_early_at": NOW, "scheduled_ends_at": "later"},
        {"ended_early_at": NOW, "ended_early_by_user_id": "staff"},
        {"scheduled_ends_at": "later", "ended_early_by_user_id": "staff"},
        {"ended_early_at": NOW, "ended_early_by_user_id": "staff", "scheduled_ends_at": "earlier"},
    ],
    ids=["without who", "without the scheduled end", "without when", "scheduled end not later"],
)
def test_tc_us23b_04_ending_early_is_recorded_whole(
    db: Session, venue: Venue, staff: User, fields: dict[str, object]
) -> None:
    ends = START + timedelta(hours=2)
    values = {
        "later": ends + timedelta(hours=2),
        "earlier": ends - timedelta(hours=1),
        "staff": staff.id,
    }
    resolved = {key: values.get(value, value) if isinstance(value, str) else value for key, value in fields.items()}
    with pytest.raises(IntegrityError, match="venue_blocks_ended_early_consistent"):
        make_venue_block(db, venue, START, ends, **resolved)
    db.rollback()


def test_tc_us23b_04_the_status_type_has_replaced(db: Session) -> None:
    values = db.scalars(text("select unnest(enum_range(null::venue_booking_status))::text")).all()

    assert values == ["requested", "approved", "rejected", "withdrawn", "held", "expired", "replaced"]
    assert [status.value for status in VenueBookingStatus] == values
