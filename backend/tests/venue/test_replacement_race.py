"""US23b (SCRUM-91): the lock orders Chloe's #135 review found could deadlock, each run with two real sessions, as
TC-US9-24 and TC-US23A-21 do. See docs/testing/US23b-replacement-venue.md (TC-US23B-21, 22)."""

import threading
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import timedelta

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.block_service import VenueBlockService, block_service
from app.venue.booking_service import VenueBookingService, booking_service
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus
from app.venue.schemas import VenueBlockWrite
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_block, make_venue_booking

START = NOW + timedelta(days=7)
END = START + timedelta(hours=2)


@dataclass
class Committed:
    event_id: uuid.UUID
    original_id: uuid.UUID
    venue_id: uuid.UUID
    block_id: uuid.UUID
    coordinator_id: uuid.UUID
    staff_ids: list[uuid.UUID]
    venue_ids: list[uuid.UUID] = field(default_factory=list)


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    """An approved primary booking that a period marks, committed for real so two sessions both see it."""
    with Session(engine) as setup:
        coordinator = make_user(setup, UserRole.COORDINATOR)
        staff = [make_user(setup, UserRole.VENUE_STAFF) for _ in range(2)]
        event = make_event(setup, status=EventStatus.PLANNING, coordinator_id=coordinator.id, start_at=START, end_at=END)
        venue = make_venue(setup)
        original = make_venue_booking(
            setup, event=event, venue=venue, user=coordinator, starts_at=START, ends_at=END,
            status=VenueBookingStatus.APPROVED, decided_by_user_id=staff[0].id, is_primary=True,
        )
        block = make_venue_block(setup, venue=venue, starts_at=START, ends_at=END)
        original.rearrangement_block_id = block.id
        original.rearrangement_flagged_at = NOW
        setup.commit()
        rows = Committed(event.id, original.id, venue.id, block.id, coordinator.id, [user.id for user in staff], [venue.id])
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(
                delete(VenueBooking).where(VenueBooking.event_id == rows.event_id, VenueBooking.replaces_booking_id.is_not(None))
            )
            cleanup.execute(delete(VenueBooking).where(VenueBooking.event_id == rows.event_id))
            cleanup.execute(delete(VenueBlock).where(VenueBlock.venue_id.in_(rows.venue_ids)))
            cleanup.execute(delete(Event).where(Event.id == rows.event_id))
            cleanup.execute(delete(Venue).where(Venue.id.in_(rows.venue_ids)))
            cleanup.execute(delete(User).where(User.id.in_([rows.coordinator_id, *rows.staff_ids])))
            cleanup.commit()


def _run(*targets) -> None:
    threads = [threading.Thread(target=target) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)


def test_tc_us23b_21_approving_a_replacement_and_a_period_at_once_both_land_in_turn(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Venue staff approve a replacement: they hold the event (FOR SHARE) and the replacement's venue, then pause.
    Another Venue staff member records a period at the original's venue, which takes its bookings (the original),
    then their events FOR UPDATE. Taking the original only after the event deadlocked: each held what the other
    wanted. Locked with the replacement first, the period waits for the approval instead."""
    with Session(engine) as setup:
        other = make_venue(setup, name="Hall B")
        replacement = make_venue_booking(
            setup, event=setup.get(Event, committed.event_id), venue=other,
            user=setup.get(User, committed.coordinator_id), starts_at=START, ends_at=END,
        )
        replacement.replaces_booking_id = committed.original_id
        setup.commit()
        committed.venue_ids.append(other.id)
        replacement_id = replacement.id

    holds_event = threading.Event()
    original = VenueBookingService._replace_original

    def pause_then_replace(self, db: Session, *args, **kwargs):
        holds_event.set()
        time.sleep(1)
        return original(self, db, *args, **kwargs)

    monkeypatch.setattr(VenueBookingService, "_replace_original", pause_then_replace)
    errors: list[BaseException] = []
    approver_id, marker_id = committed.staff_ids

    def approve() -> None:
        with Session(engine) as db:
            try:
                booking_service.approve(db, db.get(User, approver_id), replacement_id, NOW, FakeNotifier())
            except BaseException as error:  # noqa: BLE001 — reported by the assertion below
                errors.append(error)

    def mark() -> None:
        holds_event.wait(timeout=10)
        with Session(engine) as db:
            try:
                body = VenueBlockWrite(starts_at=START, ends_at=END, reason="safety")
                block_service.create(db, db.get(User, marker_id), committed.venue_id, body, NOW, FakeNotifier())
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

    _run(approve, mark)

    assert errors == []
    with Session(engine) as check:
        assert check.get(VenueBooking, committed.original_id).status == VenueBookingStatus.REPLACED
        approved = check.get(VenueBooking, replacement_id)
        assert (approved.status, approved.is_primary) == (VenueBookingStatus.APPROVED, True)
        assert len(check.scalars(select(VenueBlock).where(VenueBlock.venue_id == committed.venue_id)).all()) == 2


def test_tc_us23b_22_ending_a_period_early_and_recording_another_at_once_both_land_in_turn(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Venue staff record a second period over the marked booking: they hold it and its event, then pause before
    the venue. Another ends the first period early. Taking the venue before the bookings deadlocked with that; taking
    the bookings first, the end waits, then finds the second period still over the booking and moves its marker."""
    in_create = threading.Event()
    lock_events = VenueBlockService._lock_events
    calls = {"count": 0}

    def lock_then_pause(self, db: Session, bookings):
        locked = lock_events(self, db, bookings)
        calls["count"] += 1
        if calls["count"] == 1:
            in_create.set()
            time.sleep(1)
        return locked

    monkeypatch.setattr(VenueBlockService, "_lock_events", lock_then_pause)
    errors: list[BaseException] = []
    marker_id, ender_id = committed.staff_ids
    created: list[uuid.UUID] = []

    def mark() -> None:
        with Session(engine) as db:
            try:
                body = VenueBlockWrite(starts_at=START, ends_at=END, reason="safety")
                created.append(block_service.create(db, db.get(User, marker_id), committed.venue_id, body, NOW, FakeNotifier()).id)
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

    def end() -> None:
        in_create.wait(timeout=10)
        with Session(engine) as db:
            try:
                block_service.end_early(db, db.get(User, ender_id), committed.venue_id, committed.block_id, NOW, FakeNotifier())
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

    _run(mark, end)

    assert errors == []
    with Session(engine) as check:
        assert check.get(VenueBlock, committed.block_id).ended_early_at is not None
        assert check.get(VenueBooking, committed.original_id).rearrangement_block_id == created[0]
