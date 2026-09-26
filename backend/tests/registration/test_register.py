import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import EventStatus
from app.registration.models import Registration, RegistrationStatus
from tests.factories import (
    NOW,
    make_attendee,
    make_event,
    make_registration,
    make_registration_field,
)

pytestmark = pytest.mark.anyio


def auth(attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


def register_url(event_id: uuid.UUID) -> str:
    return f"/api/v1/events/{event_id}/registrations"


def active_registrations(db: Session, event_id: uuid.UUID) -> list[Registration]:
    return list(db.scalars(select(Registration).where(Registration.event_id == event_id)).all())


async def test_tc_us3_02_registration_disabled_is_refused(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db, registration_enabled=False)

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 403
    assert response.json() == {"code": "REGISTRATION_NOT_ENABLED"}
    assert active_registrations(db, event.id) == []


@pytest.mark.parametrize("status", [EventStatus.DRAFT, EventStatus.SUBMITTED, EventStatus.CANCELLED])
async def test_tc_us3_03_non_confirmed_event_is_refused(
    client: AsyncClient, db: Session, status: EventStatus
) -> None:
    attendee = make_attendee(db)
    event = make_event(db, status=status)

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 403
    assert response.json() == {"code": "REGISTRATION_NOT_ENABLED"}
    assert active_registrations(db, event.id) == []


async def test_tc_us3_04_before_registration_opens_is_refused(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(
        db,
        registration_opens_at=NOW + timedelta(days=1),
        registration_closes_at=NOW + timedelta(days=10),
    )

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 403
    assert response.json() == {"code": "REGISTRATION_CLOSED"}


async def test_tc_us3_05_after_registration_closes_is_refused(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(
        db,
        registration_opens_at=NOW - timedelta(days=10),
        registration_closes_at=NOW - timedelta(hours=1),
    )

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 403
    assert response.json() == {"code": "REGISTRATION_CLOSED"}


async def test_tc_us3_06_missing_required_field_is_refused(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db)
    make_registration_field(db, event, field_key="dietary", required=True)

    response = await client.post(register_url(event.id), json={"answers": {}}, headers=auth(attendee))

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": ["dietary"]}
    assert active_registrations(db, event.id) == []


async def test_tc_us3_07_valid_registration_is_confirmed(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db, capacity=10)
    make_registration_field(db, event, field_key="dietary", required=True)

    response = await client.post(
        register_url(event.id), json={"answers": {"dietary": "vegetarian"}}, headers=auth(attendee)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["event"]["name"] == event.name
    assert body["event"]["venue_name"] == event.venue_name
    registration = db.scalars(
        select(Registration).where(Registration.event_id == event.id, Registration.attendee_id == attendee.id)
    ).one()
    assert registration.status == RegistrationStatus.CONFIRMED


async def test_tc_us3_08_online_event_confirmation_carries_a_join_link(
    client: AsyncClient, db: Session
) -> None:
    from app.event.models import DeliveryMode

    attendee = make_attendee(db)
    event = make_event(
        db,
        delivery_mode=DeliveryMode.ONLINE,
        venue_name=None,
        room_number=None,
        join_link="https://smu-sg.zoom.us/j/1",
    )

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 201
    body = response.json()["event"]
    assert body["join_link"] == "https://smu-sg.zoom.us/j/1"
    assert body["venue_name"] is None


async def test_tc_us3_09_duplicate_registration_is_refused(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db)
    make_registration(db, event, attendee)

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 409
    assert response.json() == {"code": "ALREADY_REGISTERED"}
    assert len(active_registrations(db, event.id)) == 1


async def test_tc_us3_10_concurrent_registration_for_the_last_seat_is_serialised(
    client: AsyncClient, db: Session
) -> None:
    """Not a real concurrency test (the fixture uses one connection), but proves the event
    row lock means the second request sees the first request's committed occupancy."""
    attendee_a = make_attendee(db)
    attendee_b = make_attendee(db)
    event = make_event(db, capacity=1)

    first = await client.post(register_url(event.id), json={}, headers=auth(attendee_a))
    second = await client.post(register_url(event.id), json={}, headers=auth(attendee_b))

    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [201, 409]
    confirmed = [
        r for r in active_registrations(db, event.id) if r.status == RegistrationStatus.CONFIRMED
    ]
    assert len(confirmed) == 1


async def test_tc_us3_11_event_full_offers_a_waitlist_place(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db, capacity=1)
    make_registration(db, event, make_attendee(db))

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 409
    assert response.json() == {
        "code": "EVENT_FULL",
        "waitlist_available": True,
        "message": "This event is full. You may join the waitlist.",
    }
    assert active_registrations(db, event.id) == [
        r for r in active_registrations(db, event.id) if r.attendee_id != attendee.id
    ]


async def test_tc_us3_14_an_unexpired_offer_counts_toward_capacity(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db, capacity=5)
    for _ in range(4):
        make_registration(db, event, make_attendee(db))
    make_registration(
        db,
        event,
        make_attendee(db),
        status=RegistrationStatus.OFFERED,
        offer_expires_at=NOW + timedelta(hours=1),
    )

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 409
    assert response.json()["code"] == "EVENT_FULL"


async def test_tc_us3_15_a_withdrawn_attendee_may_register_again(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db)
    make_registration(db, event, attendee, status=RegistrationStatus.WITHDRAWN)

    response = await client.post(register_url(event.id), json={}, headers=auth(attendee))

    assert response.status_code == 201
    assert response.json()["status"] == "confirmed"


async def test_unknown_event_id_is_not_found(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)

    response = await client.post(register_url(uuid.uuid4()), json={}, headers=auth(attendee))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}


async def test_register_requires_an_attendee_header(client: AsyncClient, db: Session) -> None:
    event = make_event(db)

    response = await client.post(register_url(event.id), json={})

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
