import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.event.models import DeliveryMode, Event, EventStatus
from app.registration.models import Registration, RegistrationStatus
from app.user.models import Attendee

SGT = timezone(timedelta(hours=8))
# Frozen "now" for every API test (spec §8: freeze time).
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=SGT)


def make_attendee(db: Session) -> Attendee:
    attendee = Attendee(email=f"{uuid.uuid4().hex[:8]}@smu.edu.sg")
    db.add(attendee)
    db.flush()
    return attendee


def make_event(db: Session, *, start_at: datetime | None = None, capacity: int = 40) -> Event:
    start_at = start_at or NOW + timedelta(days=1)
    event = Event(
        name="Tech Talk: Agile at Scale",
        status=EventStatus.CONFIRMED,
        registration_enabled=True,
        registration_opens_at=NOW - timedelta(days=7),
        registration_closes_at=start_at,
        start_at=start_at,
        end_at=start_at + timedelta(hours=2),
        capacity=capacity,
        delivery_mode=DeliveryMode.IN_PERSON,
        venue_name="SMU SCIS Building",
        room_number="Seminar Room 2-1",
    )
    db.add(event)
    db.flush()
    return event


def make_registration(
    db: Session,
    event: Event,
    attendee: Attendee,
    *,
    status: RegistrationStatus = RegistrationStatus.CONFIRMED,
    waitlist_joined_at: datetime | None = None,
    offer_expires_at: datetime | None = None,
) -> Registration:
    registration = Registration(
        event_id=event.id,
        attendee_id=attendee.id,
        attendee_email=attendee.email,
        status=status,
        waitlist_joined_at=waitlist_joined_at,
        offer_expires_at=offer_expires_at,
    )
    db.add(registration)
    db.flush()
    return registration
