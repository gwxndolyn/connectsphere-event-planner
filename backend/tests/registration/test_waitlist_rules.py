"""US6a (SCRUM-10): the waitlist is offered, and joinable, only when the event is full and
waitlists are enabled for it (SCRUM-48, SCRUM-49). SCRUM-136: joining takes the logged-in attendee,
not a typed email (D3, D7)."""

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.event.models import Event, EventStatus
from app.main import app
from app.registration.models import AttendanceLog, Registration, RegistrationStatus
from app.seed import EVENTS, seed, seed_id
from tests.factories import NOW, make_attendee, make_event, make_registration

pytestmark = pytest.mark.anyio

def auth(attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


async def register(client: AsyncClient, event_id: uuid.UUID, attendee):
    return await client.post(f"/api/v1/events/{event_id}/registrations", json={}, headers=auth(attendee))


async def join(client: AsyncClient, event_id: uuid.UUID, attendee):
    """SCRUM-136: as the logged-in attendee, with no body."""
    return await client.post(f"/api/v1/events/{event_id}/waitlist", headers=auth(attendee))


def full_event(db: Session, **kwargs) -> Event:
    event = make_event(db, capacity=1, **kwargs)
    make_registration(db, event, make_attendee(db))
    return event


def rows_for(db: Session, event: Event, attendee) -> tuple[list, list]:
    registrations = list(
        db.scalars(
            select(Registration).where(Registration.event_id == event.id, Registration.attendee_email == attendee.email)
        )
    )
    logs = list(
        db.scalars(
            select(AttendanceLog).where(
                AttendanceLog.event_id == event.id,
                AttendanceLog.registration_id.in_([r.id for r in registrations]),
            )
        )
    )
    return registrations, logs


async def test_tc_us6a_01_full_event_with_waitlist_offers_it(client: AsyncClient, db: Session) -> None:
    event = full_event(db, waitlist_enabled=True)

    response = await register(client, event.id, make_attendee(db))

    assert response.status_code == 409
    assert response.json() == {
        "code": "EVENT_FULL",
        "waitlist_available": True,
        "message": "This event is full. You may join the waitlist.",
    }


async def test_tc_us6a_02_full_event_without_waitlist_does_not_offer_it(
    client: AsyncClient, db: Session
) -> None:
    event = full_event(db, waitlist_enabled=False)

    response = await register(client, event.id, make_attendee(db))

    assert response.status_code == 409
    assert response.json() == {
        "code": "EVENT_FULL",
        "waitlist_available": False,
        "message": "This event is full.",
    }


async def test_tc_us6a_03_joining_a_full_event_confirms_the_position(client: AsyncClient, db: Session) -> None:
    # Capacity 2: one confirmed seat, one held by an unexpired offer, so the event is full.
    event = make_event(db, capacity=2, waitlist_enabled=True)
    make_registration(db, event, make_attendee(db))
    make_registration(
        db, event, make_attendee(db), status=RegistrationStatus.OFFERED, offer_expires_at=NOW + timedelta(hours=1)
    )

    joiner = make_attendee(db)
    response = await join(client, event.id, joiner)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "waitlisted"
    assert body["position"] == 1
    registrations, logs = rows_for(db, event, joiner)
    assert [r.status for r in registrations] == [RegistrationStatus.WAITLISTED]
    assert [log.action for log in logs] == ["waitlisted"]


async def test_tc_us6a_04_event_with_places_refuses_the_waitlist(client: AsyncClient, db: Session) -> None:
    event = make_event(db, capacity=2, waitlist_enabled=True)
    make_registration(db, event, make_attendee(db))

    joiner = make_attendee(db)
    response = await join(client, event.id, joiner)

    assert response.status_code == 409
    assert response.json() == {"code": "SEATS_AVAILABLE"}


@pytest.mark.parametrize("capacity", [1, 2], ids=["full", "places remain"])
async def test_tc_us6a_05_waitlist_disabled_refuses_the_waitlist(
    client: AsyncClient, db: Session, capacity: int
) -> None:
    event = make_event(db, capacity=capacity, waitlist_enabled=False)
    make_registration(db, event, make_attendee(db))

    joiner = make_attendee(db)
    response = await join(client, event.id, joiner)

    assert response.status_code == 409
    assert response.json() == {"code": "WAITLIST_NOT_ENABLED"}


@pytest.mark.parametrize(
    ("capacity", "waitlist_enabled"),
    [(2, True), (1, False), (2, False)],
    ids=["places remain", "disabled", "places remain and disabled"],
)
async def test_tc_us6a_06_refused_joins_store_nothing(
    client: AsyncClient, db: Session, capacity: int, waitlist_enabled: bool
) -> None:
    event = make_event(db, capacity=capacity, waitlist_enabled=waitlist_enabled)
    make_registration(db, event, make_attendee(db))

    joiner = make_attendee(db)
    response = await join(client, event.id, joiner)

    assert response.status_code == 409
    assert rows_for(db, event, joiner) == ([], [])


async def test_tc_us6a_07_two_joins_get_positions_1_and_2(client: AsyncClient, db: Session) -> None:
    event = full_event(db, waitlist_enabled=True)

    app.dependency_overrides[get_now] = lambda: NOW
    first = await join(client, event.id, make_attendee(db))
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=1)
    second = await join(client, event.id, make_attendee(db))

    assert (first.status_code, first.json()["position"]) == (201, 1)
    assert (second.status_code, second.json()["position"]) == (201, 2)


@pytest.mark.parametrize(
    ("event_kwargs", "code"),
    [
        ({"status": EventStatus.CANCELLED}, "REGISTRATION_NOT_ENABLED"),
        ({"registration_enabled": False}, "REGISTRATION_NOT_ENABLED"),
        ({"registration_opens_at": NOW + timedelta(hours=1)}, "REGISTRATION_CLOSED"),
        ({"registration_closes_at": NOW}, "REGISTRATION_CLOSED"),
    ],
    ids=["cancelled", "registration disabled", "not open yet", "closed"],
)
async def test_tc_us6a_08_waitlist_follows_the_registration_gates(
    client: AsyncClient, db: Session, event_kwargs: dict, code: str
) -> None:
    event = full_event(db, waitlist_enabled=True, **event_kwargs)

    joiner = make_attendee(db)
    response = await join(client, event.id, joiner)

    assert response.status_code == 403
    assert response.json() == {"code": code}
    assert rows_for(db, event, joiner) == ([], [])


def test_tc_us6a_09_seed_enables_the_waitlist_only_on_the_full_event(db: Session) -> None:
    seed(db, now=NOW)

    enabled = {spec.slug: db.get(Event, seed_id("event", spec.slug)).waitlist_enabled for spec in EVENTS}

    assert enabled.pop("design-sprint-bootcamp") is True
    assert not any(enabled.values())


async def test_tc_us6a_11_a_logged_in_attendee_joins_with_no_email_typed(client: AsyncClient, db: Session) -> None:
    """SCRUM-136: the place is the logged-in attendee's, so it can accept an offer later (D3, D7)."""
    event = full_event(db, waitlist_enabled=True)
    joiner = make_attendee(db)

    response = await join(client, event.id, joiner)

    assert response.status_code == 201
    assert (response.json()["status"], response.json()["position"]) == ("waitlisted", 1)
    registrations, logs = rows_for(db, event, joiner)
    assert [(r.attendee_id, r.attendee_email, r.status) for r in registrations] == [
        (joiner.id, joiner.email, RegistrationStatus.WAITLISTED)
    ]
    assert [(log.action, log.attendee_id) for log in logs] == [("waitlisted", joiner.id)]


async def test_tc_us6a_12_joining_without_a_login_is_refused_and_stores_nothing(
    client: AsyncClient, db: Session
) -> None:
    event = full_event(db, waitlist_enabled=True)

    response = await client.post(f"/api/v1/events/{event.id}/waitlist", json={"email": "calvin.ng.2024@smu.edu.sg"})

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
    waitlisted = db.scalars(
        select(Registration).where(
            Registration.event_id == event.id, Registration.status == RegistrationStatus.WAITLISTED
        )
    ).all()
    assert waitlisted == []
    assert db.scalars(select(AttendanceLog).where(AttendanceLog.event_id == event.id)).all() == []


async def test_tc_us6a_13_a_waitlisted_attendee_accepts_the_freed_seat(client: AsyncClient, db: Session) -> None:
    """The gap SCRUM-136 closes: an offer made to a place joined from the board can be accepted."""
    event = make_event(db, capacity=1, waitlist_enabled=True)
    holder = make_attendee(db)
    held = make_registration(db, event, holder)
    joiner = make_attendee(db)
    joined = await join(client, event.id, joiner)
    assert joined.status_code == 201

    withdrawn = await client.post(f"/api/v1/registrations/{held.id}/withdraw", headers=auth(holder))
    assert withdrawn.status_code == 200
    place = db.get(Registration, uuid.UUID(joined.json()["registration_id"]))
    db.refresh(place)
    assert place.status == RegistrationStatus.OFFERED

    accepted = await client.post(f"/api/v1/registrations/{place.id}/accept", headers=auth(joiner))

    assert accepted.status_code == 200
    db.refresh(place)
    assert place.status == RegistrationStatus.CONFIRMED


async def test_tc_us6a_14_a_typed_email_in_the_body_is_ignored(client: AsyncClient, db: Session) -> None:
    """An old client's `{"email": ...}` doesn't make a place for someone else."""
    event = full_event(db, waitlist_enabled=True)
    joiner = make_attendee(db)

    response = await client.post(
        f"/api/v1/events/{event.id}/waitlist", json={"email": "someone.else@smu.edu.sg"}, headers=auth(joiner)
    )

    assert response.status_code == 201
    place = db.get(Registration, uuid.UUID(response.json()["registration_id"]))
    assert (place.attendee_id, place.attendee_email) == (joiner.id, joiner.email)
    typed = db.scalars(select(Registration).where(Registration.attendee_email == "someone.else@smu.edu.sg")).all()
    assert typed == []


async def test_tc_us6a_15_an_old_email_only_place_is_linked_to_its_attendee(client: AsyncClient, db: Session) -> None:
    """A place joined by email before SCRUM-136 has no attendee, so it couldn't accept an offer. When
    that attendee tries to join, the place becomes theirs and they're told they're already on it."""
    event = make_event(db, capacity=1, waitlist_enabled=True)
    holder = make_attendee(db)
    held = make_registration(db, event, holder)
    joiner = make_attendee(db)
    old = Registration(
        event_id=event.id,
        attendee_id=None,
        attendee_email=joiner.email,
        status=RegistrationStatus.WAITLISTED,
        waitlist_joined_at=NOW - timedelta(days=1),
    )
    db.add(old)
    db.flush()

    response = await join(client, event.id, joiner)

    assert response.status_code == 409
    assert response.json() == {"code": "ALREADY_REGISTERED"}
    db.refresh(old)
    assert old.attendee_id == joiner.id
    assert len(rows_for(db, event, joiner)[0]) == 1

    await client.post(f"/api/v1/registrations/{held.id}/withdraw", headers=auth(holder))
    db.refresh(old)
    assert old.status == RegistrationStatus.OFFERED

    accepted = await client.post(f"/api/v1/registrations/{old.id}/accept", headers=auth(joiner))

    assert accepted.status_code == 200
    db.refresh(old)
    assert old.status == RegistrationStatus.CONFIRMED
