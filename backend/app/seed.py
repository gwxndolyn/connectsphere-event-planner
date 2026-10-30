"""Sprint 1 seed data (SCRUM-23).

Sprint 1 can't create a confirmed event through the product — event creation is Epic 1 —
so the states the registration and withdrawal flows need are seeded here instead.

Idempotent: every row's UUID is derived from a slug, so re-running updates the same rows
rather than inserting duplicates.

    python -m app.seed          # against a local database
    python -m app.seed --yes    # required when DATABASE_URL is not localhost

Reseeding also deletes every equipment line on Equipment Request Demo, approved ones included, so E2E
reruns start clean (SCRUM-110); other events' lines are untouched.
"""

import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.equipment.models import EquipmentRequestLine, EquipmentType
from app.event.models import DeliveryMode, Event, EventStatus
from app.registration.models import ACTIVE_STATUSES, Registration, RegistrationStatus
from app.user.models import Attendee, User, UserRole
from app.user.supabase_admin import SupabaseAdmin, SupabaseAdminError
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus, occupied_window

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
    # US24 (SCRUM-127): the seeded venue (VenueSpec.slug) of its approved primary booking.
    # DECISION-PENDING: D70 — from PR 2 attendees see that booking's venue, not venue_name/room_number,
    # which stay as the fallback. None for an online event, or a place with no seeded venue.
    venue_slug: str | None = "scis-seminar-2-1"
    join_link: str | None = None
    # US6a: off by default, as in the database.
    waitlist_enabled: bool = False
    # US28: assigned to the seeded coordinator, so its Registrations view has an event (D52).
    coordinator_assigned: bool = False
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
# Every seeded user has a full name (TC-US16B-04).
ATTENDEE_NAMES = {
    "calvin.ng.2024@smu.edu.sg": "Calvin Ng",
    "mei.tan.2024@smu.edu.sg": "Mei Tan",
    "arjun.rao.2024@smu.edu.sg": "Arjun Rao",
    "sofia.lim.2024@smu.edu.sg": "Sofia Lim",
}
EVENT_ORGANISER_EMAIL = "event.organiser@smu.edu.sg"
EVENT_ORGANISER_NAME = "Olivia Organiser"
EVENT_COORDINATOR_EMAIL = "event.coordinator@smu.edu.sg"
# Seeded users get a full name, so what organisers see (SCRUM-13 AC 8) is a name, not an email.
EVENT_COORDINATOR_NAME = "Casey Tan"
VENUE_STAFF_EMAIL = "venue.staff@smu.edu.sg"
VENUE_STAFF_NAME = "Vera Goh"
# SCRUM-82 AC 7: more than one Lead, never a single hard-coded one.
EVENT_COORDINATOR_LEAD_EMAILS = ("lead.one@smu.edu.sg", "lead.two@smu.edu.sg")
EVENT_COORDINATOR_LEAD_NAMES = {"lead.one@smu.edu.sg": "Lena Lim", "lead.two@smu.edu.sg": "Leo Lee"}
TECH_SUPPORT_EMAIL = "tech.support@smu.edu.sg"
TECH_SUPPORT_NAME = "Terry Ong"
# US16b (SCRUM-119): the Safety officer has no screens yet, but has a login (TC-US16B-04, 21).
SAFETY_OFFICER_EMAIL = "safety.officer@smu.edu.sg"
SAFETY_OFFICER_NAME = "Sam Koh"
# DECISION-PENDING: D50 — one user holding two roles, for the role switcher (SCRUM-121) and the
# held-role checks.
MULTI_ROLE_EMAIL = "multi.role@smu.edu.sg"
MULTI_ROLE_NAME = "Morgan Lau"
# Everyone the seed creates a Supabase login for (SCRUM-104). Staff can't sign up (US16a AC 7), so this
# is how the coordinator, venue staff, Tech Support, the Safety officer, the two-role user and Leads get one.
SEEDED_LOGIN_EMAILS = [
    EVENT_ORGANISER_EMAIL,
    EVENT_COORDINATOR_EMAIL,
    VENUE_STAFF_EMAIL,
    TECH_SUPPORT_EMAIL,
    SAFETY_OFFICER_EMAIL,
    MULTI_ROLE_EMAIL,
    *EVENT_COORDINATOR_LEAD_EMAILS,
    *ATTENDEES,
]


@dataclass
class EquipmentStock:
    """A catalogue entry's stock (US5, SCRUM-124): owned, out of service (AC 3) and where it's kept (AC 7)."""

    total: int
    out_of_service: int
    location: str


AV_STORE = "AV store, Level B1, Administration Building"
IT_DESK = "IT service desk, Level 2, Administration Building"
FACILITIES_ROOM = "Facilities room, Level 1, Administration Building"
# US26 (SCRUM-108): the equipment catalogue a request line picks from. US5 (SCRUM-124) gives each a small
# stock, so a large request on Equipment Request Demo comes out short. DECISION-PENDING: D63 — stock is
# only ever set here; no screen edits it yet.
EQUIPMENT_STOCK = {
    "Projector": EquipmentStock(total=6, out_of_service=1, location=AV_STORE),
    "Projector screen": EquipmentStock(total=4, out_of_service=0, location=AV_STORE),
    "Wireless microphone": EquipmentStock(total=10, out_of_service=2, location=AV_STORE),
    "Speaker system": EquipmentStock(total=3, out_of_service=1, location=AV_STORE),
    "Laptop": EquipmentStock(total=8, out_of_service=0, location=IT_DESK),
    "HDMI cable": EquipmentStock(total=20, out_of_service=3, location=IT_DESK),
    "Extension cord": EquipmentStock(total=15, out_of_service=0, location=FACILITIES_ROOM),
    "Webcam": EquipmentStock(total=5, out_of_service=0, location=IT_DESK),
}
EQUIPMENT_TYPES = list(EQUIPMENT_STOCK)

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
        venue_slug="connexion-studio-3-2",
    ),
    EventSpec(
        slug="supabase-live-coding",
        name="Intro to Supabase: Live Coding",
        note="online — joining info is a link, not a room",
        delivery_mode=DeliveryMode.ONLINE,
        venue_name=None,
        room_number=None,
        venue_slug=None,
        join_link="https://smu-sg.zoom.us/j/88123345901",
        capacity=200,
        starts_in=timedelta(days=11),
        coordinator_assigned=True,
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
        venue_slug="mochtar-riady-auditorium",
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
        venue_slug="lks-library-seminar-3-4",
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
        venue_slug="campus-green-lawn-c",
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
        # No seeded venue there, so it keeps the event's own venue_name / room_number (D70's fallback).
        venue_slug=None,
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


@dataclass
class BookableEventSpec:
    """An approved event with no bookings, for the US22 booking screens to book (SCRUM-113)."""

    slug: str
    name: str
    expected_attendees: int


# US22 (SCRUM-89): the dev coordinator requests venues for it, locally and in
# e2e/tests/venue-booking.spec.ts. The organiser owns it and it's assigned to the seeded coordinator
# (VITE_DEV_COORDINATOR_ID), because only the assigned coordinator may book it (US10a, D20).
# Approved straight away (D24).
BOOKABLE_EVENT = BookableEventSpec(slug="bookable-venue-booking-demo", name="Venue Booking Demo", expected_attendees=40)

# US24 (SCRUM-92): every seeded booking says what it's for; a single-venue event's is its main venue.
MAIN_VENUE_PURPOSE = "Main venue"


@dataclass
class MultiVenueBookingSpec:
    """One venue of the multi-venue demo event (US24)."""

    slug: str
    venue_slug: str
    purpose: str
    status: VenueBookingStatus
    starts: time
    ends: time
    expected_attendees: int
    room_layout: str
    is_primary: bool = False
    rejection_reason: str | None = None


@dataclass
class MultiVenueEventSpec:
    """An approved event booked at several venues on one preferred day (US24, SCRUM-127)."""

    slug: str
    name: str
    in_days: int
    starts: time
    ends: time
    expected_attendees: int
    bookings: list[MultiVenueBookingSpec]


# US24 (SCRUM-92): a conference with an approved main hall (its primary venue), a breakout room
# waiting for Venue staff and one they rejected, so the screens (PR 3) show each status and an event
# whose venues aren't all arranged (AC 6, 7). Assigned to the dev coordinator, who may add and
# withdraw its bookings (D20). Twelve days ahead, away from US2's slot (day 5) and the other seeded
# events' days, so its windows clash with nothing.
MULTI_VENUE_EVENT = MultiVenueEventSpec(
    slug="multi-venue-conference-demo",
    name="Multi-Venue Conference Demo",
    in_days=12,
    starts=time(9, 0),
    ends=time(17, 0),
    expected_attendees=300,
    bookings=[
        MultiVenueBookingSpec(
            slug="multi-venue-main-hall",
            venue_slug="mochtar-riady-auditorium",
            purpose="Main hall",
            status=VenueBookingStatus.APPROVED,
            starts=time(9, 0),
            ends=time(17, 0),
            expected_attendees=300,
            room_layout="theatre",
            is_primary=True,
        ),
        MultiVenueBookingSpec(
            slug="multi-venue-breakout-a",
            venue_slug="scis-seminar-2-1",
            purpose="Breakout A",
            status=VenueBookingStatus.REQUESTED,
            starts=time(13, 0),
            ends=time(15, 0),
            expected_attendees=40,
            room_layout="classroom",
        ),
        MultiVenueBookingSpec(
            slug="multi-venue-breakout-b",
            venue_slug="lks-library-seminar-3-4",
            purpose="Breakout B",
            status=VenueBookingStatus.REJECTED,
            starts=time(13, 0),
            ends=time(15, 0),
            expected_attendees=60,
            room_layout="classroom",
            rejection_reason="The library is closed to events that afternoon.",
        ),
    ],
)

# US26 (SCRUM-109): the dev coordinator adds equipment lines to it (SCRUM-110, TC-US26-16). Only a
# planning or confirmed event takes them, from its assigned coordinator (D20), and no other seeded
# event is both. Registration is off, so it stays off the attendees' events board.
EQUIPMENT_EVENT = EventSpec(
    slug="equipment-request-demo",
    name="Equipment Request Demo",
    note="confirmed, assigned to the seeded coordinator, registration off (US26)",
    registration_enabled=False,
    starts_in=timedelta(days=14),
)

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
        user = User(id=attendee_id, email=email, full_name=ATTENDEE_NAMES[email], roles=[UserRole.ATTENDEE])
        db.add(user)
        db.flush()
    else:
        user.full_name = ATTENDEE_NAMES[email]
        user.roles = [UserRole.ATTENDEE]
    attendee = db.get(Attendee, attendee_id)
    if attendee is None:
        attendee = Attendee(id=attendee_id, email=email)
        db.add(attendee)
    return attendee


def upsert_staff_user(db: Session, slug: str, email: str, full_name: str, roles: list[UserRole]) -> User:
    """A seeded user other than an attendee, reset to its seeded email, name and roles on every run."""
    user_id = seed_id("user", slug)
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id)
        db.add(user)
    user.email = email
    user.full_name = full_name
    user.roles = roles
    user.is_active = True
    return user


def upsert_event_organiser(db: Session) -> User:
    return upsert_staff_user(db, "event-organiser", EVENT_ORGANISER_EMAIL, EVENT_ORGANISER_NAME, [UserRole.ORGANISER])


def upsert_event_coordinator(db: Session) -> User:
    """US8 reviews requests as a coordinator; the organiser can't stand in for one."""
    return upsert_staff_user(
        db, "event-coordinator", EVENT_COORDINATOR_EMAIL, EVENT_COORDINATOR_NAME, [UserRole.COORDINATOR]
    )


def upsert_venue_staff(db: Session) -> User:
    """US20 venue catalogue writes need Venue Staff."""
    return upsert_staff_user(db, "venue-staff", VENUE_STAFF_EMAIL, VENUE_STAFF_NAME, [UserRole.VENUE_STAFF])


def upsert_tech_support(db: Session) -> User:
    """US26 reviews equipment requests as Technical Support Staff."""
    return upsert_staff_user(db, "tech-support", TECH_SUPPORT_EMAIL, TECH_SUPPORT_NAME, [UserRole.TECH_SUPPORT])


def upsert_safety_officer(db: Session) -> User:
    return upsert_staff_user(
        db, "safety-officer", SAFETY_OFFICER_EMAIL, SAFETY_OFFICER_NAME, [UserRole.SAFETY_OFFICER]
    )


def upsert_multi_role(db: Session) -> User:
    """D50: Coordinator and Venue Staff, the pair US16b's switcher and held-role checks are tried with."""
    return upsert_staff_user(
        db, "multi-role", MULTI_ROLE_EMAIL, MULTI_ROLE_NAME, [UserRole.COORDINATOR, UserRole.VENUE_STAFF]
    )


def upsert_coordinator_leads(db: Session) -> list[User]:
    """US10a: the Event Coordinator Lead assigns coordinators; two exist so no one is special."""
    return [
        upsert_staff_user(db, email, email, EVENT_COORDINATOR_LEAD_NAMES[email], [UserRole.COORDINATOR_LEAD])
        for email in EVENT_COORDINATOR_LEAD_EMAILS
    ]


def upsert_equipment_type(db: Session, name: str, stock: EquipmentStock) -> EquipmentType:
    type_id = seed_id("equipment-type", name)
    values = {
        "name": name,
        "total_quantity": stock.total,
        "out_of_service_quantity": stock.out_of_service,
        "storage_location": stock.location,
    }
    equipment_type = db.get(EquipmentType, type_id)
    if equipment_type is None:
        equipment_type = EquipmentType(id=type_id, **values)
        db.add(equipment_type)
    else:
        for key, value in values.items():
            setattr(equipment_type, key, value)
    return equipment_type


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


def upsert_bookable_event(db: Session, spec: BookableEventSpec, organiser: User, coordinator: User) -> Event:
    """The approved event the booking screens book, assigned to `coordinator`. Its bookings are made
    through the app, so a reseed leaves them alone: the seed owns only the event row."""
    event_id = seed_id("event", spec.slug)
    values = {
        "name": spec.name,
        "status": EventStatus.APPROVED,
        "event_category": "Workshop",
        "purpose": "Seeded for requesting a venue (US22)",
        "expected_attendees": spec.expected_attendees,
        "created_by_user_id": organiser.id,
        "coordinator_id": coordinator.id,
    }
    event = db.get(Event, event_id)
    if event is None:
        event = Event(id=event_id, **values)
        db.add(event)
    else:
        for key, value in values.items():
            setattr(event, key, value)
    return event


def upsert_equipment_event(
    db: Session, spec: EventSpec, organiser: User, coordinator: User, now: datetime
) -> Event:
    """The confirmed event the equipment screens add lines to, assigned to `coordinator`. Its lines are
    made through the app, and a reseed removes them all (SCRUM-110): an approved line can't be removed
    and D41 allows one live line per type, so E2E reruns (TC-US26-17) would otherwise use up the types."""
    event = upsert_event(db, spec, now, organiser)
    event.coordinator_id = coordinator.id
    db.execute(delete(EquipmentRequestLine).where(EquipmentRequestLine.event_id == event.id))
    return event


def upsert_venue_booking(
    db: Session, spec: VenueBookingSpec, event: Event, coordinator: User, now: datetime
) -> VenueBooking:
    booking_id = seed_id("venue-booking", spec.slug)
    day = _slot_day(now)
    starts_at = datetime.combine(day, spec.starts, SEED_TIMEZONE)
    ends_at = datetime.combine(day, spec.ends, SEED_TIMEZONE)
    # US13: the window the venue's buffers make it occupy. The reference comes from the database.
    occupied_starts_at, occupied_ends_at = occupied_window(db.get(Venue, seed_id("venue", spec.venue_slug)), starts_at, ends_at)
    values = {
        "event_id": event.id,
        "venue_id": seed_id("venue", spec.venue_slug),
        "requested_by_user_id": coordinator.id,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "occupied_starts_at": occupied_starts_at,
        "occupied_ends_at": occupied_ends_at,
        "expected_attendees": spec.expected_attendees,
        "room_layout": spec.room_layout,
        "status": spec.status,
        "withdrawn_at": None,
        # US4: an approved seeded booking was decided by the seeded Venue Staff member, when seeded.
        "decided_at": now if spec.status == VenueBookingStatus.APPROVED else None,
        "decided_by_user_id": seed_id("user", "venue-staff") if spec.status == VenueBookingStatus.APPROVED else None,
        "rejection_reason": None,
        "alternative_suggestion": None,
        # US24: the only venue of its event, so its primary one.
        "purpose": MAIN_VENUE_PURPOSE,
        "is_primary": True,
    }
    return _upsert_booking(db, booking_id, values)


def _upsert_booking(db: Session, booking_id: uuid.UUID, values: dict[str, object]) -> VenueBooking:
    """Creates or resets a seeded booking. A seeded primary takes the flag back from any other booking
    of its event made primary in the app since, so a reseed never trips the one-primary index (US24)."""
    if values.get("is_primary"):
        db.execute(
            update(VenueBooking)
            .where(VenueBooking.event_id == values["event_id"], VenueBooking.id != booking_id, VenueBooking.is_primary)
            .values(is_primary=False)
        )
        db.flush()
    booking = db.get(VenueBooking, booking_id)
    if booking is None:
        booking = VenueBooking(id=booking_id, **values)
        db.add(booking)
    else:
        for key, value in values.items():
            setattr(booking, key, value)
    db.flush()
    return booking


def _decision(status: VenueBookingStatus, now: datetime) -> dict[str, object]:
    """US4: an approved or rejected seeded booking was decided by the seeded Venue Staff member, when seeded."""
    decided = status in (VenueBookingStatus.APPROVED, VenueBookingStatus.REJECTED)
    return {
        "status": status,
        "withdrawn_at": None,
        "decided_at": now if decided else None,
        "decided_by_user_id": seed_id("user", "venue-staff") if decided else None,
    }


def upsert_primary_booking(db: Session, spec: EventSpec, event: Event, coordinator: User, now: datetime) -> VenueBooking:
    """US24 (SCRUM-127): an in-person seeded event's approved primary booking at `spec.venue_slug`, over
    the event's own times, for as many attendees as the event holds (AC 3)."""
    # DECISION-PENDING: D65 — a booking's own window falls within the event's schedule: start_at to end_at.
    venue = db.get(Venue, seed_id("venue", spec.venue_slug))
    occupied_starts_at, occupied_ends_at = occupied_window(venue, event.start_at, event.end_at)
    values = {
        "event_id": event.id,
        "venue_id": venue.id,
        "requested_by_user_id": coordinator.id,
        "starts_at": event.start_at,
        "ends_at": event.end_at,
        "occupied_starts_at": occupied_starts_at,
        "occupied_ends_at": occupied_ends_at,
        "expected_attendees": event.capacity,
        "room_layout": venue.room_layouts[0],
        **_decision(VenueBookingStatus.APPROVED, now),
        "rejection_reason": None,
        "alternative_suggestion": None,
        "purpose": MAIN_VENUE_PURPOSE,
        "is_primary": True,
    }
    return _upsert_booking(db, seed_id("venue-booking", f"primary-{spec.slug}"), values)


def upsert_multi_venue_event(
    db: Session, spec: MultiVenueEventSpec, organiser: User, coordinator: User, now: datetime
) -> Event:
    """US24's demo event and its venues. Bookings the coordinator adds in the app are left alone; the
    seeded ones are reset, and the main hall is primary again."""
    # DECISION-PENDING: D65 — before start_at is set, the schedule is a preferred day between the
    # preferred times, so each window sits on that day inside them.
    day = now.astimezone(SEED_TIMEZONE).date() + timedelta(days=spec.in_days)
    event_id = seed_id("event", spec.slug)
    values = {
        "name": spec.name,
        "status": EventStatus.APPROVED,
        "event_category": "Conference",
        "purpose": "Seeded for booking several venues for one event (US24)",
        "preferred_dates": [day],
        "preferred_start_time": spec.starts,
        "preferred_end_time": spec.ends,
        "expected_attendees": spec.expected_attendees,
        "created_by_user_id": organiser.id,
        "coordinator_id": coordinator.id,
    }
    event = db.get(Event, event_id)
    if event is None:
        event = Event(id=event_id, **values)
        db.add(event)
    else:
        for key, value in values.items():
            setattr(event, key, value)
    db.flush()
    # Non-primary ones first, so the main hall takes the flag last.
    for booking_spec in sorted(spec.bookings, key=lambda b: b.is_primary):
        venue = db.get(Venue, seed_id("venue", booking_spec.venue_slug))
        starts_at = datetime.combine(day, booking_spec.starts, SEED_TIMEZONE)
        ends_at = datetime.combine(day, booking_spec.ends, SEED_TIMEZONE)
        occupied_starts_at, occupied_ends_at = occupied_window(venue, starts_at, ends_at)
        _upsert_booking(
            db,
            seed_id("venue-booking", booking_spec.slug),
            {
                "event_id": event.id,
                "venue_id": venue.id,
                "requested_by_user_id": coordinator.id,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "occupied_starts_at": occupied_starts_at,
                "occupied_ends_at": occupied_ends_at,
                "expected_attendees": booking_spec.expected_attendees,
                "room_layout": booking_spec.room_layout,
                **_decision(booking_spec.status, now),
                "rejection_reason": booking_spec.rejection_reason,
                "alternative_suggestion": None,
                "purpose": booking_spec.purpose,
                "is_primary": booking_spec.is_primary,
            },
        )
    return event


def seeded_booking_count() -> int:
    """Every booking the seed owns: US2's slot, each in-person event's primary and the multi-venue
    demo event's venues (US24). Bookings made in the app aren't counted."""
    primaries = sum(1 for spec in [*EVENTS, EQUIPMENT_EVENT] if spec.venue_slug)
    return len(VENUE_BOOKINGS) + primaries + len(MULTI_VENUE_EVENT.bookings)


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
    upsert_tech_support(db)
    upsert_safety_officer(db)
    upsert_multi_role(db)
    attendees = {email: upsert_attendee(db, email) for email in ATTENDEES}
    db.flush()

    for spec in EVENTS:
        event = upsert_event(db, spec, now, organiser)
        if spec.coordinator_assigned:
            event.coordinator_id = coordinator.id
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

    # US24: each in-person event's venue, as an approved primary booking.
    for spec in EVENTS:
        if spec.venue_slug:
            upsert_primary_booking(db, spec, db.get(Event, seed_id("event", spec.slug)), coordinator, now)

    for spec in VENUE_BOOKINGS:
        event = upsert_booking_event(db, spec, organiser)
        db.flush()
        upsert_venue_booking(db, spec, event, coordinator, now)
    for spec in VENUE_BLOCKS:
        upsert_venue_block(db, spec, now)
    upsert_bookable_event(db, BOOKABLE_EVENT, organiser, coordinator)
    equipment_event = upsert_equipment_event(db, EQUIPMENT_EVENT, organiser, coordinator, now)
    db.flush()
    upsert_primary_booking(db, EQUIPMENT_EVENT, equipment_event, coordinator, now)
    upsert_multi_venue_event(db, MULTI_VENUE_EVENT, organiser, coordinator, now)
    for name, stock in EQUIPMENT_STOCK.items():
        upsert_equipment_type(db, name, stock)
    db.flush()

    db.commit()


class SeedAuthError(Exception):
    """A seeded user's Supabase login couldn't be created, found or linked. Nothing was linked."""


# The seeded logins share one password and include staff, so a short one is refused (PR #56 review).
MIN_SEED_PASSWORD_LENGTH = 12


def missing_admin_settings() -> list[str]:
    """Which of the two settings the Admin API needs are unset, by name, for the skip message."""
    values = (
        ("SUPABASE_URL", settings.supabase_url),
        ("SUPABASE_SECRET_KEY", settings.supabase_secret_key.get_secret_value()),
    )
    return [name for name, value in values if not value]


def seed_auth_logins(db: Session, admin: SupabaseAdmin | None, password: str | None) -> None:
    """Create (or reuse) a confirmed Supabase login for every seeded user and link it by
    `auth_user_id` (SCRUM-104). Every login is fetched and checked before any row changes, so a failure
    for one email leaves no row half-linked. Prints emails only, never the key or password."""
    missing = (missing_admin_settings() or ["SUPABASE_SECRET_KEY"]) if admin is None else []
    if not password:
        missing.append("SEED_AUTH_PASSWORD")
    if missing:
        print(f"\nSupabase Auth logins skipped: {', '.join(missing)} not set.")
        return
    if len(password) < MIN_SEED_PASSWORD_LENGTH:
        raise SeedAuthError(f"SEED_AUTH_PASSWORD must be at least {MIN_SEED_PASSWORD_LENGTH} characters.")

    auth_ids = {}
    for email in SEEDED_LOGIN_EMAILS:
        try:
            auth_ids[email] = admin.ensure_user(email, password)
        except SupabaseAdminError as error:
            raise SeedAuthError(f"Couldn't create the Supabase login for {email}: {error}") from None

    users = list(db.scalars(select(User).where(User.email.in_(SEEDED_LOGIN_EMAILS))))
    # A row already linked to a different account (e.g. a real person signed up with a demo address and
    # #55 linked it) is never re-pointed (PR #56 review).
    for user in users:
        if user.auth_user_id not in (None, auth_ids[user.email]):
            raise SeedAuthError(f"{user.email} is already linked to a different Supabase account; nothing was linked.")
    for user in users:
        user.auth_user_id = auth_ids[user.email]
    db.commit()

    print("\nSupabase Auth logins (password: SEED_AUTH_PASSWORD in backend/.env):")
    for email in SEEDED_LOGIN_EMAILS:
        print(f"  {email}")


def admin_from_settings() -> SupabaseAdmin | None:
    if missing_admin_settings():
        return None
    return SupabaseAdmin(settings.supabase_url, settings.supabase_secret_key.get_secret_value())


# PR #78 review: on a shared database these could be someone's real requests.
REMOTE_RESEED_WARNING = (
    "Reseeding also deletes every equipment line on Equipment Request Demo, approved ones included. "
    "Other events' lines are untouched."
)


def main() -> int:
    host = make_url(settings.database_url).host or "localhost"
    is_local = host in {"localhost", "127.0.0.1", "::1"}
    if not is_local:
        if "--yes" not in sys.argv:
            print(f"Refusing to seed a non-local database ({host}) without --yes.")
            print(REMOTE_RESEED_WARNING)
            return 1
        # Said before anything is deleted, with --yes too (PR #78 review).
        print(REMOTE_RESEED_WARNING)

    print(f"Seeding {host} ...")
    with SessionLocal() as db:
        seed(db)

        print(f"\n{len(EVENTS)} events, {len(ATTENDEES)} attendees, {len(VENUES)} venues, "
              f"{seeded_booking_count()} venue bookings, {len(VENUE_BLOCKS)} venue blocks:\n")
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
        for slug in ("tech-support", "safety-officer", "multi-role"):
            user = db.get(User, seed_id("user", slug))
            print(f"X-User-Id for {user.email}:\n  {user.id}\n")
        print("Registrations you can withdraw:")
        mine = db.scalars(select(Registration).where(Registration.attendee_id == calvin.id))
        for registration in mine:
            event = db.get(Event, registration.event_id)
            print(f"  {registration.status.value:<11} {event.name:<34} {registration.id}")

        try:
            seed_auth_logins(db, admin_from_settings(), settings.seed_auth_password.get_secret_value())
        except SeedAuthError as error:
            print(f"\n{error}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
