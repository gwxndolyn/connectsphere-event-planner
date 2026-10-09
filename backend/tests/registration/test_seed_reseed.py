"""Reseeding after someone used the app (SCRUM-79): the seed resets *its* registration rows, so
any other active row for the same (event, attendee) must be withdrawn first, or the second active
row breaks `registrations_one_active_per_attendee`."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import Event
from app.registration.models import ACTIVE_STATUSES, Registration, RegistrationStatus
from app.seed import seed, seed_id
from app.user.models import Attendee
from tests.factories import NOW, make_registration

LATER = NOW + timedelta(hours=1)


def seeded(db: Session, event_slug: str, email: str) -> tuple[Event, Attendee, Registration]:
    event = db.get(Event, seed_id("event", event_slug))
    attendee = db.get(Attendee, seed_id("attendee", email))
    return event, attendee, db.get(Registration, seed_id("registration", f"{event.id}:{attendee.id}"))


def active_rows(db: Session, event: Event, attendee: Attendee) -> list[Registration]:
    return list(
        db.scalars(
            select(Registration).where(
                Registration.event_id == event.id,
                Registration.attendee_id == attendee.id,
                Registration.status.in_(ACTIVE_STATUSES),
            )
        )
    )


def test_reseed_withdraws_a_registration_made_through_the_app(db: Session) -> None:
    seed(db, now=NOW)
    event, calvin, seat = seeded(db, "tech-talk-agile", "calvin.ng.2024@smu.edu.sg")
    # In the app: Calvin withdraws the seeded seat, then registers again, which makes a new row.
    seat.status = RegistrationStatus.WITHDRAWN
    seat.withdrawn_at = NOW
    db.flush()
    again = make_registration(db, event, calvin)

    seed(db, now=LATER)

    db.refresh(seat)
    db.refresh(again)
    assert seat.status == RegistrationStatus.CONFIRMED
    assert (again.status, again.withdrawn_at) == (RegistrationStatus.WITHDRAWN, LATER)
    assert [row.id for row in active_rows(db, event, calvin)] == [seat.id]


def test_reseed_withdraws_an_extra_waitlist_entry(db: Session) -> None:
    seed(db, now=NOW)
    event, sofia, place = seeded(db, "design-sprint-bootcamp", "sofia.lim.2024@smu.edu.sg")
    # Sofia left the queue and rejoined it through the app.
    place.status = RegistrationStatus.WITHDRAWN
    db.flush()
    rejoined = make_registration(db, event, sofia, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW)

    seed(db, now=LATER)

    db.refresh(rejoined)
    assert rejoined.status == RegistrationStatus.WITHDRAWN
    assert [row.id for row in active_rows(db, event, sofia)] == [place.id]


def test_reseed_leaves_registrations_the_seed_does_not_own_alone(db: Session) -> None:
    seed(db, now=NOW)
    # Arjun has no seeded Tech Talk seat, so his app registration isn't the seed's to touch.
    tech_talk = db.get(Event, seed_id("event", "tech-talk-agile"))
    arjun = make_registration(db, tech_talk, db.get(Attendee, seed_id("attendee", "arjun.rao.2024@smu.edu.sg")))

    seed(db, now=LATER)

    db.refresh(arjun)
    assert arjun.status == RegistrationStatus.CONFIRMED
