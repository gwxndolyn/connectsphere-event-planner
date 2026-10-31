"""US24 multiple venues for one event, PR 2 (SCRUM-128, story SCRUM-92): booking several venues with a
purpose each, inside the event's schedule (D65); the primary venue (D68) and what attendees see (D70);
withdrawing one, approved ones too (D69, D77); the Organiser's view (D71); "venues arranged" (D67, D72);
and Venue staff's preparation status (D73). See docs/testing/US24-multi-venue.md."""

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import DeliveryMode, Event, EventStatus
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.factories import make_attendee, make_event, make_user, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

SINGAPORE = ZoneInfo("Asia/Singapore")
# The demo event's preferred day: Thursday a week after NOW (Thu 1 Oct 2026, 09:00).
DAY = date(2026, 10, 8)
BOOKINGS = "/api/v1/venue-bookings"


def at(hour: int, minute: int = 0, day: date = DAY) -> datetime:
    return datetime.combine(day, time(hour, minute), SINGAPORE)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def event_url(event: Event) -> str:
    return f"/api/v1/events/{event.id}/venue-bookings"


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


def schedule(event: Event, *, expected: int | None = 100, dates: list[date] | None = None) -> Event:
    """An Approved request's schedule (D65): its preferred day, 09:00 to 17:00, before start_at exists."""
    event.preferred_dates = dates if dates is not None else [DAY]
    event.preferred_start_time = time(9, 0)
    event.preferred_end_time = time(17, 0)
    event.expected_attendees = expected
    return event


@pytest.fixture
def event(db: Session, coordinator: User, organiser: User) -> Event:
    # DECISION-PENDING: D24 — tests put the request straight into approved.
    conference = make_event(db, name="Data Conference", status=EventStatus.APPROVED, coordinator_id=coordinator.id)
    conference.created_by_user_id = organiser.id
    schedule(conference)
    db.flush()
    return conference


@pytest.fixture
def hall(db: Session) -> Venue:
    # 30 min setup, 15 min turnaround, open 08:00-20:00.
    return make_venue(db, name="Main Hall", location="Building 1, Level 1", capacity=200, room_layouts=["theatre"])


@pytest.fixture
def room(db: Session) -> Venue:
    return make_venue(db, name="Breakout Room", location="Building 1, Level 2", capacity=40, room_layouts=["classroom"])


def body(event: Event, venue: Venue, starts: datetime, ends: datetime, **overrides: object) -> dict[str, object]:
    return {
        "event_id": str(event.id),
        "venue_id": str(venue.id),
        "starts_at": starts.isoformat(),
        "ends_at": ends.isoformat(),
        "expected_attendees": 40,
        "room_layout": venue.room_layouts[0],
        "purpose": "Main hall",
    } | overrides


async def request_venue(
    client: AsyncClient, coordinator: User, event: Event, venue: Venue, starts: datetime, ends: datetime, **overrides: object
) -> Response:
    return await client.post(BOOKINGS, json=body(event, venue, starts, ends, **overrides), headers=auth(coordinator))


def book(
    db: Session, event: Event, venue: Venue, user: User, starts: datetime, ends: datetime, **fields: object
) -> VenueBooking:
    """A booking straight into the database, for states the API reaches in several steps."""
    return make_venue_booking(db, event=event, venue=venue, user=user, starts_at=starts, ends_at=ends, **fields)


async def event_bookings(client: AsyncClient, user: User, event: Event) -> Response:
    return await client.get(event_url(event), headers=auth(user))


# --- TC-US24-05 several venues, each with its own window and purpose ---


async def test_tc_us24_05_one_event_books_two_venues_each_with_its_own_window_and_purpose(
    client: AsyncClient, coordinator: User, event: Event, hall: Venue, room: Venue
) -> None:
    main = await request_venue(client, coordinator, event, hall, at(9), at(17), expected_attendees=100)
    breakout = await request_venue(client, coordinator, event, room, at(13), at(15), purpose="Breakout A")

    assert (main.status_code, breakout.status_code) == (201, 201)
    assert (main.json()["purpose"], breakout.json()["purpose"]) == ("Main hall", "Breakout A")
    assert main.json()["venue"]["id"] == str(hall.id) and breakout.json()["venue"]["id"] == str(room.id)
    assert datetime.fromisoformat(breakout.json()["starts_at"]) == at(13)
    assert breakout.json()["preparation_status"] == "not_started"


# --- TC-US24-06 within the event's schedule (D65) ---


@pytest.mark.parametrize(
    ("starts", "ends", "field"),
    [
        (at(10, day=DAY + timedelta(days=1)), at(12, day=DAY + timedelta(days=1)), "starts_at"),  # not a preferred day
        (at(8, 30), at(10), "starts_at"),  # before the preferred start
        (at(16), at(17, 30), "ends_at"),  # after the preferred end
    ],
)
async def test_tc_us24_06_a_window_outside_the_preferred_schedule_is_refused_on_its_field(
    client: AsyncClient, coordinator: User, event: Event, hall: Venue, starts: datetime, ends: datetime, field: str
) -> None:
    response = await request_venue(client, coordinator, event, hall, starts, ends)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_BOOKING"
    assert response.json()["fields"] == [field]
    assert "schedule" in response.json()["errors"][field]


async def test_tc_us24_06_setup_may_start_before_the_schedule(
    client: AsyncClient, coordinator: User, event: Event, hall: Venue
) -> None:
    # Hall's 30 minutes' setup starts at 08:30; only the booking's own window must fit.
    response = await request_venue(client, coordinator, event, hall, at(9), at(10))

    assert response.status_code == 201


@pytest.mark.parametrize(
    ("starts", "ends", "status", "field"),
    [
        (at(9), at(11), 422, "starts_at"),
        (at(15), at(17), 422, "ends_at"),
        (at(10), at(16), 201, None),
    ],
)
async def test_tc_us24_06_once_start_at_and_end_at_are_set_the_window_must_sit_inside_them(
    client: AsyncClient, db: Session, coordinator: User, hall: Venue,
    starts: datetime, ends: datetime, status: int, field: str | None,
) -> None:
    planning = make_event(
        db, status=EventStatus.PLANNING, coordinator_id=coordinator.id, start_at=at(10), end_at=at(16)
    )
    response = await request_venue(client, coordinator, planning, hall, starts, ends)

    assert response.status_code == status
    if field:
        assert response.json()["fields"] == [field]


async def test_tc_us24_06_an_event_with_no_schedule_yet_is_not_checked(
    client: AsyncClient, db: Session, coordinator: User, hall: Venue
) -> None:
    bare = make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)

    # Evening, which a preferred-times schedule would refuse; within the hall's hours with its buffers.
    response = await request_venue(client, coordinator, bare, hall, at(18), at(19))

    assert response.status_code == 201


# --- TC-US24-07 purpose (D66) ---


async def test_tc_us24_07_a_missing_purpose_is_a_missing_field(
    client: AsyncClient, coordinator: User, event: Event, hall: Venue
) -> None:
    sent = body(event, hall, at(9), at(11))
    del sent["purpose"]

    response = await client.post(BOOKINGS, json=sent, headers=auth(coordinator))

    assert response.status_code == 422
    assert response.json()["code"] == "MISSING_REQUIRED_FIELD"
    assert response.json()["fields"] == ["purpose"]


@pytest.mark.parametrize("purpose", ["", "   ", "x" * 101])
async def test_tc_us24_07_a_blank_or_overlong_purpose_is_refused(
    client: AsyncClient, coordinator: User, event: Event, hall: Venue, purpose: str
) -> None:
    response = await request_venue(client, coordinator, event, hall, at(9), at(11), purpose=purpose)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_BOOKING"
    assert response.json()["fields"] == ["purpose"]


async def test_tc_us24_07_the_purpose_is_trimmed(
    client: AsyncClient, coordinator: User, event: Event, hall: Venue
) -> None:
    response = await request_venue(client, coordinator, event, hall, at(9), at(11), purpose="  Breakout A ")

    assert response.status_code == 201
    assert response.json()["purpose"] == "Breakout A"


# --- TC-US24-08 each venue checked on its own ---


async def test_tc_us24_08_one_venue_refused_for_a_clash_another_accepted(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue, room: Venue
) -> None:
    db.add(VenueBlock(venue_id=room.id, starts_at=at(13), ends_at=at(15), note="Repainting"))
    db.flush()

    refused = await request_venue(client, coordinator, event, room, at(13), at(15), purpose="Breakout A")
    accepted = await request_venue(client, coordinator, event, hall, at(13), at(15))

    assert (refused.status_code, refused.json()["code"]) == (409, "VENUE_UNAVAILABLE")
    assert accepted.status_code == 201


async def test_tc_us24_08_opening_hours_are_judged_per_venue(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue
) -> None:
    late_opener = make_venue(db, name="Late Room", opens_at=time(10, 0), setup_minutes=0, turnaround_minutes=0)

    refused = await request_venue(client, coordinator, event, late_opener, at(9), at(11), room_layout="theatre")
    accepted = await request_venue(client, coordinator, event, hall, at(9), at(11))

    assert (refused.status_code, refused.json()["code"]) == (422, "VENUE_OUTSIDE_HOURS")
    assert accepted.status_code == 201


# --- TC-US24-09 allocation within each venue's capacity (D67) ---


async def test_tc_us24_09_an_allocation_over_the_venues_capacity_is_refused(
    client: AsyncClient, coordinator: User, event: Event, room: Venue
) -> None:
    response = await request_venue(client, coordinator, event, room, at(13), at(15), expected_attendees=41)

    assert (response.status_code, response.json()["code"]) == (422, "VENUE_CAPACITY_EXCEEDED")


async def test_tc_us24_09_the_allocations_may_add_up_to_more_than_expected(
    client: AsyncClient, coordinator: User, event: Event, hall: Venue, room: Venue
) -> None:
    # Expected 100: everyone in the hall, then 40 of them in the breakout room.
    main = await request_venue(client, coordinator, event, hall, at(9), at(12), expected_attendees=100)
    breakout = await request_venue(client, coordinator, event, room, at(13), at(15), expected_attendees=40)

    assert (main.status_code, breakout.status_code) == (201, 201)


async def test_tc_us24_09_a_shortfall_never_refuses_a_request(
    client: AsyncClient, coordinator: User, event: Event, room: Venue
) -> None:
    response = await request_venue(client, coordinator, event, room, at(13), at(15), expected_attendees=10)

    assert response.status_code == 201


# --- TC-US24-10 to 12 the primary venue (D68) ---


async def test_tc_us24_10_the_first_booking_is_primary_and_later_ones_are_not(
    client: AsyncClient, coordinator: User, event: Event, hall: Venue, room: Venue
) -> None:
    first = await request_venue(client, coordinator, event, hall, at(9), at(12))
    second = await request_venue(client, coordinator, event, room, at(13), at(15), purpose="Breakout A")

    assert (first.json()["is_primary"], second.json()["is_primary"]) == (True, False)


async def test_tc_us24_10_a_new_booking_becomes_primary_when_the_event_has_none_live(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue, room: Venue
) -> None:
    book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.WITHDRAWN, is_primary=True)

    response = await request_venue(client, coordinator, event, room, at(13), at(15), purpose="Breakout A")

    assert response.json()["is_primary"] is True


async def test_tc_us24_11_make_primary_moves_the_flag(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue, room: Venue
) -> None:
    main = book(db, event, hall, coordinator, at(9), at(12), is_primary=True)
    breakout = book(db, event, room, coordinator, at(13), at(15), purpose="Breakout A")

    moved = await client.post(f"{BOOKINGS}/{breakout.id}/make-primary", headers=auth(coordinator))
    again = await client.post(f"{BOOKINGS}/{breakout.id}/make-primary", headers=auth(coordinator))

    assert (moved.status_code, moved.json()["is_primary"]) == (200, True)
    assert again.status_code == 200  # idempotent
    listed = (await event_bookings(client, coordinator, event)).json()
    assert {b["id"]: b["is_primary"] for b in listed["bookings"]} == {str(main.id): False, str(breakout.id): True}
    assert listed["primary_booking_id"] == str(breakout.id)


@pytest.mark.parametrize("status", [VenueBookingStatus.WITHDRAWN, VenueBookingStatus.REJECTED])
async def test_tc_us24_11_a_booking_that_is_not_live_cannot_be_primary(
    client: AsyncClient, db: Session, coordinator: User, event: Event, room: Venue, status: VenueBookingStatus
) -> None:
    gone = book(db, event, room, coordinator, at(13), at(15), status=status)

    response = await client.post(f"{BOOKINGS}/{gone.id}/make-primary", headers=auth(coordinator))

    assert response.status_code == 409
    assert response.json() == {"code": "BOOKING_NOT_LIVE", "status": status.value}


async def test_tc_us24_11_only_the_events_coordinator_may_make_a_booking_primary(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, room: Venue
) -> None:
    breakout = book(db, event, room, coordinator, at(13), at(15))
    other = make_user(db, UserRole.COORDINATOR)

    assert (await client.post(f"{BOOKINGS}/{breakout.id}/make-primary", headers=auth(other))).status_code == 404
    assert (await client.post(f"{BOOKINGS}/{breakout.id}/make-primary", headers=auth(staff))).status_code == 403
    assert (await client.post(f"{BOOKINGS}/{uuid.uuid4()}/make-primary", headers=auth(coordinator))).status_code == 404


async def test_tc_us24_11_a_requested_primary_shows_attendees_the_events_own_venue_until_approved(
    client: AsyncClient, db: Session, coordinator: User, staff: User, hall: Venue, room: Venue
) -> None:
    """#100 review: making a Requested booking primary is allowed (D68, CS3-25); attendees see only an
    approved primary (D70), so they see the event's own venue until Venue staff approve it."""
    # Planning, so its bookings can be approved; it's confirmed whenever attendees look, as the board
    # lists only confirmed events.
    event = make_event(db, name="Open Day", status=EventStatus.PLANNING, coordinator_id=coordinator.id)
    main = book(db, event, hall, coordinator, event.start_at, event.end_at, status=VenueBookingStatus.APPROVED, is_primary=True)
    breakout = book(db, event, room, coordinator, event.start_at, event.end_at)
    attendee = make_attendee(db)

    async def board_venue() -> tuple[str | None, str | None]:
        event.status = EventStatus.CONFIRMED
        db.flush()
        events = (await client.get("/api/v1/events/available", headers={"X-Attendee-Id": str(attendee.id)})).json()["events"]
        event.status = EventStatus.PLANNING
        db.flush()
        [listed] = [e for e in events if e["name"] == "Open Day"]
        return listed["venue_name"], listed["venue_location"]

    assert await board_venue() == ("Main Hall", "Building 1, Level 1")

    moved = await client.post(f"{BOOKINGS}/{breakout.id}/make-primary", headers=auth(coordinator))
    assert (moved.status_code, moved.json()["is_primary"], moved.json()["status"]) == (200, True, "requested")
    db.expire_all()
    assert db.get(VenueBooking, main.id).is_primary is False
    # Not approved yet: the event's own venue_name / room_number.
    assert await board_venue() == ("SMU SCIS Building", "Seminar Room 2-1")

    approved = await client.post(f"{BOOKINGS}/{breakout.id}/approve", headers=auth(staff))
    assert approved.status_code == 200
    assert await board_venue() == ("Breakout Room", "Building 1, Level 2")


async def test_tc_us24_12_withdrawing_the_primary_leaves_the_event_without_one(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue, room: Venue
) -> None:
    main = book(db, event, hall, coordinator, at(9), at(12), is_primary=True)
    breakout = book(db, event, room, coordinator, at(13), at(15))

    await client.post(f"{BOOKINGS}/{main.id}/withdraw", headers=auth(coordinator))

    listed = (await event_bookings(client, coordinator, event)).json()
    assert listed["primary_booking_id"] is None
    assert listed["next_action"] == "choose_primary"
    assert listed["venues_arranged"] is False
    assert {b["id"]: b["is_primary"] for b in listed["bookings"]}[str(breakout.id)] is False


async def test_tc_us24_12_rejecting_the_primary_leaves_the_event_without_one(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, hall: Venue, room: Venue
) -> None:
    main = book(db, event, hall, coordinator, at(9), at(12), is_primary=True)
    book(db, event, room, coordinator, at(13), at(15))

    rejected = await client.post(f"{BOOKINGS}/{main.id}/reject", json={"reason": "Closed"}, headers=auth(staff))

    assert rejected.status_code == 200
    listed = (await event_bookings(client, coordinator, event)).json()
    assert (listed["primary_booking_id"], listed["next_action"]) == (None, "choose_primary")


# --- TC-US24-13 attendees see the approved primary venue (D70) ---


@pytest.fixture
def confirmed(db: Session, coordinator: User) -> Event:
    # make_event's defaults: confirmed, registration open, tomorrow 09:00-11:00, venue_name "SMU SCIS Building".
    return make_event(db, name="Open Day", coordinator_id=coordinator.id)


async def test_tc_us24_13_attendees_see_the_approved_primary_venue_and_never_another(
    client: AsyncClient, db: Session, coordinator: User, confirmed: Event, hall: Venue, room: Venue
) -> None:
    book(db, confirmed, hall, coordinator, confirmed.start_at, confirmed.end_at, status=VenueBookingStatus.APPROVED, is_primary=True)
    book(db, confirmed, room, coordinator, confirmed.start_at, confirmed.end_at, status=VenueBookingStatus.APPROVED)
    attendee = make_attendee(db)
    headers = {"X-Attendee-Id": str(attendee.id)}

    [listed] = [e for e in (await client.get("/api/v1/events/available", headers=headers)).json()["events"] if e["name"] == "Open Day"]
    registered = await client.post(f"/api/v1/events/{confirmed.id}/registrations", json={}, headers=headers)
    [mine] = (await client.get("/api/v1/me/registrations", headers=headers)).json()["confirmed"]

    assert (listed["venue_name"], listed["venue_location"]) == ("Main Hall", "Building 1, Level 1")
    assert registered.json()["event"]["venue_name"] == "Main Hall"
    assert (mine["venue_name"], mine["joining_info"]) == ("Main Hall", "Building 1, Level 1")


@pytest.mark.parametrize("status", [None, VenueBookingStatus.REQUESTED])
async def test_tc_us24_13_without_an_approved_primary_attendees_see_the_events_own_venue(
    client: AsyncClient, db: Session, coordinator: User, confirmed: Event, hall: Venue, status: VenueBookingStatus | None
) -> None:
    if status:
        book(db, confirmed, hall, coordinator, confirmed.start_at, confirmed.end_at, status=status, is_primary=True)
    attendee = make_attendee(db)
    headers = {"X-Attendee-Id": str(attendee.id)}

    [listed] = [e for e in (await client.get("/api/v1/events/available", headers=headers)).json()["events"] if e["name"] == "Open Day"]
    await client.post(f"/api/v1/events/{confirmed.id}/registrations", json={}, headers=headers)
    [mine] = (await client.get("/api/v1/me/registrations", headers=headers)).json()["confirmed"]

    assert (listed["venue_name"], listed["venue_location"]) == ("SMU SCIS Building", "Seminar Room 2-1")
    assert (mine["venue_name"], mine["joining_info"]) == ("SMU SCIS Building", "Seminar Room 2-1")


async def test_tc_us24_13_an_online_event_has_no_venue_location(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_event(
        db, name="Webinar", delivery_mode=DeliveryMode.ONLINE, venue_name=None, room_number=None,
        join_link="https://example.com/j/1",
    )
    attendee = make_attendee(db)

    events = (await client.get("/api/v1/events/available", headers={"X-Attendee-Id": str(attendee.id)})).json()["events"]

    [webinar] = [e for e in events if e["name"] == "Webinar"]
    assert (webinar["venue_name"], webinar["venue_location"]) == (None, None)


# --- TC-US24-14 and 15 the Organiser's view (D71) ---


async def test_tc_us24_14_the_organiser_reads_every_venue_with_its_status_and_next_action(
    client: AsyncClient, db: Session, coordinator: User, organiser: User, event: Event, hall: Venue, room: Venue
) -> None:
    main = book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED, is_primary=True, expected_attendees=100)
    breakout = book(db, event, room, coordinator, at(13), at(15), purpose="Breakout A")

    response = await event_bookings(client, organiser, event)

    assert response.status_code == 200
    by_id = {b["id"]: b for b in response.json()["bookings"]}
    expected = {
        "purpose": "Main venue", "status": "approved", "is_primary": True, "next_action": "none",
        "unavailability": None, "preparation_status": "not_started", "reference": main.reference,
    }
    assert {key: by_id[str(main.id)][key] for key in expected} == expected
    assert by_id[str(breakout.id)]["next_action"] == "venue_staff_to_decide"
    assert response.json()["primary_booking_id"] == str(main.id)


async def test_tc_us24_14_only_the_events_own_organiser_and_not_an_attendee(
    client: AsyncClient, db: Session, organiser: User, event: Event
) -> None:
    other_organiser = make_user(db, UserRole.ORGANISER)
    attendee_user = make_user(db, UserRole.ATTENDEE)

    assert (await event_bookings(client, other_organiser, event)).status_code == 404
    assert (await event_bookings(client, attendee_user, event)).status_code == 403


@pytest.mark.parametrize("status", [EventStatus.SUBMITTED, EventStatus.UNDER_REVIEW, EventStatus.AWAITING_CLARIFICATION])
async def test_tc_us24_14_the_organiser_reads_nothing_before_the_request_is_approved(
    client: AsyncClient, db: Session, organiser: User, event: Event, status: EventStatus
) -> None:
    event.status = status
    db.flush()

    assert (await event_bookings(client, organiser, event)).status_code == 404


async def test_tc_us24_15_unavailability_says_why_a_venue_needs_replacing(
    client: AsyncClient, db: Session, coordinator: User, organiser: User, event: Event, hall: Venue, room: Venue
) -> None:
    rejected = book(
        db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.REJECTED,
        rejection_reason="Booked for exams", alternative_suggestion="Try the auditorium",
    )
    closed = make_venue(db, name="Closed Room", is_active=False, room_layouts=["classroom"])
    on_closed = book(db, event, closed, coordinator, at(13), at(15), status=VenueBookingStatus.APPROVED, is_primary=True)
    pending = book(db, event, room, coordinator, at(13), at(15))

    by_id = {b["id"]: b for b in (await event_bookings(client, organiser, event)).json()["bookings"]}

    assert by_id[str(rejected.id)]["unavailability"] == {
        "kind": "rejected", "reason": "Booked for exams", "alternative_suggestion": "Try the auditorium",
    }
    assert by_id[str(rejected.id)]["next_action"] == "coordinator_to_rebook"
    assert by_id[str(on_closed.id)]["unavailability"] == {"kind": "venue_inactive", "reason": None, "alternative_suggestion": None}
    assert by_id[str(on_closed.id)]["next_action"] == "coordinator_to_rebook"
    assert (by_id[str(pending.id)]["unavailability"], by_id[str(pending.id)]["next_action"]) == (None, "venue_staff_to_decide")


# --- TC-US24-16 withdrawing one booking, approved ones too (D69, D77) ---


async def test_tc_us24_16_withdrawing_an_approved_booking_frees_it_tells_venue_staff_and_leaves_the_rest(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, hall: Venue, room: Venue,
    notifier: FakeNotifier,
) -> None:
    main = book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED, is_primary=True,
                decided_by_user_id=staff.id)
    breakout = book(db, event, room, coordinator, at(13), at(15), status=VenueBookingStatus.APPROVED,
                    decided_by_user_id=staff.id, purpose="Breakout A")
    before = (breakout.status, breakout.starts_at, breakout.ends_at, breakout.is_primary)

    response = await client.post(f"{BOOKINGS}/{breakout.id}/withdraw", headers=auth(coordinator))

    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"
    # D77: who approved it is kept.
    assert response.json()["decided_by_user_id"] == str(staff.id)
    assert [call["email"] for call in notifier.booking_withdrawals] == [staff.email]
    assert notifier.booking_withdrawals[0]["booking_id"] == breakout.id
    db.expire_all()
    stored_main = db.get(VenueBooking, main.id)
    assert (stored_main.status, stored_main.is_primary) == (VenueBookingStatus.APPROVED, True)
    assert before[1:3] == (db.get(VenueBooking, breakout.id).starts_at, db.get(VenueBooking, breakout.id).ends_at)

    # The window is free again, so the coordinator can request it once more.
    again = await request_venue(client, coordinator, event, room, at(13), at(15), purpose="Breakout A")
    assert again.status_code == 201


async def test_tc_us24_16_a_rejected_booking_cannot_be_withdrawn(
    client: AsyncClient, db: Session, coordinator: User, event: Event, room: Venue
) -> None:
    rejected = book(db, event, room, coordinator, at(13), at(15), status=VenueBookingStatus.REJECTED)

    response = await client.post(f"{BOOKINGS}/{rejected.id}/withdraw", headers=auth(coordinator))

    assert response.status_code == 409
    assert response.json() == {"code": "BOOKING_NOT_LIVE", "status": "rejected"}


async def test_tc_us24_16_withdrawing_a_requested_booking_tells_nobody(
    client: AsyncClient, db: Session, coordinator: User, event: Event, room: Venue, notifier: FakeNotifier
) -> None:
    pending = book(db, event, room, coordinator, at(13), at(15))

    assert (await client.post(f"{BOOKINGS}/{pending.id}/withdraw", headers=auth(coordinator))).status_code == 200
    assert notifier.booking_withdrawals == []


# --- TC-US24-17 a rejection keeps the event where it is ---


@pytest.mark.parametrize("status", [EventStatus.APPROVED, EventStatus.PLANNING])
async def test_tc_us24_17_rejecting_one_venue_keeps_the_event_and_the_approved_one(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, hall: Venue, room: Venue,
    status: EventStatus,
) -> None:
    if status == EventStatus.PLANNING:
        event.start_at, event.end_at, event.capacity = at(9), at(17), 100
    event.status = status
    db.flush()
    main = book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED, is_primary=True)
    breakout = book(db, event, room, coordinator, at(13), at(15))

    rejected = await client.post(f"{BOOKINGS}/{breakout.id}/reject", json={}, headers=auth(staff))

    assert rejected.status_code == 200
    db.expire_all()
    assert db.get(Event, event.id).status == status
    stored = db.get(VenueBooking, main.id)
    assert (stored.status, stored.is_primary) == (VenueBookingStatus.APPROVED, True)


# --- TC-US24-18 venues arranged (D67, D72) ---


async def arranged(client: AsyncClient, coordinator: User, event: Event) -> tuple[bool, int, int | None]:
    listed = (await event_bookings(client, coordinator, event)).json()
    return listed["venues_arranged"], listed["allocated_attendees"], listed["expected_attendees"]


async def test_tc_us24_18_no_bookings_or_a_requested_one_is_not_arranged(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue
) -> None:
    assert await arranged(client, coordinator, event) == (False, 0, 100)
    book(db, event, hall, coordinator, at(9), at(12), is_primary=True, expected_attendees=100)
    assert await arranged(client, coordinator, event) == (False, 100, 100)


async def test_tc_us24_18_every_live_booking_approved_with_one_primary_and_enough_allocated_is_arranged(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue, room: Venue
) -> None:
    book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED, is_primary=True, expected_attendees=60)
    # A shortfall: 60 allocated for 100 expected (CS3-24).
    assert await arranged(client, coordinator, event) == (False, 60, 100)

    book(db, event, room, coordinator, at(13), at(15), status=VenueBookingStatus.APPROVED, expected_attendees=40)
    assert await arranged(client, coordinator, event) == (True, 100, 100)

    # Withdrawn and rejected bookings don't count either way.
    book(db, event, room, coordinator, at(9), at(10), status=VenueBookingStatus.REJECTED, expected_attendees=40)
    assert await arranged(client, coordinator, event) == (True, 100, 100)


async def test_tc_us24_18_approved_bookings_with_no_primary_are_not_arranged(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue
) -> None:
    book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED, expected_attendees=100)

    assert (await arranged(client, coordinator, event))[0] is False


async def test_tc_us24_18_preparation_does_not_change_arranged(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue
) -> None:
    booking = book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED, is_primary=True,
                   expected_attendees=100)
    for preparation in ("not_started", "in_progress", "ready"):
        booking.preparation_status = preparation
        db.flush()
        assert (await arranged(client, coordinator, event))[0] is True


async def test_tc_us24_18_an_online_event_is_arranged_without_venues(
    client: AsyncClient, db: Session, coordinator: User, organiser: User
) -> None:
    online = make_event(
        db, status=EventStatus.APPROVED, coordinator_id=coordinator.id, delivery_mode=DeliveryMode.ONLINE,
        venue_name=None, room_number=None, join_link="https://example.com/j/2",
    )

    assert (await arranged(client, coordinator, online))[0] is True


async def test_tc_us24_18_with_no_expected_attendance_any_allocation_is_enough(
    client: AsyncClient, db: Session, coordinator: User, event: Event, hall: Venue
) -> None:
    event.expected_attendees = None
    db.flush()
    book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED, is_primary=True, expected_attendees=5)

    assert await arranged(client, coordinator, event) == (True, 5, None)


# --- TC-US24-28 Venue staff set preparation (D73) ---


def preparation_url(booking: VenueBooking | uuid.UUID) -> str:
    booking_id = booking if isinstance(booking, uuid.UUID) else booking.id
    return f"{BOOKINGS}/{booking_id}/preparation"


async def test_tc_us24_28_venue_staff_move_an_approved_booking_through_preparation(
    client: AsyncClient, db: Session, coordinator: User, organiser: User, staff: User, event: Event, hall: Venue, room: Venue
) -> None:
    main = book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED, is_primary=True)
    other = book(db, event, room, coordinator, at(13), at(15), status=VenueBookingStatus.APPROVED)

    for value in ("in_progress", "ready", "not_started", "ready"):
        response = await client.post(preparation_url(main), json={"preparation_status": value}, headers=auth(staff))
        assert (response.status_code, response.json()["preparation_status"]) == (200, value)

    for reader in (coordinator, organiser):
        by_id = {b["id"]: b for b in (await event_bookings(client, reader, event)).json()["bookings"]}
        assert by_id[str(main.id)]["preparation_status"] == "ready"
        assert by_id[str(other.id)]["preparation_status"] == "not_started"


@pytest.mark.parametrize("value", ["done", "", "Ready", None])
async def test_tc_us24_28_an_unknown_preparation_status_is_refused(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, hall: Venue, value: object
) -> None:
    main = book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED)

    response = await client.post(preparation_url(main), json={"preparation_status": value}, headers=auth(staff))

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_BOOKING"
    assert response.json()["fields"] == ["preparation_status"]


@pytest.mark.parametrize(
    "status", [VenueBookingStatus.REQUESTED, VenueBookingStatus.REJECTED, VenueBookingStatus.WITHDRAWN]
)
async def test_tc_us24_28_only_an_approved_booking_is_prepared(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, hall: Venue, status: VenueBookingStatus
) -> None:
    booking = book(db, event, hall, coordinator, at(9), at(12), status=status)

    response = await client.post(preparation_url(booking), json={"preparation_status": "ready"}, headers=auth(staff))

    assert response.status_code == 409
    assert response.json() == {"code": "BOOKING_NOT_APPROVED", "status": status.value}


async def test_tc_us24_28_only_venue_staff_set_preparation(
    client: AsyncClient, db: Session, coordinator: User, organiser: User, staff: User, event: Event, hall: Venue
) -> None:
    main = book(db, event, hall, coordinator, at(9), at(12), status=VenueBookingStatus.APPROVED)
    lead = make_user(db, UserRole.COORDINATOR_LEAD)

    for user in (coordinator, lead, organiser):
        response = await client.post(preparation_url(main), json={"preparation_status": "ready"}, headers=auth(user))
        assert response.status_code == 403
    unknown = await client.post(preparation_url(uuid.uuid4()), json={"preparation_status": "ready"}, headers=auth(staff))
    assert unknown.status_code == 404
    assert db.scalar(select(VenueBooking.preparation_status).where(VenueBooking.id == main.id)) == "not_started"


# --- TC-US24-20 the request read gives the form the event's own dates (D65, SCRUM-129) ---


async def test_tc_us24_20_the_request_read_carries_start_at_and_end_at_once_set(
    client: AsyncClient, db: Session, organiser: User, event: Event
) -> None:
    approved = (await client.get(f"/api/v1/event-requests/{event.id}", headers=auth(organiser))).json()
    assert (approved["start_at"], approved["end_at"]) == (None, None)

    event.start_at, event.end_at, event.capacity = at(10), at(16), 100
    event.status = EventStatus.PLANNING
    db.flush()
    planned = (await client.get(f"/api/v1/event-requests/{event.id}", headers=auth(organiser))).json()
    assert (datetime.fromisoformat(planned["start_at"]), datetime.fromisoformat(planned["end_at"])) == (at(10), at(16))
