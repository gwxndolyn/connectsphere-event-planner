import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.registration.models import AttendanceLog, Registration, RegistrationStatus
from app.registration.service import registration_service
from app.user.models import Attendee
from tests.factories import NOW, make_attendee, make_event, make_registration

pytestmark = pytest.mark.anyio


def auth(attendee: Attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


def withdraw_url(registration: Registration) -> str:
    return f"/api/v1/registrations/{registration.id}/withdraw"


def log_entries(db: Session, registration: Registration) -> list[AttendanceLog]:
    return list(
        db.scalars(select(AttendanceLog).where(AttendanceLog.registration_id == registration.id)).all()
    )


async def test_tc_us7_01_withdraws_a_confirmed_registration(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db, start_at=NOW + timedelta(days=1))
    registration = make_registration(db, event, attendee)

    response = await client.post(withdraw_url(registration), headers=auth(attendee))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "withdrawn"
    assert body["event_name"] == event.name
    assert datetime.fromisoformat(body["withdrawn_at"]) == NOW
    assert registration.status == RegistrationStatus.WITHDRAWN


async def test_tc_us7_02_cannot_withdraw_another_attendees_registration(
    client: AsyncClient, db: Session
) -> None:
    attendee_a = make_attendee(db)
    attendee_b = make_attendee(db)
    event = make_event(db)
    registration_b = make_registration(db, event, attendee_b)

    response = await client.post(withdraw_url(registration_b), headers=auth(attendee_a))

    # 404 rather than 403: the response must not reveal that B's registration exists (TC-X-04).
    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}
    assert registration_b.status == RegistrationStatus.CONFIRMED
    assert log_entries(db, registration_b) == []


async def test_tc_us7_03_cannot_withdraw_after_the_event_has_started(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    event = make_event(db, start_at=NOW - timedelta(hours=1))
    registration = make_registration(db, event, attendee)

    response = await client.post(withdraw_url(registration), headers=auth(attendee))

    assert response.status_code == 403
    assert response.json() == {"code": "EVENT_STARTED"}
    assert registration.status == RegistrationStatus.CONFIRMED
    assert registration.withdrawn_at is None
    assert log_entries(db, registration) == []


async def test_tc_us7_04_can_withdraw_one_minute_before_the_event_starts(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    event = make_event(db, start_at=NOW + timedelta(minutes=1))
    registration = make_registration(db, event, attendee)

    response = await client.post(withdraw_url(registration), headers=auth(attendee))

    assert response.status_code == 200
    assert registration.status == RegistrationStatus.WITHDRAWN


async def test_withdrawal_at_the_exact_start_time_is_refused(client: AsyncClient, db: Session) -> None:
    """The cutoff is start_at itself: everything strictly before it is allowed, start_at is not."""
    attendee = make_attendee(db)
    event = make_event(db, start_at=NOW)
    registration = make_registration(db, event, attendee)

    response = await client.post(withdraw_url(registration), headers=auth(attendee))

    assert response.status_code == 403
    assert response.json() == {"code": "EVENT_STARTED"}


async def test_tc_us7_05_second_withdrawal_is_refused_and_logged_only_once(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    event = make_event(db)
    registration = make_registration(db, event, attendee)

    first = await client.post(withdraw_url(registration), headers=auth(attendee))
    second = await client.post(withdraw_url(registration), headers=auth(attendee))

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json() == {"code": "ALREADY_WITHDRAWN"}
    assert len(log_entries(db, registration)) == 1


async def test_tc_us7_06_withdrawal_with_an_empty_waitlist_frees_a_seat(
    client: AsyncClient, db: Session
) -> None:
    event = make_event(db, capacity=10)
    attendees = [make_attendee(db) for _ in range(10)]
    registrations = [make_registration(db, event, attendee) for attendee in attendees]

    response = await client.post(withdraw_url(registrations[0]), headers=auth(attendees[0]))

    assert response.status_code == 200
    assert response.json()["seats_remaining"] == 1
    # No waitlist, so no offer is created and nobody is notified.
    offered = db.scalars(
        select(Registration).where(
            Registration.event_id == event.id, Registration.status == RegistrationStatus.OFFERED
        )
    ).all()
    assert not offered


async def test_tc_us7_12_withdrawal_is_recorded_with_a_timestamp(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    event = make_event(db)
    registration = make_registration(db, event, attendee)

    await client.post(withdraw_url(registration), headers=auth(attendee))

    assert registration.withdrawn_at == NOW
    entries = log_entries(db, registration)
    assert len(entries) == 1
    assert entries[0].action == "withdrawn"
    assert entries[0].occurred_at == NOW
    assert entries[0].event_id == event.id
    assert entries[0].attendee_id == attendee.id


async def test_tc_us7_14_waitlisted_attendee_leaves_and_the_queue_moves_up(
    client: AsyncClient, db: Session
) -> None:
    event = make_event(db, capacity=1)
    make_registration(db, event, make_attendee(db))  # the one confirmed seat

    first, second, third = (
        make_registration(
            db,
            event,
            make_attendee(db),
            status=RegistrationStatus.WAITLISTED,
            waitlist_joined_at=NOW - timedelta(hours=hours),
        )
        for hours in (3, 2, 1)
    )
    second_attendee = db.get(Attendee, second.attendee_id)

    response = await client.post(withdraw_url(second), headers=auth(second_attendee))

    assert response.status_code == 200
    assert second.status == RegistrationStatus.WITHDRAWN
    assert registration_service.waitlist_position(db, first) == 1
    assert registration_service.waitlist_position(db, third) == 2
    # Leaving a waitlist frees no seat: the confirmed attendee still holds the only one.
    assert response.json()["seats_remaining"] == 0


async def test_withdraw_requires_an_attendee_header(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db)
    registration = make_registration(db, event, attendee)

    response = await client.post(withdraw_url(registration))

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
    assert registration.status == RegistrationStatus.CONFIRMED


async def test_unknown_registration_id_is_not_found(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)

    response = await client.post(f"/api/v1/registrations/{uuid.uuid4()}/withdraw", headers=auth(attendee))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}


async def test_an_offered_seat_cannot_be_withdrawn(client: AsyncClient, db: Session) -> None:
    """Not in the spec's error table: an offer is released by declining it (SCRUM-37)."""
    attendee = make_attendee(db)
    event = make_event(db)
    registration = make_registration(
        db,
        event,
        attendee,
        status=RegistrationStatus.OFFERED,
        offer_expires_at=NOW + timedelta(hours=24),
    )

    response = await client.post(withdraw_url(registration), headers=auth(attendee))

    assert response.status_code == 409
    assert response.json() == {"code": "REGISTRATION_NOT_ACTIVE"}
