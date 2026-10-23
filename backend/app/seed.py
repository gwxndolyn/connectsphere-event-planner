"""Sprint 1 seed data (SCRUM-23).

Sprint 1 can't create a confirmed event through the product — event creation is Epic 1 —
so the states the registration and withdrawal flows need are seeded here instead.

Idempotent: every row's UUID is derived from a slug, so re-running updates the same rows
rather than inserting duplicates.

    python -m app.seed          # against a local database
    python -m app.seed --yes    # required when DATABASE_URL is not localhost
"""

import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.event.models import DeliveryMode, Event, EventStatus
from app.registration.models import ACTIVE_STATUSES, Registration, RegistrationStatus
from app.user.models import Attendee, User, UserRole
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus

# Fixed namespace so slugs map to the same UUIDs on every machine and every run.
SEED_NAMESPACE = uuid.UUID("3f2b0c54-9b1a-4f3e-9a7e-2c0d1b8e5a41")
SEED_TIMEZONE = ZoneInfo("Asia/Singapore")


def seed_id(kind: str, slug: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{kind}:{slug}")


@dataclass
class EventSpec:
    slug: str
    name: str
    # Which of the states in the spec's SCRUM-23 list this event covers.
    note: str
    status: EventStatus = EventStatus.CONFIRMED
    registration_enabled: bool = True
    opens_in: timedelta | None = timedelta(days=-7)
    closes_in: timedelta | None = timedelta(days=7)
    starts_in: timedelta = timedelta(days=7)
    duration: timedelta = timedelta(hours=2)
    capacity: int = 40
    delivery_mode: DeliveryMode = DeliveryMode.IN_PERSON
    venue_name: str | None = "SMU SCIS Building"
    room_number: str | None = "Seminar Room 2-1"
    join_link: str | None = None
    # US6a: off by default, as in the database.
    waitlist_enabled: bool = False
    # Emails of attendees holding a confirmed seat, in order.
    confirmed: list[str] = field(default_factory=list)
    # Emails on the waitlist, earliest first.
    waitlisted: list[str] = field(default_factory=list)


ATTENDEES = [
    "calvin.ng.2024@smu.edu.sg",
    "mei.tan.2024@smu.edu.sg",
    "arjun.rao.2024@smu.edu.sg",
    "sofia.lim.2024@smu.edu.sg",
]
EVENT_ORGANISER_EMAIL = "event.organiser@smu.edu.sg"
EVENT_ORGANISER_NAME = "Olivia Organiser"
EVENT_COORDINATOR_EMAIL = "event.coordinator@smu.edu.sg"
# Seeded users get a full name, so what organisers see (SCRUM-13 AC 8) is a name, not an email.
EVENT_COORDINATOR_NAME = "Casey Tan"
VENUE_STAFF_EMAIL = "venue.staff@smu.edu.sg"
# SCRUM-82 AC 7: more than one Lead, never a single hard-coded one.
EVENT_COORDINATOR_LEAD_EMAILS = ("lead.one@smu.edu.sg", "lead.two@smu.edu.sg")
EVENT_COORDINATOR_LEAD_NAMES = {"lead.one@smu.edu.sg": "Lena Lim", "lead.two@smu.edu.sg": "Leo Lee"}

EVENTS = [
    EventSpec(
        slug="tech-talk-agile",
        name="Tech Talk: Agile at Scale",
        note="confirmed, registration open, seats available",
        capacity=40,
        confirmed=["calvin.ng.2024@smu.edu.sg", "mei.tan.2024@smu.edu.sg"],
    ),
    EventSpec(
        slug="design-sprint-bootcamp",
        name="Design Sprint Bootcamp",
        note="at full capacity, with a waitlist behind it",
        capacity=2,
        waitlist_enabled=True,
        starts_in=timedelta(days=4),
        confirmed=["mei.tan.2024@smu.edu.sg", "arjun.rao.2024@smu.edu.sg"],
        waitlisted=["sofia.lim.2024@smu.edu.sg", "calvin.ng.2024@smu.edu.sg"],
        venue_name="SMU Connexion",
        room_number="Studio 3-2",
    ),
    EventSpec(
        slug="supabase-live-coding",
        name="Intro to Supabase: Live Coding",
        note="online — joining info is a link, not a room",
        delivery_mode=DeliveryMode.ONLINE,
        venue_name=None,
        room_number=None,
        join_link="https://smu-sg.zoom.us/j/88123345901",
        capacity=200,
        starts_in=timedelta(days=11),
        confirmed=["calvin.ng.2024@smu.edu.sg"],
    ),
    EventSpec(
        slug="startup-pitch-night",
        name="Startup Pitch Night",
        note="registration not open yet (before registration_opens_at)",
        opens_in=timedelta(days=3),
        closes_in=timedelta(days=18),
        starts_in=timedelta(days=20),
        capacity=250,
        venue_name="Mochtar Riady Auditorium",
        room_number="Level B1",
    ),
    EventSpec(
        slug="career-fair-prep",
        name="Career Fair Prep Workshop",
        note="registration window has closed",
        opens_in=timedelta(days=-21),
        closes_in=timedelta(days=-1),
        starts_in=timedelta(days=2),
        capacity=60,
        venue_name="SMU Li Ka Shing Library",
        room_number="Seminar Room 3-4",
    ),
    EventSpec(
        slug="wellness-week-yoga",
        name="Wellness Week: Sunrise Yoga",
        note="confirmed but registration_enabled = false",
        registration_enabled=False,
        starts_in=timedelta(days=9),
        capacity=25,
        venue_name="SMU Campus Green",
        room_number="Lawn C",
    ),
    EventSpec(
        slug="orientation-debrief",
        name="Orientation Debrief",
        note="already ended — must not appear in any listing",
        opens_in=timedelta(days=-30),
        closes_in=timedelta(days=-10),
        starts_in=timedelta(days=-9),
        capacity=100,
        venue_name="SMU School of Accountancy",
        room_number="Function Room 2",
    ),
]


@dataclass
class VenueSpec:
    """A seeded venue for US20 and US2 search (SCRUM-87): varied capacity, tags and buffers."""

    slug: str
    name: str
    location: str
    capacity: int
    facilities: list[str]
    accessibility_features: list[str]
    room_layouts: list[str]
    opens_at: time
    closes_at: time
    setup_minutes: int
    turnaround_minutes: int
    is_active: bool = True


# The first five are the rooms the events above use, so they stay active. The inactive venue is
# one no seeded event names, so no demo event sits at a deactivated venue.
VENUES = [
    VenueSpec(
        slug="scis-seminar-2-1",
        name="SCIS Seminar Room 2-1",
        location="School of Computing and Information Systems, Level 2",
        capacity=40,
        facilities=["projector", "screen", "wifi", "whiteboard", "power_outlets"],
        accessibility_features=["wheelchair", "lift"],
        room_layouts=["classroom", "theatre", "u_shape"],
        opens_at=time(8, 0),
        closes_at=time(22, 0),
        setup_minutes=15,
        turnaround_minutes=15,
    ),
    VenueSpec(
        slug="mochtar-riady-auditorium",
        name="Mochtar Riady Auditorium",
        location="Administration Building, Level B1",
        capacity=450,
        facilities=["projector", "screen", "sound_system", "microphone", "stage", "wifi"],
        accessibility_features=["wheelchair", "lift", "accessible_toilet", "hearing_loop"],
        room_layouts=["theatre"],
        opens_at=time(8, 0),
        closes_at=time(23, 0),
        setup_minutes=60,
        turnaround_minutes=45,
    ),
    VenueSpec(
        slug="connexion-studio-3-2",
        name="SMU Connexion Studio 3-2",
        location="SMU Connexion, Level 3",
        capacity=30,
        facilities=["wifi", "whiteboard", "screen", "video_conferencing"],
        accessibility_features=["wheelchair", "lift"],
        room_layouts=["boardroom", "u_shape", "classroom"],
        opens_at=time(9, 0),
        closes_at=time(21, 0),
        # 0 is a valid buffer (US20 AC 4): back-to-back bookings with no setup or turnaround.
        setup_minutes=0,
        turnaround_minutes=0,
    ),
    VenueSpec(
        slug="campus-green-lawn-c",
        name="Campus Green, Lawn C",
        location="SMU Campus Green",
        capacity=200,
        facilities=["power_outlets"],
        accessibility_features=["step_free_entrance"],
        room_layouts=["standing", "banquet"],
        opens_at=time(7, 0),
        closes_at=time(19, 0),
        setup_minutes=90,
        turnaround_minutes=60,
    ),
    VenueSpec(
        slug="lks-library-seminar-3-4",
        name="Li Ka Shing Library Seminar Room 3-4",
        location="Li Ka Shing Library, Level 3",
        capacity=60,
        facilities=["projector", "screen", "wifi"],
        accessibility_features=["wheelchair", "lift"],
        room_layouts=["classroom", "theatre"],
        opens_at=time(9, 0),
        closes_at=time(18, 0),
        setup_minutes=20,
        turnaround_minutes=20,
    ),
    VenueSpec(
        slug="soe-seminar-b1-1",
        name="SOE Seminar Room B1-1",
        location="School of Economics, Level B1",
        capacity=50,
        facilities=["projector", "screen"],
        accessibility_features=["lift"],
        room_layouts=["classroom", "cabaret"],
        opens_at=time(9, 0),
        closes_at=time(18, 0),
        setup_minutes=20,
        turnaround_minutes=15,
        is_active=False,
    ),
]


@dataclass
class VenueBookingSpec:
    """A US22 booking on a seeded venue, for an approved event the seed adds alongside it (D24)."""

    slug: str
    event_name: str
    venue_slug: str
    status: VenueBookingStatus
    starts: time
    ends: time
    expected_attendees: int
    room_layout: str


@dataclass
class VenueBlockSpec:
    """A seeded venue closure (US2 AC 5)."""

    slug: str
    venue_slug: str
    starts: time
    ends: time
    note: str


# US2 AC 5: five days ahead, 10:00–12:00 Singapore time, one venue has a requested booking, one an
# approved booking and one a block, so searching that slot shows them drop out and the rest stay.
VENUE_SLOT_IN_DAYS = 5
VENUE_BOOKINGS = [
    VenueBookingSpec(
        slug="scis-requested",
        event_name="Analytics Club Workshop",
        venue_slug="scis-seminar-2-1",
        status=VenueBookingStatus.REQUESTED,
        starts=time(10, 0),
        ends=time(12, 0),
        expected_attendees=30,
        room_layout="classroom",
    ),
    VenueBookingSpec(
        slug="auditorium-approved",
        event_name="Faculty Town Hall",
        venue_slug="mochtar-riady-auditorium",
        status=VenueBookingStatus.APPROVED,
        starts=time(9, 0),
        ends=time(13, 0),
        expected_attendees=300,
        room_layout="theatre",
    ),
]
VENUE_BLOCKS = [
    VenueBlockSpec(
        slug="connexion-maintenance",
        venue_slug="connexion-studio-3-2",
        starts=time(8, 0),
        ends=time(18, 0),
        note="Closed for AV maintenance",
    ),
]


def upsert_attendee(db: Session, email: str) -> Attendee:
    attendee_id = seed_id("attendee", email)
    user = db.get(User, attendee_id)
    if user is None:
        user = User(id=attendee_id, email=email, role=UserRole.ATTENDEE)
        db.add(user)
        db.flush()
    attendee = db.get(Attendee, attendee_id)
    if attendee is None:
        attendee = Attendee(id=attendee_id, email=email)
        db.add(attendee)
    return attendee


def upsert_event_organiser(db: Session) -> User:
    organiser_id = seed_id("user", "event-organiser")
    organiser = db.get(User, organiser_id)
    if organiser is None:
        organiser = User(
            id=organiser_id,
            email=EVENT_ORGANISER_EMAIL,
            full_name=EVENT_ORGANISER_NAME,
            role=UserRole.ORGANISER,
            is_active=True,
        )
        db.add(organiser)
    else:
        organiser.email = EVENT_ORGANISER_EMAIL
        organiser.full_name = EVENT_ORGANISER_NAME
        organiser.role = UserRole.ORGANISER
        organiser.is_active = True
    return organiser


def upsert_event_coordinator(db: Session) -> User:
    """US8 reviews requests as a coordinator; the organiser can't stand in for one."""
    coordinator_id = seed_id("user", "event-coordinator")
    coordinator = db.get(User, coordinator_id)
    if coordinator is None:
        coordinator = User(
            id=coordinator_id,
            email=EVENT_COORDINATOR_EMAIL,
            full_name=EVENT_COORDINATOR_NAME,
            role=UserRole.COORDINATOR,
            is_active=True,
        )
        db.add(coordinator)
    else:
        coordinator.email = EVENT_COORDINATOR_EMAIL
        coordinator.full_name = EVENT_COORDINATOR_NAME
        coordinator.role = UserRole.COORDINATOR
        coordinator.is_active = True
    return coordinator


def upsert_venue_staff(db: Session) -> User:
    """US20 venue catalogue writes need Venue Staff."""
    # DECISION-PENDING: D19 — operations_manager stands in for Venue Staff until US16b adds the role.
    staff_id = seed_id("user", "venue-staff")
    staff = db.get(User, staff_id)
    if staff is None:
        staff = User(
            id=staff_id,
            email=VENUE_STAFF_EMAIL,
            role=UserRole.OPERATIONS_MANAGER,
            is_active=True,
        )
        db.add(staff)
    else:
        staff.email = VENUE_STAFF_EMAIL
        staff.role = UserRole.OPERATIONS_MANAGER
        staff.is_active = True
    return staff


def upsert_coordinator_leads(db: Session) -> list[User]:
    """US10a: the Event Coordinator Lead assigns coordinators; two exist so no one is special."""
    leads = []
    for email in EVENT_COORDINATOR_LEAD_EMAILS:
        lead_id = seed_id("user", email)
        lead = db.get(User, lead_id)
        if lead is None:
            lead = User(
                id=lead_id,
                email=email,
                full_name=EVENT_COORDINATOR_LEAD_NAMES[email],
                role=UserRole.COORDINATOR_LEAD,
                is_active=True,
            )
            db.add(lead)
        else:
            lead.email = email
            lead.full_name = EVENT_COORDINATOR_LEAD_NAMES[email]
            lead.role = UserRole.COORDINATOR_LEAD
            lead.is_active = True
        leads.append(lead)
    return leads


def upsert_event(db: Session, spec: EventSpec, now: datetime, organiser: User) -> Event:
    event_id = seed_id("event", spec.slug)
    start_at = now + spec.starts_in
    values = {
        "name": spec.name,
        "status": spec.status,
        "registration_enabled": spec.registration_enabled,
        "registration_opens_at": now + spec.opens_in if spec.opens_in else None,
        "registration_closes_at": now + spec.closes_in if spec.closes_in else None,
        "start_at": start_at,
        "end_at": start_at + spec.duration,
        "capacity": spec.capacity,
        "delivery_mode": spec.delivery_mode,
        "venue_name": spec.venue_name,
        "room_number": spec.room_number,
        "join_link": spec.join_link,
        "waitlist_enabled": spec.waitlist_enabled,
        # US28: the seeded organiser runs these, so it can view their registrations.
        "created_by_user_id": organiser.id,
    }
    event = db.get(Event, event_id)
    if event is None:
        event = Event(id=event_id, **values)
        db.add(event)
    else:
        for key, value in values.items():
            setattr(event, key, value)
    return event


def upsert_venue(db: Session, spec: VenueSpec) -> Venue:
    venue_id = seed_id("venue", spec.slug)
    values = {
        "name": spec.name,
        "location": spec.location,
        "capacity": spec.capacity,
        "facilities": spec.facilities,
        "accessibility_features": spec.accessibility_features,
        "room_layouts": spec.room_layouts,
        "opens_at": spec.opens_at,
        "closes_at": spec.closes_at,
        "setup_minutes": spec.setup_minutes,
        "turnaround_minutes": spec.turnaround_minutes,
        "is_active": spec.is_active,
    }
    venue = db.get(Venue, venue_id)
    if venue is None:
        venue = Venue(id=venue_id, **values)
        db.add(venue)
    else:
        for key, value in values.items():
            setattr(venue, key, value)
    return venue


def _slot_day(now: datetime):
    return now.astimezone(SEED_TIMEZONE).date() + timedelta(days=VENUE_SLOT_IN_DAYS)


def upsert_booking_event(db: Session, spec: VenueBookingSpec, organiser: User) -> Event:
    """The approved event a seeded booking is for. Nothing approves requests yet (US17), so the seed
    puts it straight into approved (D24). No request_reference: a fixed ER- value could collide with
    event_request_reference_seq later, and the column is nullable."""
    event_id = seed_id("event", f"booking-{spec.slug}")
    values = {
        "name": spec.event_name,
        "status": EventStatus.APPROVED,
        "event_category": "Seminar",
        "purpose": "Seeded for venue search and booking (US2, US22)",
        "expected_attendees": spec.expected_attendees,
        "created_by_user_id": organiser.id,
    }
    event = db.get(Event, event_id)
    if event is None:
        event = Event(id=event_id, **values)
        db.add(event)
    else:
        for key, value in values.items():
            setattr(event, key, value)
    return event


def upsert_venue_booking(
    db: Session, spec: VenueBookingSpec, event: Event, coordinator: User, now: datetime
) -> VenueBooking:
    booking_id = seed_id("venue-booking", spec.slug)
    day = _slot_day(now)
    values = {
        "event_id": event.id,
        "venue_id": seed_id("venue", spec.venue_slug),
        "requested_by_user_id": coordinator.id,
        "starts_at": datetime.combine(day, spec.starts, SEED_TIMEZONE),
        "ends_at": datetime.combine(day, spec.ends, SEED_TIMEZONE),
        "expected_attendees": spec.expected_attendees,
        "room_layout": spec.room_layout,
        "status": spec.status,
        "withdrawn_at": None,
    }
    booking = db.get(VenueBooking, booking_id)
    if booking is None:
        booking = VenueBooking(id=booking_id, **values)
        db.add(booking)
    else:
        for key, value in values.items():
            setattr(booking, key, value)
    return booking


def upsert_venue_block(db: Session, spec: VenueBlockSpec, now: datetime) -> VenueBlock:
    block_id = seed_id("venue-block", spec.slug)
    day = _slot_day(now)
    values = {
        "venue_id": seed_id("venue", spec.venue_slug),
        "starts_at": datetime.combine(day, spec.starts, SEED_TIMEZONE),
        "ends_at": datetime.combine(day, spec.ends, SEED_TIMEZONE),
        "note": spec.note,
    }
    block = db.get(VenueBlock, block_id)
    if block is None:
        block = VenueBlock(id=block_id, **values)
        db.add(block)
    else:
        for key, value in values.items():
            setattr(block, key, value)
    return block


def upsert_registration(
    db: Session,
    event: Event,
    attendee: Attendee,
    status: RegistrationStatus,
    now: datetime,
    queue_index: int = 0,
) -> Registration:
    registration_id = seed_id("registration", f"{event.id}:{attendee.id}")
    waitlisted = status == RegistrationStatus.WAITLISTED
    values = {
        "event_id": event.id,
        "attendee_id": attendee.id,
        "attendee_email": attendee.email,
        "status": status,
        # Spaced a minute apart so the derived queue order is stable and obvious.
        "waitlist_joined_at": now - timedelta(minutes=60 - queue_index) if waitlisted else None,
        "offer_expires_at": None,
        "withdrawn_at": None,
        "updated_at": now,
    }
    # Using the app between seeds (withdraw, then register or rejoin again) leaves a newer active
    # row for this pair. Withdraw it, and flush before resetting the seeded row, so the two are
    # never active at once (registrations_one_active_per_attendee).
    others = db.scalars(
        select(Registration).where(
            Registration.event_id == event.id,
            Registration.attendee_id == attendee.id,
            Registration.id != registration_id,
            Registration.status.in_(ACTIVE_STATUSES),
        )
    ).all()
    for other in others:
        other.status = RegistrationStatus.WITHDRAWN
        other.withdrawn_at = now
        other.updated_at = now
    if others:
        db.flush()

    registration = db.get(Registration, registration_id)
    if registration is None:
        registration = Registration(id=registration_id, **values)
        db.add(registration)
    else:
        for key, value in values.items():
            setattr(registration, key, value)
    return registration


def seed(db: Session, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    organiser = upsert_event_organiser(db)
    coordinator = upsert_event_coordinator(db)
    upsert_venue_staff(db)
    upsert_coordinator_leads(db)
    attendees = {email: upsert_attendee(db, email) for email in ATTENDEES}
    db.flush()

    for spec in EVENTS:
        event = upsert_event(db, spec, now, organiser)
        db.flush()
        for email in spec.confirmed:
            upsert_registration(db, event, attendees[email], RegistrationStatus.CONFIRMED, now)
        for index, email in enumerate(spec.waitlisted):
            upsert_registration(
                db, event, attendees[email], RegistrationStatus.WAITLISTED, now, queue_index=index
            )
        db.flush()

    for spec in VENUES:
        upsert_venue(db, spec)
    db.flush()

    for spec in VENUE_BOOKINGS:
        event = upsert_booking_event(db, spec, organiser)
        db.flush()
        upsert_venue_booking(db, spec, event, coordinator, now)
    for spec in VENUE_BLOCKS:
        upsert_venue_block(db, spec, now)
    db.flush()

    db.commit()


def main() -> int:
    host = make_url(settings.database_url).host or "localhost"
    is_local = host in {"localhost", "127.0.0.1", "::1"}
    if not is_local and "--yes" not in sys.argv:
        print(f"Refusing to seed a non-local database ({host}) without --yes.")
        return 1

    print(f"Seeding {host} ...")
    with SessionLocal() as db:
        seed(db)

        print(f"\n{len(EVENTS)} events, {len(ATTENDEES)} attendees, {len(VENUES)} venues, "
              f"{len(VENUE_BOOKINGS)} venue bookings, {len(VENUE_BLOCKS)} venue blocks:\n")
        for spec in EVENTS:
            print(f"  {spec.name:<34} {spec.note}")

        calvin = db.get(Attendee, seed_id("attendee", ATTENDEES[0]))
        print(f"\nX-Attendee-Id for {calvin.email}:\n  {calvin.id}\n")
        organiser = db.get(User, seed_id("user", "event-organiser"))
        print(f"VITE_DEV_USER_ID for {organiser.email}:\n  {organiser.id}\n")
        coordinator = db.get(User, seed_id("user", "event-coordinator"))
        print(f"X-User-Id for {coordinator.email}:\n  {coordinator.id}\n")
        venue_staff = db.get(User, seed_id("user", "venue-staff"))
        print(f"VITE_DEV_VENUE_STAFF_ID for {venue_staff.email}:\n  {venue_staff.id}\n")
        for email in EVENT_COORDINATOR_LEAD_EMAILS:
            lead = db.get(User, seed_id("user", email))
            print(f"X-User-Id for {lead.email} (Coordinator Lead):\n  {lead.id}\n")
        print("Registrations you can withdraw:")
        mine = db.scalars(select(Registration).where(Registration.attendee_id == calvin.id))
        for registration in mine:
            event = db.get(Event, registration.event_id)
            print(f"  {registration.status.value:<11} {event.name:<34} {registration.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
