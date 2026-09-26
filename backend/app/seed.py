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
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.event.models import DeliveryMode, Event, EventStatus
from app.registration.models import Registration, RegistrationStatus
from app.user.models import Attendee

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


def upsert_attendee(db: Session, email: str) -> Attendee:
    attendee_id = seed_id("attendee", email)
    attendee = db.get(Attendee, attendee_id)
    if attendee is None:
        attendee = Attendee(id=attendee_id, email=email)
        db.add(attendee)
    return attendee


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
    }
    event = db.get(Event, event_id)
    if event is None:
        event = Event(id=event_id, **values)
        db.add(event)
    else:
        for key, value in values.items():
            setattr(event, key, value)
    return event


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

        print(f"\n{len(EVENTS)} events, {len(ATTENDEES)} attendees:\n")
        for spec in EVENTS:
            print(f"  {spec.name:<34} {spec.note}")

        calvin = db.get(Attendee, seed_id("attendee", ATTENDEES[0]))
        print(f"\nX-Attendee-Id for {calvin.email}:\n  {calvin.id}\n")
        print("Registrations you can withdraw:")
        mine = db.scalars(select(Registration).where(Registration.attendee_id == calvin.id))
        for registration in mine:
            event = db.get(Event, registration.event_id)
            print(f"  {registration.status.value:<11} {event.name:<34} {registration.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
