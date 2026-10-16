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

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.event.models import DeliveryMode, Event, EventStatus
from app.registration.models import ACTIVE_STATUSES, Registration, RegistrationStatus
from app.user.models import Attendee, User, UserRole
from app.user.supabase_admin import SupabaseAdmin, SupabaseAdminError
from app.venue.models import Venue

# Fixed namespace so slugs map to the same UUIDs on every machine and every run.
SEED_NAMESPACE = uuid.UUID("3f2b0c54-9b1a-4f3e-9a7e-2c0d1b8e5a41")


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
EVENT_COORDINATOR_EMAIL = "event.coordinator@smu.edu.sg"
# Everyone the seed creates a Supabase login for (SCRUM-104). Staff can't sign up (US16a AC 7), so this
# is how the coordinator gets one.
SEEDED_LOGIN_EMAILS = [EVENT_ORGANISER_EMAIL, EVENT_COORDINATOR_EMAIL, *ATTENDEES]

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
            role=UserRole.ORGANISER,
            is_active=True,
        )
        db.add(organiser)
    else:
        organiser.email = EVENT_ORGANISER_EMAIL
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
            role=UserRole.COORDINATOR,
            is_active=True,
        )
        db.add(coordinator)
    else:
        coordinator.email = EVENT_COORDINATOR_EMAIL
        coordinator.role = UserRole.COORDINATOR
        coordinator.is_active = True
    return coordinator


def upsert_event(db: Session, spec: EventSpec, now: datetime) -> Event:
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
    upsert_event_organiser(db)
    upsert_event_coordinator(db)
    attendees = {email: upsert_attendee(db, email) for email in ATTENDEES}
    db.flush()

    for spec in EVENTS:
        event = upsert_event(db, spec, now)
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

    db.commit()


class SeedAuthError(Exception):
    """A seeded user's Supabase login couldn't be created or found. Nothing was linked."""


def seed_auth_logins(db: Session, admin: SupabaseAdmin | None, password: str | None) -> None:
    """Create (or reuse) a confirmed Supabase login for every seeded user and link it by
    `auth_user_id` (SCRUM-104). Every login is fetched before any row changes, so a failure for one
    email leaves no row half-linked. Prints emails only, never the key or password."""
    missing = [name for name, value in (("SUPABASE_SECRET_KEY", admin), ("SEED_AUTH_PASSWORD", password)) if not value]
    if missing:
        print(f"\nSupabase Auth logins skipped: {', '.join(missing)} not set.")
        return

    auth_ids = {}
    for email in SEEDED_LOGIN_EMAILS:
        try:
            auth_ids[email] = admin.ensure_user(email, password)
        except SupabaseAdminError as error:
            raise SeedAuthError(f"Couldn't create the Supabase login for {email}: {error}") from None

    for user in db.scalars(select(User).where(User.email.in_(SEEDED_LOGIN_EMAILS))):
        user.auth_user_id = auth_ids[user.email]
    db.commit()

    print("\nSupabase Auth logins (password: SEED_AUTH_PASSWORD in backend/.env):")
    for email in SEEDED_LOGIN_EMAILS:
        print(f"  {email}")


def admin_from_settings() -> SupabaseAdmin | None:
    if not (settings.supabase_url and settings.supabase_secret_key):
        return None
    return SupabaseAdmin(settings.supabase_url, settings.supabase_secret_key)


def main() -> int:
    host = make_url(settings.database_url).host or "localhost"
    is_local = host in {"localhost", "127.0.0.1", "::1"}
    if not is_local and "--yes" not in sys.argv:
        print(f"Refusing to seed a non-local database ({host}) without --yes.")
        return 1

    print(f"Seeding {host} ...")
    with SessionLocal() as db:
        seed(db)

        print(f"\n{len(EVENTS)} events, {len(ATTENDEES)} attendees, {len(VENUES)} venues:\n")
        for spec in EVENTS:
            print(f"  {spec.name:<34} {spec.note}")

        calvin = db.get(Attendee, seed_id("attendee", ATTENDEES[0]))
        print(f"\nX-Attendee-Id for {calvin.email}:\n  {calvin.id}\n")
        organiser = db.get(User, seed_id("user", "event-organiser"))
        print(f"VITE_DEV_USER_ID for {organiser.email}:\n  {organiser.id}\n")
        coordinator = db.get(User, seed_id("user", "event-coordinator"))
        print(f"X-User-Id for {coordinator.email}:\n  {coordinator.id}\n")
        print("Registrations you can withdraw:")
        mine = db.scalars(select(Registration).where(Registration.attendee_id == calvin.id))
        for registration in mine:
            event = db.get(Event, registration.event_id)
            print(f"  {registration.status.value:<11} {event.name:<34} {registration.id}")

        try:
            seed_auth_logins(db, admin_from_settings(), settings.seed_auth_password)
        except SeedAuthError as error:
            print(f"\n{error}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
