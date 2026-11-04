"""US20 AC 2 (SCRUM-147): Venue staff edit a venue's capacity or opening hours. The live future bookings the new values
no longer fit read "Needs review" (`unavailability.kind: "venue_changed"`, D119), and Venue staff and each affected
event's coordinator are told once. Nothing about the booking changes. See docs/testing/US20-venue-catalogue.md."""

from datetime import time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBooking, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

# make_venue: capacity 40, open 08:00 to 20:00, 30 minutes' setup and 15 minutes' turnaround. A booking from 09:00
# to 11:00 Singapore time occupies 08:30 to 11:15.
START = NOW + timedelta(days=7)
END = START + timedelta(hours=2)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


@pytest.fixture
def staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    return make_event(
        db, name="Data Science Summit", status=EventStatus.PLANNING, coordinator_id=coordinator.id, start_at=START, end_at=END
    )


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db, name="Hall A")


def booking(db: Session, event: Event, venue: Venue, user: User, **overrides: object) -> VenueBooking:
    fields: dict[str, object] = {"starts_at": START, "ends_at": END}
    fields.update(overrides)
    return make_venue_booking(db, event=event, venue=venue, user=user, **fields)


async def edit(client: AsyncClient, staff: User, venue: Venue, **changes: object) -> None:
    response = await client.patch(f"/api/v1/venues/{venue.id}", headers=auth(staff), json=changes)
    assert response.status_code == 200, response.text


async def bookings(client: AsyncClient, coordinator: User, event: Event) -> dict[str, dict]:
    response = await client.get(f"/api/v1/events/{event.id}/venue-bookings", headers=auth(coordinator))
    assert response.status_code == 200, response.text
    return {row["reference"]: row for row in response.json()["bookings"]}


async def test_tc_us20_20_a_capacity_drop_flags_approved_and_requested_future_bookings_and_changes_neither(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    approved = booking(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, expected_attendees=30)
    requested = booking(
        db, event, venue, coordinator, starts_at=START + timedelta(days=1), ends_at=END + timedelta(days=1),
        expected_attendees=25, is_primary=False,
    )
    before = {row.reference: (row.status, row.expected_attendees, row.occupied_starts_at, row.occupied_ends_at) for row in (approved, requested)}

    await edit(client, staff, venue, capacity=20)

    rows = await bookings(client, coordinator, event)
    for reference, expected in ((approved.reference, 30), (requested.reference, 25)):
        row = rows[reference]
        assert row["unavailability"] == {
            "kind": "venue_changed",
            "reason": None,
            "alternative_suggestion": None,
            "block": None,
            "flagged_at": None,
            "detail": "capacity",
            "capacity": 20,
            "opens_at": None,
            "closes_at": None,
        }
        assert row["next_action"] == "coordinator_to_rebook"
        assert row["expected_attendees"] == expected
    db.expire_all()
    after = {row.reference: (row.status, row.expected_attendees, row.occupied_starts_at, row.occupied_ends_at) for row in (approved, requested)}
    assert after == before


async def test_tc_us20_21_an_hours_change_flags_a_booking_whose_occupied_window_now_falls_outside(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    flagged = booking(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED)
    # 14:00 to 15:00 occupies 13:30 to 15:15, inside 09:00 to 18:00.
    fits = booking(
        db, event, venue, coordinator, starts_at=START + timedelta(hours=5), ends_at=START + timedelta(hours=6), is_primary=False
    )

    await edit(client, staff, venue, opens_at="09:00:00", closes_at="18:00:00")

    rows = await bookings(client, coordinator, event)
    # Setup from 08:30 now starts before opening.
    assert rows[flagged.reference]["unavailability"]["kind"] == "venue_changed"
    assert rows[flagged.reference]["unavailability"]["detail"] == "hours"
    assert rows[flagged.reference]["unavailability"]["opens_at"] == "09:00:00"
    assert rows[flagged.reference]["unavailability"]["closes_at"] == "18:00:00"
    assert rows[flagged.reference]["unavailability"]["capacity"] is None
    assert rows[fits.reference]["unavailability"] is None
    db.expire_all()
    assert (flagged.occupied_starts_at, flagged.occupied_ends_at) == (START - timedelta(minutes=30), END + timedelta(minutes=15))


async def test_tc_us20_22_fitting_past_withdrawn_and_rejected_bookings_are_not_flagged(
    client: AsyncClient, db: Session, notifier: FakeNotifier, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    fits = booking(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, expected_attendees=15)
    past = booking(
        db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, starts_at=NOW - timedelta(days=2),
        ends_at=NOW - timedelta(days=2) + timedelta(hours=2), is_primary=False,
    )
    withdrawn = booking(
        db, event, venue, coordinator, status=VenueBookingStatus.WITHDRAWN, starts_at=START + timedelta(days=1),
        ends_at=END + timedelta(days=1), is_primary=False,
    )
    rejected = booking(
        db, event, venue, coordinator, status=VenueBookingStatus.REJECTED, starts_at=START + timedelta(days=2),
        ends_at=END + timedelta(days=2), is_primary=False, rejection_reason="Double-booked",
    )

    await edit(client, staff, venue, capacity=20)

    rows = await bookings(client, coordinator, event)
    assert rows[fits.reference]["unavailability"] is None
    assert rows[past.reference]["unavailability"] is None
    assert rows[withdrawn.reference]["unavailability"] is None
    # A rejected booking keeps reading why it was rejected.
    assert rows[rejected.reference]["unavailability"]["kind"] == "rejected"
    assert notifier.booking_reviews == []


async def test_tc_us20_23_venue_staff_and_the_coordinator_are_each_told_once(
    client: AsyncClient, db: Session, notifier: FakeNotifier, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    other_staff = make_user(db, UserRole.VENUE_STAFF)
    make_user(db, UserRole.VENUE_STAFF, active=False)
    affected = booking(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, expected_attendees=30)

    await edit(client, staff, venue, capacity=20, name="Hall A (renovated)")

    assert sorted(call["email"] for call in notifier.booking_reviews) == sorted([staff.email, other_staff.email, coordinator.email])
    [call] = [call for call in notifier.booking_reviews if call["email"] == coordinator.email]
    assert call == {
        "email": coordinator.email,
        "event_id": event.id,
        "event_name": "Data Science Summit",
        "venue_name": "Hall A (renovated)",
        "reference": affected.reference,
        "starts_at": affected.starts_at,
        "ends_at": affected.ends_at,
        "reason": "capacity is now 20, below the 30 expected",
    }

    # Lowering it again tells nobody: the booking already needed review before this edit.
    notifier.booking_reviews.clear()
    await edit(client, staff, venue, capacity=10)
    assert notifier.booking_reviews == []


async def test_tc_us20_23_a_coordinator_who_is_also_venue_staff_is_told_once(
    client: AsyncClient, db: Session, notifier: FakeNotifier, staff: User, venue: Venue
) -> None:
    both = make_user(db, UserRole.COORDINATOR, UserRole.VENUE_STAFF)
    event = make_event(db, name="Careers Fair", status=EventStatus.PLANNING, coordinator_id=both.id, start_at=START, end_at=END)
    booking(db, event, venue, both, status=VenueBookingStatus.APPROVED)

    await edit(client, staff, venue, closes_at="11:00:00")

    assert sorted(call["email"] for call in notifier.booking_reviews) == sorted([staff.email, both.email])
    assert {call["reason"] for call in notifier.booking_reviews} == {"the venue now closes at 11:00"}


async def test_tc_us20_24_an_edit_to_name_or_location_sends_nothing(
    client: AsyncClient, db: Session, notifier: FakeNotifier, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    # Already over capacity (the venue was edited before this change landed): only a capacity or hours edit tells.
    booking(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, expected_attendees=50)

    await edit(client, staff, venue, name="Hall A North", location="Block B, Level 2")
    # Resending the stored capacity and hours, as a form posting every field does, isn't a change either.
    await edit(client, staff, venue, capacity=40, opens_at="08:00:00", closes_at="20:00:00")

    assert notifier.booking_reviews == []


async def test_tc_us20_25_raising_capacity_back_clears_the_flag(
    client: AsyncClient, db: Session, notifier: FakeNotifier, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    affected = booking(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, expected_attendees=30)
    await edit(client, staff, venue, capacity=20)
    assert (await bookings(client, coordinator, event))[affected.reference]["unavailability"]["kind"] == "venue_changed"

    notifier.booking_reviews.clear()
    await edit(client, staff, venue, capacity=30)

    row = (await bookings(client, coordinator, event))[affected.reference]
    assert row["unavailability"] is None
    assert row["next_action"] == "none"
    assert notifier.booking_reviews == []


async def test_tc_us20_26_a_failing_notifier_doesnt_fail_the_edit(
    client: AsyncClient, db: Session, notifier: FakeNotifier, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    affected = booking(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, expected_attendees=30)
    notifier.fail = True

    response = await client.patch(f"/api/v1/venues/{venue.id}", headers=auth(staff), json={"capacity": 20})

    assert response.status_code == 200
    assert response.json()["capacity"] == 20
    db.expire_all()
    assert db.get(Venue, venue.id).capacity == 20
    notifier.fail = False
    assert (await bookings(client, coordinator, event))[affected.reference]["unavailability"]["detail"] == "capacity"
