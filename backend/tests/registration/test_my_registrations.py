from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import DeliveryMode
from app.registration.models import RegistrationStatus
from tests.factories import NOW, make_attendee, make_event, make_registration

pytestmark = pytest.mark.anyio

URL = "/api/v1/me/registrations"


def auth(attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


async def test_tc_us11_01_only_the_callers_own_registrations_appear(
    client: AsyncClient, db: Session
) -> None:
    attendee_a = make_attendee(db)
    attendee_b = make_attendee(db)
    event = make_event(db)
    make_registration(db, event, attendee_a)
    make_registration(db, event, attendee_b)

    response = await client.get(URL, headers=auth(attendee_a))

    body = response.json()
    assert len(body["confirmed"]) == 1
    assert body["waitlisted"] == []


async def test_tc_us11_02_in_person_confirmed_entry_shows_room_number_as_joining_info(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    event = make_event(
        db,
        name="Tech Talk: Agile at Scale",
        start_at=NOW + timedelta(days=1, hours=5),
        venue_name="SMU SCIS Building",
        room_number="Seminar Room 2-1",
    )
    make_registration(db, event, attendee)

    response = await client.get(URL, headers=auth(attendee))

    entry = response.json()["confirmed"][0]
    assert entry["event_name"] == "Tech Talk: Agile at Scale"
    assert entry["venue_name"] == "SMU SCIS Building"
    assert entry["joining_info"] == "Seminar Room 2-1"
    assert entry["delivery_mode"] == "in_person"
    assert "date" in entry and "start_time" in entry and "end_time" in entry


async def test_tc_us11_03_online_event_joining_info_is_the_join_link(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    event = make_event(
        db,
        delivery_mode=DeliveryMode.ONLINE,
        venue_name=None,
        room_number=None,
        join_link="https://smu-sg.zoom.us/j/1",
    )
    make_registration(db, event, attendee)

    response = await client.get(URL, headers=auth(attendee))

    entry = response.json()["confirmed"][0]
    assert entry["joining_info"] == "https://smu-sg.zoom.us/j/1"
    assert entry["venue_name"] is None


async def test_tc_us11_04_entries_are_ordered_ascending_by_start(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    late = make_event(db, name="Late Event", start_at=NOW + timedelta(days=10))
    early = make_event(db, name="Early Event", start_at=NOW + timedelta(days=1))
    mid = make_event(db, name="Mid Event", start_at=NOW + timedelta(days=5))
    for event in (late, early, mid):
        make_registration(db, event, attendee)

    response = await client.get(URL, headers=auth(attendee))

    names = [e["event_name"] for e in response.json()["confirmed"]]
    assert names == ["Early Event", "Mid Event", "Late Event"]


async def test_tc_us11_05_same_start_time_breaks_tie_alphabetically(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    same_start = NOW + timedelta(days=3)
    zumba = make_event(db, name="Zumba", start_at=same_start)
    archery = make_event(db, name="Archery", start_at=same_start)
    make_registration(db, zumba, attendee)
    make_registration(db, archery, attendee)

    response = await client.get(URL, headers=auth(attendee))

    names = [e["event_name"] for e in response.json()["confirmed"]]
    assert names == ["Archery", "Zumba"]


async def test_tc_us11_06_confirmed_and_waitlisted_are_separate_sections_confirmed_first(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    confirmed_event = make_event(db, name="Confirmed Event")
    waitlisted_event = make_event(db, name="Waitlisted Event")
    make_registration(db, confirmed_event, attendee, status=RegistrationStatus.CONFIRMED)
    make_registration(
        db,
        waitlisted_event,
        attendee,
        status=RegistrationStatus.WAITLISTED,
        waitlist_joined_at=NOW,
    )

    response = await client.get(URL, headers=auth(attendee))

    body = response.json()
    assert [e["event_name"] for e in body["confirmed"]] == ["Confirmed Event"]
    assert [e["event_name"] for e in body["waitlisted"]] == ["Waitlisted Event"]


async def test_tc_us11_07_waitlisted_entry_shows_queue_position(
    client: AsyncClient, db: Session
) -> None:
    event = make_event(db, capacity=0)
    a, b, c = (make_attendee(db) for _ in range(3))
    make_registration(
        db, event, a, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW - timedelta(minutes=3)
    )
    make_registration(
        db, event, b, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW - timedelta(minutes=2)
    )
    make_registration(
        db, event, c, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW - timedelta(minutes=1)
    )

    response = await client.get(URL, headers=auth(c))

    entry = response.json()["waitlisted"][0]
    assert entry["waitlist_position"] == 3


async def test_tc_us11_08_a_withdrawn_registration_is_absent(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    event = make_event(db)
    make_registration(db, event, attendee, status=RegistrationStatus.WITHDRAWN)

    response = await client.get(URL, headers=auth(attendee))

    body = response.json()
    assert body["confirmed"] == []
    assert body["waitlisted"] == []


async def test_tc_us11_09_a_past_event_is_absent_filtered_on_end_at(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    ended = make_event(
        db,
        name="Already Ended",
        start_at=NOW - timedelta(hours=3),
        end_at=NOW - timedelta(hours=1),
    )
    in_progress = make_event(
        db,
        name="In Progress",
        start_at=NOW - timedelta(minutes=30),
        end_at=NOW + timedelta(minutes=30),
    )
    make_registration(db, ended, attendee)
    make_registration(db, in_progress, attendee)

    response = await client.get(URL, headers=auth(attendee))

    names = [e["event_name"] for e in response.json()["confirmed"]]
    assert names == ["In Progress"]


async def test_tc_us11_10_no_upcoming_registrations_returns_empty_lists(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)

    response = await client.get(URL, headers=auth(attendee))

    assert response.json() == {"confirmed": [], "waitlisted": []}


async def test_tc_us11_11_confirmed_only_does_not_break_when_waitlisted_is_empty(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    event = make_event(db)
    make_registration(db, event, attendee, status=RegistrationStatus.CONFIRMED)

    response = await client.get(URL, headers=auth(attendee))

    body = response.json()
    assert len(body["confirmed"]) == 1
    assert body["waitlisted"] == []


async def test_my_registrations_requires_an_attendee_header(client: AsyncClient, db: Session) -> None:
    response = await client.get(URL)

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
