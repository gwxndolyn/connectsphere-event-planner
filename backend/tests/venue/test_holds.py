"""US25 (SCRUM-93) PR 2: place, confirm and decline a hold, its expiry and warnings on read, and holds in a request's
conflict check, search, the calendar and a cancel. The schema is PR 1's (test_hold_schema.py); see
docs/testing/US25-venue-holds.md."""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.event.models import Event, EventStatus
from app.main import app
from app.user.models import User, UserRole
from app.venue.booking_service import venues_arranged
from app.venue.models import Venue, VenueBooking, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue

pytestmark = pytest.mark.anyio

HOLDS_URL = "/api/v1/venue-holds"
START = NOW + timedelta(days=7)
END = START + timedelta(hours=2)
EXPIRES = NOW + timedelta(days=3)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def at(moment: datetime) -> None:
    """Move the app's clock: a hold lapses on the next read after its expiry (D103)."""
    app.dependency_overrides[get_now] = lambda: moment


def hold_body(event: Event, venue: Venue, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "event_id": str(event.id),
        "venue_id": str(venue.id),
        "starts_at": START.isoformat(),
        "ends_at": END.isoformat(),
        "expected_attendees": 30,
        "room_layout": "theatre",
        "purpose": "Main venue",
        "hold_expires_at": EXPIRES.isoformat(),
    }
    body.update(overrides)
    return body


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    return make_event(db, name="Data Science Summit", status=EventStatus.APPROVED, coordinator_id=coordinator.id)


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db, name="Hall A")


async def place(client: AsyncClient, staff: User, event: Event, venue: Venue, **overrides: object):
    return await client.post(HOLDS_URL, headers=auth(staff), json=hold_body(event, venue, **overrides))


async def bookings(client: AsyncClient, user: User, event: Event) -> dict:
    response = await client.get(f"/api/v1/events/{event.id}/venue-bookings", headers=auth(user))
    assert response.status_code == 200, response.text
    return response.json()


# --- AC 1: placing a hold ---


async def test_tc_us25_07_venue_staff_hold_a_venue_and_the_coordinator_is_told(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, notifier: FakeNotifier
) -> None:
    response = await place(client, staff, event, venue)

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["status"], body["is_primary"], body["next_action"]) == ("held", False, "coordinator_to_confirm")
    assert datetime.fromisoformat(body["hold_expires_at"]) == EXPIRES
    assert (body["held_by_user_id"], body["requested_by_user_id"]) == (str(staff.id), str(staff.id))
    assert [(call["email"], call["stage"], call["venue_name"]) for call in notifier.holds] == [
        (coordinator.email, "placed", "Hall A")
    ]


@pytest.mark.parametrize(
    ("expires", "code", "message"),
    [
        (None, "MISSING_REQUIRED_FIELD", None),
        ((NOW - timedelta(minutes=1)).isoformat(), "INVALID_HOLD", "The hold must expire in the future."),
        ((NOW + timedelta(days=14, minutes=1)).isoformat(), "INVALID_HOLD", "A hold can last at most 14 days."),
        ((START + timedelta(minutes=1)).isoformat(), "INVALID_HOLD", "The hold must expire before the held time starts."),
        ("2026-10-04T09:00:00", "INVALID_HOLD", "Give the expiry with a timezone offset, e.g. 2026-10-08T17:00:00+08:00."),
    ],
    ids=["missing", "past", "over 14 days", "after the start", "no offset"],
)
async def test_tc_us25_08_the_expiry_is_required_future_within_14_days_and_before_the_start(
    client: AsyncClient, db: Session, staff: User, event: Event, venue: Venue, expires: str | None, code: str,
    message: str | None,
) -> None:
    response = await place(client, staff, event, venue, hold_expires_at=expires)

    assert response.status_code == 422
    assert (response.json()["code"], response.json()["fields"]) == (code, ["hold_expires_at"])
    if message:
        assert response.json()["errors"] == {"hold_expires_at": message}
    assert db.query(VenueBooking).count() == 0


async def test_tc_us25_08_a_hold_is_checked_as_a_request_is(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    draft = make_event(db, status=EventStatus.DRAFT, coordinator_id=coordinator.id)
    confirmed = make_event(db, status=EventStatus.CONFIRMED, coordinator_id=coordinator.id)

    too_many = await place(client, staff, event, venue, expected_attendees=41)
    hidden = await place(client, staff, draft, venue)
    unbookable = await place(client, staff, confirmed, venue)

    assert (too_many.status_code, too_many.json()["code"]) == (422, "VENUE_CAPACITY_EXCEEDED")
    assert (hidden.status_code, hidden.json()) == (404, {"code": "NOT_FOUND"})
    assert (unbookable.status_code, unbookable.json()["code"]) == (409, "EVENT_NOT_BOOKABLE")


async def test_tc_us25_09_venue_staff_list_the_events_they_may_hold_a_venue_for(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event
) -> None:
    planning = make_event(db, name="Alumni Night", status=EventStatus.PLANNING, coordinator_id=coordinator.id)
    make_event(db, name="Not Yet", status=EventStatus.UNDER_REVIEW)

    response = await client.get(f"{HOLDS_URL}/events", headers=auth(staff))

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["events"]] == [str(planning.id), str(event.id)]


# --- AC 2, 6: it blocks the window, but isn't a booking ---


async def test_tc_us25_10_a_hold_keeps_requests_and_search_out_of_its_window(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    held = (await place(client, staff, event, venue)).json()
    other = make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)

    request = await client.post(
        "/api/v1/venue-bookings",
        headers=auth(coordinator),
        json={k: v for k, v in hold_body(other, venue).items() if k != "hold_expires_at"},
    )
    search = await client.get(
        "/api/v1/venues/available",
        headers=auth(coordinator),
        params={"date": "2026-10-08", "start_time": "09:00", "end_time": "11:00", "attendees": "10"},
    )

    assert (request.status_code, request.json()["code"]) == (409, "VENUE_UNAVAILABLE")
    assert request.json()["conflict"]["kind"] == "booking"
    assert str(venue.id) not in search.text
    assert held["status"] == "held"


async def test_tc_us25_10_a_hold_is_not_one_of_the_events_venues(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    await place(client, staff, event, venue)

    listed = await bookings(client, coordinator, event)

    assert (listed["venues_arranged"], listed["primary_booking_id"], listed["allocated_attendees"]) == (False, None, 0)
    assert venues_arranged(db, event) is False


# --- AC 5: confirming, then approval before the expiry ---


async def test_tc_us25_11_the_coordinator_confirms_a_hold_into_a_request(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, notifier: FakeNotifier
) -> None:
    held = (await place(client, staff, event, venue)).json()

    response = await client.post(f"/api/v1/venue-bookings/{held['id']}/confirm", headers=auth(coordinator))

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["requested_by_user_id"], body["is_primary"]) == ("requested", str(coordinator.id), True)
    assert (body["held_by_user_id"], datetime.fromisoformat(body["hold_expires_at"])) == (str(staff.id), EXPIRES)
    assert [call["email"] for call in notifier.venue_bookings] == [staff.email]


async def test_tc_us25_11_only_the_events_coordinator_confirms_and_only_a_hold(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    held = (await place(client, staff, event, venue)).json()
    url = f"/api/v1/venue-bookings/{held['id']}/confirm"

    stranger = await client.post(url, headers=auth(make_user(db, UserRole.COORDINATOR)))
    await client.post(url, headers=auth(coordinator))
    again = await client.post(url, headers=auth(coordinator))

    assert (stranger.status_code, stranger.json()) == (404, {"code": "NOT_FOUND"})
    assert (again.status_code, again.json()) == (409, {"code": "HOLD_NOT_HELD", "status": "requested"})


async def test_tc_us25_12_venue_staff_approve_a_confirmed_hold_before_it_expires(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    held = (await place(client, staff, event, venue)).json()
    await client.post(f"/api/v1/venue-bookings/{held['id']}/confirm", headers=auth(coordinator))
    other_staff = make_user(db, UserRole.VENUE_STAFF)

    approved = await client.post(f"/api/v1/venue-bookings/{held['id']}/approve", headers=auth(other_staff), json={})

    assert (approved.status_code, approved.json()["status"]) == (200, "approved")


async def test_tc_us25_12_a_confirmed_hold_not_approved_by_its_expiry_lapses(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, notifier: FakeNotifier
) -> None:
    held = (await place(client, staff, event, venue)).json()
    await client.post(f"/api/v1/venue-bookings/{held['id']}/confirm", headers=auth(coordinator))
    at(EXPIRES)

    late = await client.post(f"/api/v1/venue-bookings/{held['id']}/approve", headers=auth(staff), json={})

    assert (late.status_code, late.json()) == (409, {"code": "BOOKING_NOT_PENDING", "status": "expired"})
    assert notifier.holds[-1]["stage"] == "expired"


# --- AC 7: declining ---


async def test_tc_us25_13_the_coordinator_declines_a_hold_and_the_window_is_free(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    held = (await place(client, staff, event, venue)).json()

    declined = await client.post(f"/api/v1/venue-bookings/{held['id']}/withdraw", headers=auth(coordinator))
    again = await place(client, staff, event, venue)

    assert (declined.status_code, declined.json()["status"]) == (200, "withdrawn")
    assert again.status_code == 201


# --- AC 3, 4: expiry and the warnings, on read (D103) ---


async def test_tc_us25_14_a_hold_lapses_on_the_next_read_after_its_expiry(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, notifier: FakeNotifier
) -> None:
    held = (await place(client, staff, event, venue)).json()
    at(EXPIRES)

    listed = await bookings(client, coordinator, event)
    retaken = await place(client, staff, event, venue, hold_expires_at=(EXPIRES + timedelta(days=1)).isoformat())

    row = next(b for b in listed["bookings"] if b["id"] == held["id"])
    assert (row["status"], datetime.fromisoformat(row["expired_at"])) == ("expired", EXPIRES)
    assert retaken.status_code == 201  # the window is free again (AC 3)
    db.refresh(event)
    assert event.status == EventStatus.APPROVED  # the event stays as it was
    # Nothing read it in its last 24 hours, so there was no warning: the coordinator hears it expired (D103).
    assert [call["stage"] for call in notifier.holds if call["booking_id"] == uuid.UUID(held["id"])] == [
        "placed",
        "expired",
    ]


async def test_tc_us25_15_the_coordinator_is_warned_once_in_the_last_24_hours(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, notifier: FakeNotifier
) -> None:
    await place(client, staff, event, venue)

    at(EXPIRES - timedelta(hours=25))
    await bookings(client, coordinator, event)
    at(EXPIRES - timedelta(hours=23))
    await bookings(client, coordinator, event)
    await bookings(client, coordinator, event)

    assert [call["stage"] for call in notifier.holds] == ["placed", "expiring"]


async def test_tc_us25_15_a_short_hold_warns_at_once(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, notifier: FakeNotifier
) -> None:
    await place(client, staff, event, venue, hold_expires_at=(NOW + timedelta(hours=6)).isoformat())
    await bookings(client, coordinator, event)

    assert [call["stage"] for call in notifier.holds] == ["placed", "expiring"]


# --- The calendar and a cancel ---


async def test_tc_us25_16_the_calendar_shows_a_hold_until_it_expires(
    client: AsyncClient, db: Session, staff: User, event: Event, venue: Venue
) -> None:
    await place(client, staff, event, venue)
    url = f"/api/v1/venues/{venue.id}/calendar?from=2026-10-08&to=2026-10-08"

    shown = (await client.get(url, headers=auth(staff))).json()["items"]
    at(EXPIRES)
    gone = (await client.get(url, headers=auth(staff))).json()["items"]

    assert [(item["kind"], item["label"]) for item in shown] == [("hold", "Hold")]
    assert datetime.fromisoformat(shown[0]["booking"]["hold_expires_at"]) == EXPIRES
    assert gone == []


async def test_tc_us25_17_cancelling_the_event_releases_its_holds(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    held = (await place(client, staff, event, venue)).json()

    cancelled = await client.post(
        f"/api/v1/event-requests/{event.id}/cancel", headers=auth(coordinator), json={"reason": "Called off"}
    )

    assert cancelled.status_code == 200, cancelled.text
    row = db.get(VenueBooking, uuid.UUID(held["id"]))
    db.refresh(row)
    assert row.status == VenueBookingStatus.WITHDRAWN
