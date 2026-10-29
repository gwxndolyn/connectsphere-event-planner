"""US21 venue availability calendar, PR 1 (SCRUM-122, story SCRUM-88): a venue's live bookings, with
their stored occupied windows (US13), and its blocks (US2) over a range of Singapore days, for
Coordinators, Leads and Venue Staff (D56). See docs/testing/US21-venue-calendar.md."""

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBookingStatus
from tests.factories import make_event, make_user, make_venue, make_venue_block, make_venue_booking

pytestmark = pytest.mark.anyio

SINGAPORE = ZoneInfo("Asia/Singapore")
# A Monday-to-Sunday week, after NOW (Thu 1 Oct 2026).
MONDAY = date(2026, 10, 12)
SUNDAY = MONDAY + timedelta(days=6)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), SINGAPORE)


def when(value: str) -> datetime:
    return datetime.fromisoformat(value)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


async def calendar(
    client: AsyncClient, user: User | None, venue_id: uuid.UUID, start: object = MONDAY, end: object = SUNDAY
) -> Response:
    params = {key: str(value) for key, value in (("from", start), ("to", end)) if value is not None}
    headers = auth(user) if user else {}
    return await client.get(f"/api/v1/venues/{venue_id}/calendar", params=params, headers=headers)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def venue(db: Session) -> Venue:
    # make_venue's buffers: 30 min setup, 15 min turnaround; open 08:00-20:00.
    return make_venue(db, name="Hall A")


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    return make_event(db, name="Design Review", status=EventStatus.APPROVED, coordinator_id=coordinator.id)


def book(db: Session, event: Event, venue: Venue, user: User, day: date = MONDAY, start: int = 10, **kwargs: object):
    return make_venue_booking(
        db, event=event, venue=venue, user=user, starts_at=at(day, start), ends_at=at(day, start + 2), **kwargs
    )


async def test_tc_us21_01_an_approved_booking_with_its_buffers(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    booking = book(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED)

    response = await calendar(client, staff, venue.id)

    assert response.status_code == 200
    body = response.json()
    assert body["from"] == "2026-10-12"
    assert body["to"] == "2026-10-18"
    assert body["venue"] == {
        "id": str(venue.id),
        "name": "Hall A",
        "is_active": True,
        "opens_at": "08:00:00",
        "closes_at": "20:00:00",
        "setup_minutes": 30,
        "turnaround_minutes": 15,
    }
    [item] = body["items"]
    assert item["kind"] == "booking"
    assert item["label"] == "Booking"
    assert when(item["starts_at"]) == at(MONDAY, 10)
    assert when(item["ends_at"]) == at(MONDAY, 12)
    assert when(item["occupied"]["starts_at"]) == at(MONDAY, 9, 30)
    assert when(item["occupied"]["ends_at"]) == at(MONDAY, 12, 15)
    assert item["note"] is None
    assert item["booking"]["id"] == str(booking.id)
    assert item["booking"]["status"] == "approved"


async def test_tc_us21_02_a_requested_booking_is_shown_as_pending(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    book(db, event, venue, coordinator)

    [item] = (await calendar(client, staff, venue.id)).json()["items"]

    assert item["label"] == "Booking"
    assert item["booking"]["status"] == "requested"


async def test_tc_us21_03_a_block_is_unavailable_with_its_note(
    client: AsyncClient, db: Session, staff: User, venue: Venue
) -> None:
    make_venue_block(db, venue, at(MONDAY, 13), at(MONDAY, 15), note="Aircon repair")

    [item] = (await calendar(client, staff, venue.id)).json()["items"]

    assert item["kind"] == "block"
    assert item["label"] == "Unavailable"
    assert item["booking"] is None
    assert item["note"] == "Aircon repair"
    # A block has no buffers of its own (D22).
    assert item["occupied"] == {"starts_at": item["starts_at"], "ends_at": item["ends_at"]}
    assert when(item["starts_at"]) == at(MONDAY, 13)


async def test_tc_us21_04_withdrawn_and_rejected_bookings_are_left_out(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    book(db, event, venue, coordinator, status=VenueBookingStatus.WITHDRAWN)
    book(db, event, venue, coordinator, start=14, status=VenueBookingStatus.REJECTED)

    assert (await calendar(client, staff, venue.id)).json()["items"] == []


async def test_tc_us21_05_a_booking_for_a_cancelled_event_is_left_out(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue
) -> None:
    cancelled = make_event(db, status=EventStatus.CANCELLED, coordinator_id=coordinator.id)
    book(db, cancelled, venue, coordinator, status=VenueBookingStatus.APPROVED)

    assert (await calendar(client, staff, venue.id)).json()["items"] == []


async def test_tc_us21_06_items_overlapping_the_range_by_their_buffers_are_included(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    # Stored windows set directly (the hours rule is the create path's, not the calendar's).
    # Own times end before the range starts; turnaround runs into its first day.
    before = MONDAY - timedelta(days=1)
    late = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=at(before, 21), ends_at=at(before, 23),
        occupied_starts_at=at(before, 20, 30), occupied_ends_at=at(MONDAY, 1),
    )
    # Setup starts inside the range's last day; own times start after it.
    after = SUNDAY + timedelta(days=1)
    early = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=at(after, 0, 30), ends_at=at(after, 2),
        occupied_starts_at=at(SUNDAY, 23), occupied_ends_at=at(after, 2),
    )

    items = (await calendar(client, staff, venue.id)).json()["items"]

    assert [item["booking"]["id"] for item in items] == [str(late.id), str(early.id)]


async def test_tc_us21_07_items_outside_the_range_or_at_another_venue_are_left_out(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    book(db, event, venue, coordinator, day=MONDAY - timedelta(days=3))
    book(db, event, venue, coordinator, day=SUNDAY + timedelta(days=2))
    make_venue_block(db, venue, at(SUNDAY + timedelta(days=1), 9), at(SUNDAY + timedelta(days=1), 10))
    other = make_venue(db, name="Hall B")
    book(db, event, other, coordinator)
    make_venue_block(db, other, at(MONDAY, 9), at(MONDAY, 10))

    assert (await calendar(client, staff, venue.id)).json()["items"] == []


async def test_tc_us21_08_items_in_order_with_the_event_name_and_status(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    # A request may have no name until it's planned (events_final_fields_required); it's named by its reference.
    unnamed = make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)
    unnamed.name = None
    unnamed.request_reference = "ER-2026-000042"
    planning = make_event(db, name="Launch Night", status=EventStatus.PLANNING, coordinator_id=coordinator.id)
    book(db, unnamed, venue, coordinator, day=MONDAY + timedelta(days=2))
    book(db, planning, venue, coordinator, day=MONDAY + timedelta(days=3))
    make_venue_block(db, venue, at(MONDAY + timedelta(days=1), 9), at(MONDAY + timedelta(days=1), 10))
    book(db, event, venue, coordinator)

    items = (await calendar(client, staff, venue.id)).json()["items"]

    assert [item["kind"] for item in items] == ["booking", "block", "booking", "booking"]
    assert [item["booking"]["event"] if item["booking"] else None for item in items] == [
        {"name": "Design Review", "request_reference": None, "status": "approved"},
        None,
        {"name": None, "request_reference": "ER-2026-000042", "status": "approved"},
        {"name": "Launch Night", "request_reference": None, "status": "planning"},
    ]


async def test_tc_us21_08_a_booking_and_a_block_starting_together_list_the_booking_first(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    make_venue_block(db, venue, at(MONDAY, 9, 30), at(MONDAY, 9, 45))
    book(db, event, venue, coordinator)  # occupied from 09:30

    items = (await calendar(client, staff, venue.id)).json()["items"]

    assert [item["kind"] for item in items] == ["booking", "block"]


async def test_tc_us21_09_the_reference_only_for_staff_leads_and_the_events_coordinator(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    booking = book(db, event, venue, coordinator)
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    other_coordinator = make_user(db, UserRole.COORDINATOR)

    async def reference(user: User) -> str | None:
        [item] = (await calendar(client, user, venue.id)).json()["items"]
        return item["booking"]["reference"]

    assert await reference(staff) == booking.reference
    assert await reference(lead) == booking.reference
    assert await reference(coordinator) == booking.reference
    assert await reference(other_coordinator) is None
    # Everything else still reaches the other coordinator (D58).
    [item] = (await calendar(client, other_coordinator, venue.id)).json()["items"]
    assert item["booking"]["event"]["name"] == "Design Review"
    assert item["booking"]["status"] == "requested"


@pytest.mark.parametrize(
    "role", [UserRole.ORGANISER, UserRole.ATTENDEE, UserRole.TECH_SUPPORT, UserRole.SAFETY_OFFICER]
)
async def test_tc_us21_10_other_roles_are_403_and_no_identity_401(
    client: AsyncClient, db: Session, venue: Venue, role: UserRole
) -> None:
    refused = await calendar(client, make_user(db, role), venue.id)
    anonymous = await calendar(client, None, venue.id)

    assert refused.status_code == 403
    assert refused.json()["code"] == "FORBIDDEN"
    assert anonymous.status_code == 401


async def test_tc_us21_11_any_held_calendar_role_is_enough(client: AsyncClient, db: Session, venue: Venue) -> None:
    both = make_user(db, UserRole.ORGANISER, UserRole.COORDINATOR)

    assert (await calendar(client, both, venue.id)).status_code == 200


async def test_tc_us21_12_an_inactive_venue_follows_the_venue_read_rule(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event
) -> None:
    inactive = make_venue(db, name="Closed Hall", is_active=False)
    stranger = make_user(db, UserRole.COORDINATOR)
    book(db, event, inactive, coordinator)

    assert (await calendar(client, staff, inactive.id)).status_code == 200
    assert (await calendar(client, coordinator, inactive.id)).status_code == 200
    refused = await calendar(client, stranger, inactive.id)
    assert refused.status_code == 404
    assert refused.json()["code"] == "NOT_FOUND"


async def test_tc_us21_13_an_unknown_venue_is_404(client: AsyncClient, staff: User) -> None:
    response = await calendar(client, staff, uuid.uuid4())

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    ("start", "end", "fields"),
    [
        (None, SUNDAY, ["from"]),
        (MONDAY, None, ["to"]),
        (None, None, ["from", "to"]),
        ("12-10-2026", SUNDAY, ["from"]),
        (MONDAY, "soon", ["to"]),
        (MONDAY, MONDAY - timedelta(days=1), ["to"]),
        (MONDAY, MONDAY + timedelta(days=42), ["to"]),
    ],
)
async def test_tc_us21_14_a_bad_range_is_invalid_date_range(
    client: AsyncClient, staff: User, venue: Venue, start: object, end: object, fields: list[str]
) -> None:
    response = await calendar(client, staff, venue.id, start, end)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_DATE_RANGE"
    assert response.json()["fields"] == fields


async def test_tc_us21_14_forty_two_days_and_a_single_day_are_accepted(
    client: AsyncClient, staff: User, venue: Venue
) -> None:
    assert (await calendar(client, staff, venue.id, MONDAY, MONDAY + timedelta(days=41))).status_code == 200
    assert (await calendar(client, staff, venue.id, MONDAY, MONDAY)).status_code == 200
