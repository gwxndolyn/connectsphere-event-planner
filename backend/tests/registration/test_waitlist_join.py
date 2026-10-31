import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.main import app
from app.registration.models import Registration, RegistrationStatus
from tests.factories import NOW, make_attendee, make_event, make_registration

pytestmark = pytest.mark.anyio


def waitlist_url(event_id: uuid.UUID) -> str:
    return f"/api/v1/events/{event_id}/waitlist"


def auth(attendee) -> dict[str, str]:
    # SCRUM-136: joining a waitlist takes the logged-in attendee, not a typed email (D3, D7).
    return {"X-Attendee-Id": str(attendee.id)}


async def test_tc_us3_12_joining_the_waitlist_after_event_full_creates_a_waitlisted_row(
    client: AsyncClient, db: Session
) -> None:
    event = make_event(db, capacity=1)
    make_registration(db, event, make_attendee(db))
    attendee = make_attendee(db)

    response = await client.post(waitlist_url(event.id), headers=auth(attendee))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "waitlisted"
    assert body["position"] == 1
    registration = db.scalars(
        select(Registration).where(Registration.event_id == event.id, Registration.attendee_id == attendee.id)
    ).one()
    assert registration.status == RegistrationStatus.WAITLISTED
    assert registration.waitlist_joined_at is not None


async def test_tc_us3_13_waitlist_positions_are_derived_from_join_order(
    client: AsyncClient, db: Session
) -> None:
    """The `client` fixture freezes `now` to one constant for the whole test, so three calls
    in a row would otherwise tie on `waitlist_joined_at` and fall back to a random UUID
    tie-break. Stagger the clock between calls, the way real, non-simultaneous requests would."""
    event = make_event(db, capacity=0)
    a, b, c = make_attendee(db), make_attendee(db), make_attendee(db)

    app.dependency_overrides[get_now] = lambda: NOW
    first = await client.post(waitlist_url(event.id), headers=auth(a))
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=1)
    second = await client.post(waitlist_url(event.id), headers=auth(b))
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=2)
    third = await client.post(waitlist_url(event.id), headers=auth(c))

    assert first.json()["position"] == 1
    assert second.json()["position"] == 2
    assert third.json()["position"] == 3


async def test_joining_the_waitlist_stores_the_attendee_and_their_own_email(
    client: AsyncClient, db: Session
) -> None:
    event = make_event(db, capacity=0)
    attendee = make_attendee(db)

    response = await client.post(waitlist_url(event.id), headers=auth(attendee))

    assert response.status_code == 201
    registration = db.scalars(select(Registration).where(Registration.event_id == event.id)).one()
    assert (registration.attendee_id, registration.attendee_email) == (attendee.id, attendee.email)


async def test_duplicate_waitlist_join_is_refused(client: AsyncClient, db: Session) -> None:
    event = make_event(db, capacity=0)
    attendee = make_attendee(db)
    await client.post(waitlist_url(event.id), headers=auth(attendee))

    response = await client.post(waitlist_url(event.id), headers=auth(attendee))

    assert response.status_code == 409
    assert response.json() == {"code": "ALREADY_REGISTERED"}


async def test_unknown_event_id_is_not_found(client: AsyncClient, db: Session) -> None:
    response = await client.post(waitlist_url(uuid.uuid4()), headers=auth(make_attendee(db)))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}
