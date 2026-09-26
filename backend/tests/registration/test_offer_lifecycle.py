from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.registration.models import AttendanceLog, Registration, RegistrationStatus
from app.registration.service import WAITLIST_OFFER_WINDOW, registration_service
from app.user.models import Attendee
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_attendee, make_event, make_registration

pytestmark = pytest.mark.anyio


def auth(attendee: Attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


def event_with_outstanding_offer(db: Session):
    """The state a withdrawal leaves behind: B holds an offer, C is next in the queue."""
    event = make_event(db, capacity=1, start_at=NOW + timedelta(days=1))
    holder = make_attendee(db)
    make_registration(db, event, holder, status=RegistrationStatus.WITHDRAWN)

    b_attendee = make_attendee(db)
    b = make_registration(
        db,
        event,
        b_attendee,
        status=RegistrationStatus.OFFERED,
        waitlist_joined_at=NOW - timedelta(hours=3),
        offer_expires_at=NOW + WAITLIST_OFFER_WINDOW,
    )
    c_attendee = make_attendee(db)
    c = make_registration(
        db,
        event,
        c_attendee,
        status=RegistrationStatus.WAITLISTED,
        waitlist_joined_at=NOW - timedelta(hours=2),
    )
    return event, (b_attendee, b), (c_attendee, c)


async def test_tc_us7_10_an_expired_offer_moves_to_the_next_person(
    client: AsyncClient, db: Session
) -> None:
    event, (_, b), (_, c) = event_with_outstanding_offer(db)

    response = await client.post(
        f"/api/v1/registrations/{b.id}/expire-offer", headers=auth(make_attendee(db))
    )

    assert response.status_code == 200
    assert response.json()["status"] == "expired"
    assert response.json()["offer_passed_on"] is True
    assert b.status == RegistrationStatus.EXPIRED
    assert c.status == RegistrationStatus.OFFERED
    assert c.offer_expires_at == NOW + WAITLIST_OFFER_WINDOW
    # Both state changes are recorded (TC-X-03).
    actions = db.scalars(
        select(AttendanceLog.action)
        .where(AttendanceLog.event_id == event.id)
        .order_by(AttendanceLog.id)
    ).all()
    assert list(actions) == ["offer_expired", "offered"]


async def test_tc_us7_11_a_declined_offer_moves_on_immediately(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    event, (b_attendee, b), (c_attendee, c) = event_with_outstanding_offer(db)

    response = await client.post(f"/api/v1/registrations/{b.id}/decline", headers=auth(b_attendee))

    assert response.status_code == 200
    assert response.json()["status"] == "declined"
    assert b.status == RegistrationStatus.DECLINED
    # No waiting for the window to lapse.
    assert c.status == RegistrationStatus.OFFERED
    assert [offer["email"] for offer in notifier.offers] == [c_attendee.email]
    actions = db.scalars(
        select(AttendanceLog.action)
        .where(AttendanceLog.event_id == event.id)
        .order_by(AttendanceLog.id)
    ).all()
    assert list(actions) == ["declined", "offered"]


async def test_the_seat_returns_to_the_pool_when_the_queue_is_empty(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    event = make_event(db, capacity=1, start_at=NOW + timedelta(days=1))
    attendee = make_attendee(db)
    offered = make_registration(
        db,
        event,
        attendee,
        status=RegistrationStatus.OFFERED,
        waitlist_joined_at=NOW - timedelta(hours=1),
        offer_expires_at=NOW + WAITLIST_OFFER_WINDOW,
    )

    response = await client.post(
        f"/api/v1/registrations/{offered.id}/expire-offer", headers=auth(attendee)
    )

    body = response.json()
    assert body["offer_passed_on"] is False
    assert body["seats_remaining"] == 1
    assert notifier.offers == []


async def test_cannot_decline_another_attendees_offer(client: AsyncClient, db: Session) -> None:
    _, (_, b), _ = event_with_outstanding_offer(db)

    response = await client.post(
        f"/api/v1/registrations/{b.id}/decline", headers=auth(make_attendee(db))
    )

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}
    assert b.status == RegistrationStatus.OFFERED


@pytest.mark.parametrize("action", ["expire-offer", "decline"])
async def test_releasing_a_registration_that_holds_no_offer_is_refused(
    client: AsyncClient, db: Session, action: str
) -> None:
    event = make_event(db, start_at=NOW + timedelta(days=1))
    attendee = make_attendee(db)
    confirmed = make_registration(db, event, attendee)

    response = await client.post(
        f"/api/v1/registrations/{confirmed.id}/{action}", headers=auth(attendee)
    )

    assert response.status_code == 409
    assert response.json() == {"code": "NO_ACTIVE_OFFER"}
    assert confirmed.status == RegistrationStatus.CONFIRMED


async def test_an_expired_offer_does_not_hold_a_seat(client: AsyncClient, db: Session) -> None:
    event, (_, b), _ = event_with_outstanding_offer(db)
    assert registration_service.seats_remaining(db, event, NOW) == 0

    await client.post(f"/api/v1/registrations/{b.id}/expire-offer", headers=auth(make_attendee(db)))

    # C now holds it instead, so the count is unchanged — but B's row no longer counts.
    held_by_c = db.scalars(
        select(Registration).where(
            Registration.event_id == event.id, Registration.status == RegistrationStatus.OFFERED
        )
    ).all()
    assert len(held_by_c) == 1
    assert registration_service.seats_remaining(db, event, NOW) == 0
