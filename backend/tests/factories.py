import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.event.models import DeliveryMode, Event, EventRegistrationField, EventStatus
from app.registration.models import Registration, RegistrationStatus
from app.user.models import Attendee, User, UserRole
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus, occupied_window

SGT = timezone(timedelta(hours=8))
# Frozen "now" for every API test (spec §8: freeze time).
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=SGT)


def make_attendee(db: Session) -> Attendee:
    attendee_id = uuid.uuid4()
    email = f"{uuid.uuid4().hex[:8]}@smu.edu.sg"
    user = User(id=attendee_id, email=email, role=UserRole.ATTENDEE)
    attendee = Attendee(id=attendee_id, email=email)
    db.add(user)
    db.flush()
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
    # True, unlike the column's default: like registration_enabled, the factory builds an event
    # that takes registrations and offers a waitlist when full. Pass False to test US6a AC 2.
    waitlist_enabled: bool = True,
    # US10a (SCRUM-13): the coordinator assigned to the event; None leaves it unassigned.
    coordinator_id: uuid.UUID | None = None,
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
        waitlist_enabled=waitlist_enabled,
        coordinator_id=coordinator_id,
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


def make_user(db: Session, role: UserRole, *, active: bool = True) -> User:
    user = User(email=f"{uuid.uuid4().hex}@smu.edu.sg", role=role, is_active=active)
    db.add(user)
    db.flush()
    return user


def make_venue(db: Session, **overrides: object) -> Venue:
    fields: dict[str, object] = {
        "name": "Stored Room",
        "location": "Stored Building",
        "capacity": 40,
        "facilities": ["projector"],
        "accessibility_features": [],
        "room_layouts": ["theatre"],
        "opens_at": time(8, 0),
        "closes_at": time(20, 0),
        "setup_minutes": 30,
        "turnaround_minutes": 15,
    }
    venue = Venue(**(fields | overrides))
    db.add(venue)
    db.flush()
    return venue


def make_venue_booking(
    db: Session,
    *,
    event: Event,
    venue: Venue,
    user: User,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    status: VenueBookingStatus = VenueBookingStatus.REQUESTED,
    **overrides: object,
) -> VenueBooking:
    starts_at = starts_at or NOW + timedelta(days=7)
    ends_at = ends_at or starts_at + timedelta(hours=2)
    # US13: the window the venue's buffers make it occupy; a test can override either end.
    occupied_starts_at, occupied_ends_at = occupied_window(venue, starts_at, ends_at)
    fields: dict[str, object] = {
        "event_id": event.id,
        "venue_id": venue.id,
        "requested_by_user_id": user.id,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "occupied_starts_at": occupied_starts_at,
        "occupied_ends_at": occupied_ends_at,
        "expected_attendees": 30,
        "room_layout": "theatre",
        "status": status,
        # venue_bookings_withdrawn_consistent: a withdrawn booking always carries its timestamp.
        "withdrawn_at": NOW if status == VenueBookingStatus.WITHDRAWN else None,
        # venue_bookings_decided_consistent: an approved or rejected booking carries its decision time.
        "decided_at": NOW if status in (VenueBookingStatus.APPROVED, VenueBookingStatus.REJECTED) else None,
    }
    booking = VenueBooking(**(fields | overrides))
    db.add(booking)
    db.flush()
    return booking

def make_venue_block(db: Session, venue: Venue, starts_at: datetime, ends_at: datetime, note: str | None = None) -> VenueBlock:
    """A time the venue is out of use with no event behind it (US2's venue_blocks)."""
    block = VenueBlock(venue_id=venue.id, starts_at=starts_at, ends_at=ends_at, note=note)
    db.add(block)
    db.flush()
    return block
