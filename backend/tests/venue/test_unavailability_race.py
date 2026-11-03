"""US23a (SCRUM-90): Venue staff mark a venue unavailable while another Venue staff member approves a booking there.
See docs/testing/US23a-venue-unavailability.md (TC-US23A-21), from Matt's #133 review."""

import threading
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import timedelta

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.block_service import block_service
from app.venue.booking_service import VenueBookingService, booking_service
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus
from app.venue.schemas import VenueBlockWrite
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

START = NOW + timedelta(days=7)
END = START + timedelta(hours=2)


@dataclass
class Committed:
    event_id: uuid.UUID
    booking_id: uuid.UUID
    venue_id: uuid.UUID
    user_ids: list[uuid.UUID]


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    """Committed for real, so two sessions on separate connections both see them (as TC-US9-24)."""
    with Session(engine) as setup:
        coordinator = make_user(setup, UserRole.COORDINATOR)
        approver = make_user(setup, UserRole.VENUE_STAFF)
        marker = make_user(setup, UserRole.VENUE_STAFF)
        event = make_event(setup, status=EventStatus.PLANNING, coordinator_id=coordinator.id, start_at=START, end_at=END)
        venue = make_venue(setup)
        booking = make_venue_booking(setup, event=event, venue=venue, user=coordinator, starts_at=START, ends_at=END)
        setup.commit()
        rows = Committed(event.id, booking.id, venue.id, [coordinator.id, approver.id, marker.id])
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(VenueBooking).where(VenueBooking.event_id == rows.event_id))
            cleanup.execute(delete(VenueBlock).where(VenueBlock.venue_id == rows.venue_id))
            cleanup.execute(delete(Event).where(Event.id == rows.event_id))
            cleanup.execute(delete(Venue).where(Venue.id == rows.venue_id))
            cleanup.execute(delete(User).where(User.id.in_(rows.user_ids)))
            cleanup.commit()


def test_tc_us23a_21_an_approval_and_a_period_at_once_both_land_in_turn(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Venue staff approve: they lock the booking, then (after a pause) the event and the venue. Another Venue staff
    member records a period over it in the pause. The period takes the bookings before the venue, the approval's
    order, so it waits for the approval to commit and then marks the now-approved booking. Taking the venue first
    could deadlock: each would hold what the other wanted, and Postgres would abort one with a 500."""
    holds_booking = threading.Event()
    original = VenueBookingService._lock_pending

    def lock_then_pause(self, db: Session, booking_id: uuid.UUID, staff: User) -> VenueBooking:
        booking = original(self, db, booking_id, staff)
        holds_booking.set()
        time.sleep(1)
        return booking

    monkeypatch.setattr(VenueBookingService, "_lock_pending", lock_then_pause)
    errors: list[BaseException] = []
    _, approver_id, marker_id = committed.user_ids

    def approve() -> None:
        with Session(engine) as db:
            try:
                booking_service.approve(db, db.get(User, approver_id), committed.booking_id, NOW, FakeNotifier())
            except BaseException as error:  # noqa: BLE001 — reported by the assertion below
                errors.append(error)

    def mark() -> None:
        holds_booking.wait(timeout=10)
        with Session(engine) as db:
            try:
                body = VenueBlockWrite(starts_at=START, ends_at=END, reason="maintenance")
                block_service.create(db, db.get(User, marker_id), committed.venue_id, body, NOW, FakeNotifier())
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

    threads = [threading.Thread(target=approve), threading.Thread(target=mark)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    with Session(engine) as check:
        booking = check.get(VenueBooking, committed.booking_id)
        assert booking.status == VenueBookingStatus.APPROVED
        assert booking.rearrangement_block_id is not None
