"""US22 venue booking request, PR 3 (SCRUM-113, story SCRUM-89): the seeded event the booking
screens and e2e/tests/venue-booking.spec.ts book. See docs/testing/US22-venue-booking.md."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.seed import BOOKABLE_EVENT, seed, seed_id
from app.user.models import User
from app.venue.models import VenueBooking
from tests.factories import NOW


def test_tc_us22_19_seed_has_a_bookable_approved_event(db: Session) -> None:
    """TC-US22-19 to 21 need an Approved event with nothing booked yet. Nothing approves requests
    until US17, so the seed puts it straight into approved (D24); any coordinator may book it (D20)."""
    seed(db, now=NOW)

    event = db.get(Event, seed_id("event", BOOKABLE_EVENT.slug))
    assert event is not None
    assert event.name == "Venue Booking Demo"
    assert event.status == EventStatus.APPROVED
    assert event.expected_attendees == 40
    # The organiser owns it: events have no assigned coordinator until US10a.
    assert db.get(User, event.created_by_user_id).email == "event.organiser@smu.edu.sg"
    assert db.scalar(select(func.count()).where(VenueBooking.event_id == event.id)) == 0


def test_tc_us22_19_reseeding_adds_no_second_event(db: Session) -> None:
    seed(db, now=NOW)
    seed(db, now=NOW)

    assert db.scalar(select(func.count()).select_from(Event).where(Event.name == "Venue Booking Demo")) == 1
