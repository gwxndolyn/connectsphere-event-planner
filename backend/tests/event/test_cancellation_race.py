"""US9 (SCRUM-12): a cancel and a Venue staff approval of the same event's booking at the same moment.
See docs/testing/US9-cancel-event.md (TC-US9-24)."""

import threading
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.event.cancellation_schemas import CancellationWrite
from app.event.cancellation_service import cancellation_service
from app.event.models import Event, EventCancellation, EventStatus
from app.user.models import User, UserRole
from app.venue.booking_service import VenueBookingService, booking_service
from app.venue.models import Venue, VenueBooking, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking


@dataclass
class Committed:
    event_id: uuid.UUID
    booking_id: uuid.UUID
    venue_id: uuid.UUID
    coordinator_id: uuid.UUID
    staff_id: uuid.UUID


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    """Committed for real, so two sessions on separate connections both see them (as TC-US7-19)."""
    with Session(engine) as setup:
        coordinator = make_user(setup, UserRole.COORDINATOR)
        staff = make_user(setup, UserRole.VENUE_STAFF)
        event = make_event(setup, status=EventStatus.PLANNING, coordinator_id=coordinator.id)
        venue = make_venue(setup)
        booking = make_venue_booking(setup, event=event, venue=venue, user=coordinator)
        setup.commit()
        rows = Committed(event.id, booking.id, venue.id, coordinator.id, staff.id)
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(EventCancellation).where(EventCancellation.event_id == rows.event_id))
            cleanup.execute(delete(VenueBooking).where(VenueBooking.event_id == rows.event_id))
            cleanup.execute(delete(Event).where(Event.id == rows.event_id))
            cleanup.execute(delete(Venue).where(Venue.id == rows.venue_id))
            cleanup.execute(delete(User).where(User.id.in_([rows.coordinator_id, rows.staff_id])))
            cleanup.commit()


def test_tc_us9_24_a_cancel_and_an_approval_at_once_both_land_in_turn(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Venue staff approve: they lock the booking, then (after a pause) the event. The coordinator cancels in the
    pause. The cancel takes the event's bookings before the event, the approval's order, so it waits for the
    approval to commit and then withdraws the now-approved booking. Taking the event first deadlocked: each held
    what the other wanted, and Postgres aborted one with a 500."""
    holds_booking = threading.Event()
    original = VenueBookingService._lock_pending

    def lock_then_pause(self, db: Session, booking_id: uuid.UUID, staff: User) -> VenueBooking:
        booking = original(self, db, booking_id, staff)
        holds_booking.set()
        time.sleep(1)
        return booking

    monkeypatch.setattr(VenueBookingService, "_lock_pending", lock_then_pause)
    errors: list[BaseException] = []

    def approve() -> None:
        with Session(engine) as db:
            try:
                staff = db.get(User, committed.staff_id)
                booking_service.approve(db, staff, committed.booking_id, NOW, FakeNotifier())
            except BaseException as error:  # noqa: BLE001 — reported by the assertion below
                errors.append(error)

    def cancel() -> None:
        holds_booking.wait(timeout=10)
        with Session(engine) as db:
            try:
                coordinator = db.get(User, committed.coordinator_id)
                cancellation_service.cancel(
                    db, coordinator, committed.event_id, CancellationWrite(reason="Clash"), NOW, FakeNotifier()
                )
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

    threads = [threading.Thread(target=approve), threading.Thread(target=cancel)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    with Session(engine) as check:
        booking = check.get(VenueBooking, committed.booking_id)
        assert (booking.status, booking.decided_at is not None) == (VenueBookingStatus.WITHDRAWN, True)
        assert check.get(Event, committed.event_id).status == EventStatus.CANCELLED
