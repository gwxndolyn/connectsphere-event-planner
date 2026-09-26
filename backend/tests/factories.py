import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.event.models import DeliveryMode, Event, EventRegistrationField, EventStatus
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


def make_event(
    db: Session,
    *,
    name: str = "Tech Talk: Agile at Scale",
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    capacity: int = 40,
    status: EventStatus = EventStatus.CONFIRMED,
    registration_enabled: bool = True,
    registration_opens_at: datetime | None = None,
    registration_closes_at: datetime | None = None,
    delivery_mode: DeliveryMode = DeliveryMode.IN_PERSON,
    venue_name: str | None = "SMU SCIS Building",
    room_number: str | None = "Seminar Room 2-1",
    join_link: str | None = None,
) -> Event:
    start_at = start_at or NOW + timedelta(days=1)
    registration_opens_at = (
        NOW - timedelta(days=7) if registration_opens_at is None else registration_opens_at
    )
    registration_closes_at = start_at if registration_closes_at is None else registration_closes_at
    event = Event(
        name=name,
        status=status,
        registration_enabled=registration_enabled,
        registration_opens_at=registration_opens_at,
        registration_closes_at=registration_closes_at,
        start_at=start_at,
        end_at=end_at or start_at + timedelta(hours=2),
        capacity=capacity,
        delivery_mode=delivery_mode,
        venue_name=venue_name,
        room_number=room_number,
        join_link=join_link,
    )
    db.add(event)
    db.flush()
    return event


def make_registration_field(
    db: Session,
    event: Event,
    *,
    field_key: str = "dietary",
    label: str = "Dietary requirements",
    field_type: str = "text",
    required: bool = True,
) -> EventRegistrationField:
    field = EventRegistrationField(
        event_id=event.id,
        field_key=field_key,
        label=label,
        field_type=field_type,
        required=required,
    )
    db.add(field)
    db.flush()
    return field


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
