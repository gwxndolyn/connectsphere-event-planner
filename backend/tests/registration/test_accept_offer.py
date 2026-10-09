from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.registration.models import AttendanceLog, Registration, RegistrationStatus
from app.registration.service import WAITLIST_OFFER_WINDOW, registration_service
from app.user.models import Attendee
from tests.factories import NOW, make_attendee, make_event, make_registration

pytestmark = pytest.mark.anyio


def auth(attendee: Attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


async def accept(client: AsyncClient, registration: Registration, attendee: Attendee | None):
    headers = auth(attendee) if attendee else {}
    return await client.post(f"/api/v1/registrations/{registration.id}/accept", headers=headers)


def full_event_with_offer(db: Session, *, offer_expires_at=NOW + WAITLIST_OFFER_WINDOW):
    """After a withdrawal from a one-seat event: B holds the offer, C is still queued."""
    event = make_event(db, capacity=1, start_at=NOW + timedelta(days=1))
    make_registration(db, event, make_attendee(db), status=RegistrationStatus.WITHDRAWN)
    b_attendee = make_attendee(db)
    b = make_registration(
        db,
        event,
        b_attendee,
        status=RegistrationStatus.OFFERED,
        waitlist_joined_at=NOW - timedelta(hours=3),
        offer_expires_at=offer_expires_at,
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


async def test_tc_us6b_01_offer_holder_accepts_and_is_registered(client: AsyncClient, db: Session) -> None:
    event, (b_attendee, b), (_, c) = full_event_with_offer(db)

    response = await accept(client, b, b_attendee)

    assert response.status_code == 200
    body = response.json()
    assert body["registration_id"] == str(b.id)
    assert body["status"] == "confirmed"
    assert body["event"]["name"] == event.name
    assert body["event"]["venue_name"] == event.venue_name
    db.refresh(b)
    assert b.status == RegistrationStatus.CONFIRMED
    assert b.offer_expires_at is None
    # The offer already held the seat, so taking it up changes nothing for anyone else.
    assert registration_service.seats_remaining(db, event, NOW) == 0
    assert registration_service.waitlist_position(db, c) == 1
    log = db.scalars(
        select(AttendanceLog).where(AttendanceLog.registration_id == b.id, AttendanceLog.action == "registered")
    ).one()
    assert log.occurred_at == NOW and log.note == "accepted waitlist offer"


async def test_tc_us6b_02_waitlisted_attendee_without_an_offer_is_refused(
    client: AsyncClient, db: Session
) -> None:
    _, _, (c_attendee, c) = full_event_with_offer(db)

    response = await accept(client, c, c_attendee)

    assert response.status_code == 409
    assert response.json() == {"code": "NO_ACTIVE_OFFER"}
    db.refresh(c)
    assert c.status == RegistrationStatus.WAITLISTED


@pytest.mark.parametrize(
    "status", [RegistrationStatus.CONFIRMED, RegistrationStatus.DECLINED, RegistrationStatus.WITHDRAWN]
)
async def test_tc_us6b_03_registrations_without_an_offer_are_refused(
    client: AsyncClient, db: Session, status: RegistrationStatus
) -> None:
    event = make_event(db, start_at=NOW + timedelta(days=1))
    attendee = make_attendee(db)
    registration = make_registration(db, event, attendee, status=status)

    response = await accept(client, registration, attendee)

    assert response.status_code == 409
    assert response.json() == {"code": "NO_ACTIVE_OFFER"}
    assert registration.status == status


async def test_tc_us6b_04_cannot_accept_another_attendees_offer(client: AsyncClient, db: Session) -> None:
    _, (_, b), (c_attendee, _) = full_event_with_offer(db)

    response = await accept(client, b, c_attendee)

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}
    db.refresh(b)
    assert b.status == RegistrationStatus.OFFERED


async def test_tc_us6b_05_a_lapsed_offer_cannot_be_accepted(client: AsyncClient, db: Session) -> None:
    _, (b_attendee, b), _ = full_event_with_offer(db, offer_expires_at=NOW)

    response = await accept(client, b, b_attendee)

    assert response.status_code == 409
    assert response.json() == {"code": "OFFER_EXPIRED"}
    db.refresh(b)
    assert b.status == RegistrationStatus.OFFERED


async def test_tc_us6b_06_accepted_place_shows_under_confirmed(client: AsyncClient, db: Session) -> None:
    event, (b_attendee, b), _ = full_event_with_offer(db)
    await accept(client, b, b_attendee)

    response = await client.get("/api/v1/me/registrations", headers=auth(b_attendee))

    assert response.status_code == 200
    assert [row["registration_id"] for row in response.json()["confirmed"]] == [str(b.id)]
    assert response.json()["waitlisted"] == []


async def test_tc_us6b_07_needs_identity_and_an_unstarted_event(client: AsyncClient, db: Session) -> None:
    event, (b_attendee, b), _ = full_event_with_offer(db)

    assert (await accept(client, b, None)).status_code == 401

    event.start_at = NOW - timedelta(minutes=1)
    event.end_at = NOW + timedelta(hours=1)
    db.flush()
    started = await accept(client, b, b_attendee)
    assert started.status_code == 403
    assert started.json() == {"code": "EVENT_STARTED"}
    db.refresh(b)
    assert b.status == RegistrationStatus.OFFERED


async def test_tc_us6b_08_the_next_attendee_sees_the_offer_on_screen(
    client: AsyncClient, db: Session
) -> None:
    """SCRUM-50: a withdrawal from a full event puts the place in the next attendee's own list."""
    event = make_event(db, capacity=1, start_at=NOW + timedelta(days=1))
    leaver = make_attendee(db)
    leaver_registration = make_registration(db, event, leaver)
    waiting = make_attendee(db)
    queued = make_registration(
        db, event, waiting, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW - timedelta(hours=1)
    )

    before = (await client.get("/api/v1/me/registrations", headers=auth(waiting))).json()
    await client.post(f"/api/v1/registrations/{leaver_registration.id}/withdraw", headers=auth(leaver))
    after = (await client.get("/api/v1/me/registrations", headers=auth(waiting))).json()

    assert [row["registration_id"] for row in before["waitlisted"]] == [str(queued.id)]
    assert before["offered"] == []
    assert after["waitlisted"] == []
    assert len(after["offered"]) == 1
    offer = after["offered"][0]
    assert offer["registration_id"] == str(queued.id)
    assert offer["event_name"] == event.name
    assert datetime.fromisoformat(offer["offer_expires_at"]) == NOW + WAITLIST_OFFER_WINDOW


async def test_tc_us6b_09_the_notice_carries_what_is_needed_to_accept(
    client: AsyncClient, db: Session, notifier
) -> None:
    event = make_event(db, capacity=1, start_at=NOW + timedelta(days=1))
    leaver = make_attendee(db)
    leaver_registration = make_registration(db, event, leaver)
    waiting = make_attendee(db)
    make_registration(
        db, event, waiting, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW - timedelta(hours=1)
    )

    await client.post(f"/api/v1/registrations/{leaver_registration.id}/withdraw", headers=auth(leaver))
    notice = notifier.offers[0]
    accepted = await client.post(
        f"/api/v1/registrations/{notice['registration_id']}/accept", headers=auth(waiting)
    )

    assert notice["email"] == waiting.email
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "confirmed"


async def test_tc_us6b_10_a_lapsed_offer_is_not_listed(client: AsyncClient, db: Session) -> None:
    _, (b_attendee, _), _ = full_event_with_offer(db, offer_expires_at=NOW)

    response = await client.get("/api/v1/me/registrations", headers=auth(b_attendee))

    assert response.json()["offered"] == []
    assert response.json()["waitlisted"] == []
