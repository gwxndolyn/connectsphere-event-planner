"""Core feature "Notification System": an attendee is told when their registration goes through and when
their withdrawal does (registration updates). Best effort, after the commit, like every other notice."""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.registration.models import Registration, RegistrationStatus
from tests.conftest import FakeNotifier
from tests.factories import make_attendee, make_event, make_registration

pytestmark = pytest.mark.anyio


def auth(attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


async def test_tc_us3_19_registering_tells_the_attendee(client: AsyncClient, db: Session, notifier: FakeNotifier) -> None:
    event = make_event(db, name="Alumni night")
    attendee = make_attendee(db)

    response = await client.post(f"/api/v1/events/{event.id}/registrations", headers=auth(attendee), json={"answers": {}})

    assert response.status_code == 201
    assert notifier.registration_changes == [
        {"email": attendee.email, "event_id": event.id, "event_name": "Alumni night", "change": "registered"}
    ]


async def test_tc_us3_20_a_refused_registration_tells_no_one(client: AsyncClient, db: Session, notifier: FakeNotifier) -> None:
    event = make_event(db, registration_enabled=False)
    attendee = make_attendee(db)

    response = await client.post(f"/api/v1/events/{event.id}/registrations", headers=auth(attendee), json={"answers": {}})

    assert response.status_code == 403
    assert notifier.registration_changes == []


async def test_tc_us3_21_a_failing_notifier_does_not_undo_the_registration(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    event = make_event(db)
    attendee = make_attendee(db)
    notifier.fail = True

    response = await client.post(f"/api/v1/events/{event.id}/registrations", headers=auth(attendee), json={"answers": {}})

    assert response.status_code == 201
    assert db.get(Registration, response.json()["registration_id"]).status == RegistrationStatus.CONFIRMED


async def test_tc_us7_27_withdrawing_tells_the_attendee(client: AsyncClient, db: Session, notifier: FakeNotifier) -> None:
    event = make_event(db, name="Alumni night")
    attendee = make_attendee(db)
    registration = make_registration(db, event, attendee)

    response = await client.post(f"/api/v1/registrations/{registration.id}/withdraw", headers=auth(attendee))

    assert response.status_code == 200
    assert notifier.registration_changes == [
        {"email": registration.attendee_email, "event_id": event.id, "event_name": "Alumni night", "change": "withdrawn"}
    ]


async def test_tc_us7_28_a_refused_withdrawal_tells_no_one(client: AsyncClient, db: Session, notifier: FakeNotifier) -> None:
    event = make_event(db)
    attendee = make_attendee(db)
    registration = make_registration(db, event, attendee, status=RegistrationStatus.WITHDRAWN)

    response = await client.post(f"/api/v1/registrations/{registration.id}/withdraw", headers=auth(attendee))

    assert response.status_code == 409
    assert notifier.registration_changes == []


async def test_tc_us7_29_a_failing_notifier_does_not_undo_the_withdrawal(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    event = make_event(db)
    attendee = make_attendee(db)
    registration = make_registration(db, event, attendee)
    notifier.fail = True

    response = await client.post(f"/api/v1/registrations/{registration.id}/withdraw", headers=auth(attendee))

    assert response.status_code == 200
    db.refresh(registration)
    assert registration.status == RegistrationStatus.WITHDRAWN
