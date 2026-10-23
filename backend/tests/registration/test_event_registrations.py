"""US28 (SCRUM-96): an Organiser or Coordinator views the registrations for an event they manage."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.registration.models import Registration, RegistrationAnswer, RegistrationStatus
from app.seed import seed, seed_id
from app.user.models import User, UserRole
from tests.factories import (
    NOW,
    make_attendee,
    make_event,
    make_registration,
    make_registration_field,
    make_user,
)

pytestmark = pytest.mark.anyio


def url(event: Event) -> str:
    return f"/api/v1/events/{event.id}/registrations"


MANAGED_URL = "/api/v1/me/managed-events"


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def owned_event(db: Session, organiser: User, **overrides) -> Event:
    event = make_event(db, **overrides)
    event.created_by_user_id = organiser.id
    db.flush()
    return event


def statuses(body: dict) -> list[str]:
    return [row["status"] for row in body["registrations"]]


async def test_tc_us28_01_organiser_sees_registrations_for_their_own_event(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser)
    make_registration(db, event, make_attendee(db))

    response = await client.get(url(event), headers=auth(organiser))

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["id"] == str(event.id)
    assert len(body["registrations"]) == 1


async def test_tc_us28_02_another_organisers_event_is_not_found(client: AsyncClient, db: Session) -> None:
    owner = make_user(db, UserRole.ORGANISER)
    other = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, owner)
    make_registration(db, event, make_attendee(db))

    response = await client.get(url(event), headers=auth(other))

    # 404, not 403: never reveal another person's record (§1a).
    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}


async def test_tc_us28_03_a_coordinator_sees_any_event_until_assignment_exists(
    client: AsyncClient, db: Session
) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR)
    event = owned_event(db, make_user(db, UserRole.ORGANISER))
    make_registration(db, event, make_attendee(db))

    response = await client.get(url(event), headers=auth(coordinator))

    # D29: any coordinator, until the follow-up narrows it to the assigned one.
    assert response.status_code == 200
    assert len(response.json()["registrations"]) == 1


@pytest.mark.parametrize("role", [UserRole.ATTENDEE, UserRole.OPERATIONS_MANAGER])
async def test_tc_us28_04_other_roles_are_forbidden(client: AsyncClient, db: Session, role: UserRole) -> None:
    event = owned_event(db, make_user(db, UserRole.ORGANISER))

    response = await client.get(url(event), headers=auth(make_user(db, role)))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_tc_us28_04b_no_identity_is_unauthenticated(client: AsyncClient, db: Session) -> None:
    event = owned_event(db, make_user(db, UserRole.ORGANISER))

    response = await client.get(url(event))

    assert response.status_code == 401


@pytest.mark.parametrize("status", [EventStatus.DRAFT, EventStatus.SUBMITTED, EventStatus.APPROVED])
async def test_tc_us28_05_a_request_that_is_not_yet_an_event_is_not_found(
    client: AsyncClient, db: Session, status: EventStatus
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser, status=status)

    for user in (organiser, make_user(db, UserRole.COORDINATOR)):
        response = await client.get(url(event), headers=auth(user))
        assert response.status_code == 404


async def test_tc_us28_05b_unknown_event_is_not_found(client: AsyncClient, db: Session) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR)

    response = await client.get(
        "/api/v1/events/00000000-0000-0000-0000-000000000000/registrations", headers=auth(coordinator)
    )

    assert response.status_code == 404


async def test_tc_us28_06_totals_count_confirmed_waitlisted_offered_and_remaining_capacity(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser, capacity=5)
    for _ in range(2):
        make_registration(db, event, make_attendee(db))
    make_registration(
        db, event, make_attendee(db), status=RegistrationStatus.OFFERED, offer_expires_at=NOW + timedelta(hours=3)
    )
    for minutes in (2, 1):
        make_registration(
            db,
            event,
            make_attendee(db),
            status=RegistrationStatus.WAITLISTED,
            waitlist_joined_at=NOW - timedelta(minutes=minutes),
        )
    make_registration(db, event, make_attendee(db), status=RegistrationStatus.WITHDRAWN)

    response = await client.get(url(event), headers=auth(organiser))

    # The live offer holds its seat (§2): 5 - 2 confirmed - 1 offered.
    assert response.json()["totals"] == {"confirmed": 2, "waitlisted": 2, "offered": 1, "seats_remaining": 2}


async def test_tc_us28_07_each_row_has_name_email_status_time_position_and_answers(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser)
    make_registration_field(db, event, field_key="dietary", label="Dietary requirements")
    make_registration_field(db, event, field_key="tshirt", label="T-shirt size", required=False)
    mei = make_attendee(db)
    db.get(User, mei.id).full_name = "Mei Tan"
    seat = make_registration(db, event, mei)
    db.add(RegistrationAnswer(registration_id=seat.id, field_key="dietary", value="vegetarian"))
    queued = make_registration(
        db, event, make_attendee(db), status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW
    )
    db.flush()

    body = (await client.get(url(event), headers=auth(organiser))).json()

    assert [field["field_key"] for field in body["registration_fields"]] == ["dietary", "tshirt"]
    confirmed, waitlisted = body["registrations"]
    assert confirmed["registration_id"] == str(seat.id)
    assert confirmed["attendee_name"] == "Mei Tan"
    assert confirmed["attendee_email"] == mei.email
    assert confirmed["status"] == "confirmed"
    assert confirmed["registered_at"]
    assert confirmed["waitlist_position"] is None
    assert confirmed["answers"] == {"dietary": "vegetarian"}
    assert waitlisted["registration_id"] == str(queued.id)
    assert waitlisted["attendee_name"] is None
    assert waitlisted["waitlist_position"] == 1
    assert waitlisted["answers"] == {}


async def test_tc_us28_08_seat_holders_come_first_then_the_queue_in_order(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser)
    second = make_registration(
        db, event, make_attendee(db), status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW
    )
    first = make_registration(
        db,
        event,
        make_attendee(db),
        status=RegistrationStatus.WAITLISTED,
        waitlist_joined_at=NOW - timedelta(minutes=5),
    )
    offer = make_registration(
        db, event, make_attendee(db), status=RegistrationStatus.OFFERED, offer_expires_at=NOW + timedelta(hours=1)
    )
    seat = make_registration(db, event, make_attendee(db))

    body = (await client.get(url(event), headers=auth(organiser))).json()

    assert [row["registration_id"] for row in body["registrations"]] == [
        str(seat.id),
        str(offer.id),
        str(first.id),
        str(second.id),
    ]
    assert [row["waitlist_position"] for row in body["registrations"]] == [None, None, 1, 2]
    assert body["registrations"][1]["offer_expires_at"] is not None


async def test_tc_us28_09_filter_by_one_or_more_statuses(client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser)
    make_registration(db, event, make_attendee(db))
    make_registration(db, event, make_attendee(db), status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW)
    make_registration(
        db, event, make_attendee(db), status=RegistrationStatus.OFFERED, offer_expires_at=NOW + timedelta(hours=1)
    )

    waitlisted = (await client.get(url(event), params={"status": "waitlisted"}, headers=auth(organiser))).json()
    two = (
        await client.get(url(event), params=[("status", "confirmed"), ("status", "offered")], headers=auth(organiser))
    ).json()

    assert statuses(waitlisted) == ["waitlisted"]
    assert statuses(two) == ["confirmed", "offered"]
    # Totals describe the event, not the filtered list (AC 2).
    assert waitlisted["totals"] == two["totals"] == {
        "confirmed": 1,
        "waitlisted": 1,
        "offered": 1,
        "seats_remaining": 38,
    }


async def test_tc_us28_10_withdrawn_and_declined_are_hidden_unless_show_all(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser)
    make_registration(db, event, make_attendee(db))
    for status in (RegistrationStatus.WITHDRAWN, RegistrationStatus.DECLINED, RegistrationStatus.EXPIRED):
        make_registration(db, event, make_attendee(db), status=status)

    default = (await client.get(url(event), headers=auth(organiser))).json()
    everything = (await client.get(url(event), params={"show_all": "true"}, headers=auth(organiser))).json()
    withdrawn = (await client.get(url(event), params={"status": "withdrawn"}, headers=auth(organiser))).json()

    assert statuses(default) == ["confirmed"]
    assert statuses(everything) == ["confirmed", "withdrawn", "declined", "expired"]
    # Asking for a hidden status by name shows it without the toggle.
    assert statuses(withdrawn) == ["withdrawn"]


async def test_tc_us28_11_an_email_only_waitlist_entry_shows_its_email(client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser)
    db.add(
        Registration(
            event_id=event.id,
            attendee_id=None,
            attendee_email="guest@example.com",
            status=RegistrationStatus.WAITLISTED,
            waitlist_joined_at=NOW,
        )
    )
    db.flush()

    row = (await client.get(url(event), headers=auth(organiser))).json()["registrations"][0]

    assert (row["attendee_name"], row["attendee_email"], row["waitlist_position"]) == (
        None,
        "guest@example.com",
        1,
    )


async def test_tc_us28_12_an_unknown_status_filter_is_rejected(client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    event = owned_event(db, organiser)

    response = await client.get(url(event), params={"status": "cancelled"}, headers=auth(organiser))

    assert response.status_code == 422


async def test_tc_us28_13_managed_events_are_the_organisers_own_events_only(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    later = owned_event(db, organiser, name="Later", start_at=NOW + timedelta(days=5))
    sooner = owned_event(db, organiser, name="Sooner", start_at=NOW + timedelta(days=2))
    owned_event(db, organiser, name="Still a request", status=EventStatus.SUBMITTED)
    owned_event(db, make_user(db, UserRole.ORGANISER), name="Someone else's")

    body = (await client.get(MANAGED_URL, headers=auth(organiser))).json()

    assert [event["id"] for event in body["events"]] == [str(sooner.id), str(later.id)]
    first = body["events"][0]
    assert (first["name"], first["status"], first["capacity"]) == ("Sooner", "confirmed", 40)
    assert first["start_at"] and first["end_at"]


async def test_tc_us28_14_a_coordinator_manages_every_event_and_others_are_refused(
    client: AsyncClient, db: Session
) -> None:
    mine = owned_event(db, make_user(db, UserRole.ORGANISER))
    theirs = owned_event(db, make_user(db, UserRole.ORGANISER))
    request = owned_event(db, make_user(db, UserRole.ORGANISER), status=EventStatus.UNDER_REVIEW)

    coordinator_ids = {
        event["id"]
        for event in (await client.get(MANAGED_URL, headers=auth(make_user(db, UserRole.COORDINATOR)))).json()[
            "events"
        ]
    }
    refused = await client.get(MANAGED_URL, headers=auth(make_user(db, UserRole.ATTENDEE)))

    assert {str(mine.id), str(theirs.id)} <= coordinator_ids
    assert str(request.id) not in coordinator_ids
    assert refused.status_code == 403


def test_tc_us28_15_the_seeded_organiser_owns_the_seeded_events(db: Session) -> None:
    seed(db, now=NOW)

    event = db.get(Event, seed_id("event", "design-sprint-bootcamp"))

    assert event.created_by_user_id == seed_id("user", "event-organiser")
