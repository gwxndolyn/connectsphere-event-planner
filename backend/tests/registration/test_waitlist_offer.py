from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import Event
from app.registration.models import AttendanceLog, Registration, RegistrationStatus
from app.registration.service import WAITLIST_OFFER_WINDOW, registration_service
from app.user.models import Attendee
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_attendee, make_event, make_registration

pytestmark = pytest.mark.anyio


def auth(attendee: Attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


def full_event_with_waitlist(db: Session, capacity: int = 2) -> tuple[Event, list, list]:
    """A full event with a queue behind it: every seat confirmed, two people waiting."""
    event = make_event(db, capacity=capacity, start_at=NOW + timedelta(days=1))
    holders = []
    for _ in range(capacity):
        attendee = make_attendee(db)
        holders.append((attendee, make_registration(db, event, attendee)))

    queue = []
    for hours_ago in (3, 2):
        attendee = make_attendee(db)
        queue.append(
            (
                attendee,
                make_registration(
                    db,
                    event,
                    attendee,
                    status=RegistrationStatus.WAITLISTED,
                    waitlist_joined_at=NOW - timedelta(hours=hours_ago),
                ),
            )
        )
    return event, holders, queue


async def test_tc_us7_07_freed_seat_is_offered_to_the_head_of_the_waitlist(
    client: AsyncClient, db: Session
) -> None:
    event, holders, queue = full_event_with_waitlist(db)
    (leaver, leaver_registration) = holders[0]
    (_, first_in_queue) = queue[0]
    (_, second_in_queue) = queue[1]

    response = await client.post(
        f"/api/v1/registrations/{leaver_registration.id}/withdraw", headers=auth(leaver)
    )

    assert response.status_code == 200
    assert first_in_queue.status == RegistrationStatus.OFFERED
    assert first_in_queue.offer_expires_at == NOW + WAITLIST_OFFER_WINDOW
    assert second_in_queue.status == RegistrationStatus.WAITLISTED
    assert registration_service.waitlist_position(db, second_in_queue) == 1
    # The offer holds the seat, so nothing is free for anyone else.
    assert response.json()["seats_remaining"] == 0


async def test_tc_us7_08_the_offered_attendee_is_notified(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    event, holders, queue = full_event_with_waitlist(db)
    (leaver, leaver_registration) = holders[0]
    (first_attendee, _) = queue[0]

    await client.post(
        f"/api/v1/registrations/{leaver_registration.id}/withdraw", headers=auth(leaver)
    )

    assert len(notifier.offers) == 1
    assert notifier.offers[0] == {
        "email": first_attendee.email,
        "event_name": event.name,
        "expires_at": NOW + WAITLIST_OFFER_WINDOW,
    }


async def test_tc_us7_09_the_seat_is_not_available_while_an_offer_stands(
    client: AsyncClient, db: Session
) -> None:
    event, holders, queue = full_event_with_waitlist(db)
    (leaver, leaver_registration) = holders[0]
    (_, second_in_queue) = queue[1]

    await client.post(
        f"/api/v1/registrations/{leaver_registration.id}/withdraw", headers=auth(leaver)
    )

    # An unexpired offer counts towards occupancy, so the next person can't take the seat.
    assert registration_service.seats_remaining(db, event, NOW) == 0
    assert second_in_queue.status == RegistrationStatus.WAITLISTED
    # It only frees up once the window lapses — expiry itself is SCRUM-37.
    assert registration_service.seats_remaining(db, event, NOW + WAITLIST_OFFER_WINDOW) == 1


async def test_tc_us7_15_a_failed_notification_does_not_roll_back_the_withdrawal(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    event, holders, queue = full_event_with_waitlist(db)
    (leaver, leaver_registration) = holders[0]
    (_, first_in_queue) = queue[0]
    notifier.fail = True

    response = await client.post(
        f"/api/v1/registrations/{leaver_registration.id}/withdraw", headers=auth(leaver)
    )

    assert response.status_code == 200
    assert leaver_registration.status == RegistrationStatus.WITHDRAWN
    assert first_in_queue.status == RegistrationStatus.OFFERED


async def test_each_state_change_writes_exactly_one_log_row(
    client: AsyncClient, db: Session
) -> None:
    """TC-X-03, across the two rows this one call touches."""
    event, holders, queue = full_event_with_waitlist(db)
    (leaver, leaver_registration) = holders[0]
    (_, first_in_queue) = queue[0]

    await client.post(
        f"/api/v1/registrations/{leaver_registration.id}/withdraw", headers=auth(leaver)
    )

    entries = db.scalars(
        select(AttendanceLog).where(AttendanceLog.event_id == event.id).order_by(AttendanceLog.id)
    ).all()
    assert [(e.registration_id, e.action) for e in entries] == [
        (leaver_registration.id, "withdrawn"),
        (first_in_queue.id, "offered"),
    ]


async def test_no_offer_is_made_when_the_waitlist_is_empty(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    """TC-US7-06 again, from the offer side: the seat returns to the pool."""
    event = make_event(db, capacity=1, start_at=NOW + timedelta(days=1))
    attendee = make_attendee(db)
    registration = make_registration(db, event, attendee)

    response = await client.post(
        f"/api/v1/registrations/{registration.id}/withdraw", headers=auth(attendee)
    )

    assert response.json()["seats_remaining"] == 1
    assert notifier.offers == []
    offered = db.scalars(
        select(Registration).where(
            Registration.event_id == event.id, Registration.status == RegistrationStatus.OFFERED
        )
    ).all()
    assert not offered


async def test_leaving_the_waitlist_offers_nothing(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    """A waitlisted departure frees no seat, so nobody gets an offer (TC-US7-14)."""
    event, _, queue = full_event_with_waitlist(db)
    (first_attendee, first_in_queue) = queue[0]
    (_, second_in_queue) = queue[1]

    response = await client.post(
        f"/api/v1/registrations/{first_in_queue.id}/withdraw", headers=auth(first_attendee)
    )

    assert response.status_code == 200
    assert notifier.offers == []
    assert second_in_queue.status == RegistrationStatus.WAITLISTED
    assert registration_service.waitlist_position(db, second_in_queue) == 1


async def test_waitlist_positions_are_stable_when_join_times_tie(
    client: AsyncClient, db: Session
) -> None:
    """Identical timestamps must still produce distinct, repeatable positions."""
    event = make_event(db, capacity=1, start_at=NOW + timedelta(days=1))
    make_registration(db, event, make_attendee(db))
    tied = [
        make_registration(
            db,
            event,
            make_attendee(db),
            status=RegistrationStatus.WAITLISTED,
            waitlist_joined_at=NOW - timedelta(hours=1),
        )
        for _ in range(3)
    ]

    positions = sorted(registration_service.waitlist_position(db, r) for r in tied)

    assert positions == [1, 2, 3]
