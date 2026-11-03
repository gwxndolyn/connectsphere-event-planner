"""US23b (SCRUM-91) PR 2: an affected event goes back to Planning; the coordinator requests a replacement venue,
which replaces the original once Venue staff approve it, and attendees hear only then; Venue staff end a period
early and the coordinator asks to restore the original, which Venue staff confirm or decline. The schema is PR 1's
(test_replacement_schema.py); see docs/testing/US23b-replacement-venue.md."""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import AuditAction, Event, EventAuditEntry, EventStatus
from app.registration.models import RegistrationStatus
from app.user.models import User, UserRole
from app.venue.booking_service import venues_arranged
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.factories import (
    NOW,
    make_attendee,
    make_event,
    make_registration,
    make_user,
    make_venue,
    make_venue_block,
    make_venue_booking,
)

pytestmark = pytest.mark.anyio

# Venue buffers from make_venue: 30 minutes' setup, 15 minutes' turnaround; open 08:00 to 20:00 Singapore.
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
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def event(db: Session, coordinator: User, organiser: User) -> Event:
    event = make_event(
        db, name="Data Science Summit", status=EventStatus.PLANNING, coordinator_id=coordinator.id,
        start_at=START, end_at=END,
    )
    event.created_by_user_id = organiser.id
    db.flush()
    return event


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db, name="Hall A")


@pytest.fixture
def original(db: Session, event: Event, venue: Venue, coordinator: User, staff: User) -> VenueBooking:
    """The event's approved primary venue, before any period."""
    return make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=START, ends_at=END,
        status=VenueBookingStatus.APPROVED, decided_by_user_id=staff.id, is_primary=True,
    )


async def mark(client: AsyncClient, staff: User, venue: Venue, starts_at: datetime = START, ends_at: datetime = END):
    response = await client.post(
        f"/api/v1/venues/{venue.id}/blocks",
        headers=auth(staff),
        json={"starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(), "reason": "maintenance"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def end_early(client: AsyncClient, staff: User, venue: Venue, block_id: str):
    return await client.post(f"/api/v1/venues/{venue.id}/blocks/{block_id}/end", headers=auth(staff))


async def request_replacement(
    client: AsyncClient, coordinator: User, event: Event, venue: Venue, original: VenueBooking, **overrides: object
):
    body: dict[str, object] = {
        "event_id": str(event.id),
        "venue_id": str(venue.id),
        "starts_at": START.isoformat(),
        "ends_at": END.isoformat(),
        "expected_attendees": 30,
        "room_layout": "theatre",
        "purpose": "Main venue",
        "replaces_booking_id": str(original.id),
    }
    body.update(overrides)
    return await client.post("/api/v1/venue-bookings", headers=auth(coordinator), json=body)


async def bookings_of(client: AsyncClient, user: User, event: Event) -> dict[str, dict]:
    response = await client.get(f"/api/v1/events/{event.id}/venue-bookings", headers=auth(user))
    assert response.status_code == 200, response.text
    return {booking["reference"]: booking for booking in response.json()["bookings"]}


# --- AC 1: the event is back in Planning ---


@pytest.mark.parametrize("status", [EventStatus.CONFIRMED, EventStatus.PREPARATION], ids=["confirmed", "preparation"])
async def test_tc_us23b_05_an_affected_event_goes_back_to_planning(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    original: VenueBooking, status: EventStatus,
) -> None:
    event.status = status
    event.confirmed_at = NOW - timedelta(days=1)
    event.confirmed_by_user_id = coordinator.id
    db.flush()

    await mark(client, staff, venue)

    db.refresh(event)
    assert (event.status, event.confirmed_at, event.confirmed_by_user_id) == (EventStatus.PLANNING, None, None)
    entries = db.scalars(
        select(EventAuditEntry).where(EventAuditEntry.event_id == event.id).order_by(EventAuditEntry.seq)
    ).all()
    assert [(e.action, e.field_name, e.previous_value, e.new_value, e.user_id) for e in entries] == [
        (AuditAction.STATUS_CHANGED, "status", status.value, "planning", staff.id),
        (
            AuditAction.CONFIRMATION_CLEARED, "confirmation",
            {"confirmed_at": (NOW - timedelta(days=1)).isoformat(), "confirmed_by": str(coordinator.id)}, None, staff.id,
        ),
    ]
    history = await client.get(f"/api/v1/events/{event.id}/history", headers=auth(coordinator))
    assert history.status_code == 200, history.text


@pytest.mark.parametrize("status", [EventStatus.APPROVED, EventStatus.PLANNING], ids=["approved", "planning"])
async def test_tc_us23b_05_an_event_not_yet_confirmed_keeps_its_status(
    client: AsyncClient, db: Session, staff: User, event: Event, venue: Venue, original: VenueBooking,
    status: EventStatus,
) -> None:
    event.status = status
    db.flush()

    await mark(client, staff, venue)

    db.refresh(event)
    assert event.status == status
    assert db.scalars(select(EventAuditEntry).where(EventAuditEntry.event_id == event.id)).all() == []


async def test_tc_us23b_05_an_unaffected_confirmed_event_stays_confirmed(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    event.status = EventStatus.CONFIRMED
    event.confirmed_at = NOW
    event.confirmed_by_user_id = coordinator.id
    db.flush()

    await mark(client, staff, venue, starts_at=END + timedelta(hours=1), ends_at=END + timedelta(hours=3))

    db.refresh(event)
    assert event.status == EventStatus.CONFIRMED


# --- AC 3: a replacement request ---


async def test_tc_us23b_06_the_coordinator_requests_a_replacement_venue_staff_then_decide(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    original: VenueBooking, notifier: FakeNotifier,
) -> None:
    await mark(client, staff, venue)
    hall_b = make_venue(db, name="Hall B")

    response = await request_replacement(client, coordinator, event, hall_b, original)

    assert response.status_code == 201, response.text
    replacement = response.json()
    assert (replacement["status"], replacement["replaces_booking_id"]) == ("requested", str(original.id))
    # The original stays primary until the replacement is approved (one primary at a time, D68).
    assert replacement["is_primary"] is False
    # Venue staff hear of it like any new request (AC 3).
    assert [(call["email"], str(call["booking_id"])) for call in notifier.venue_bookings] == [(staff.email, replacement["id"])]
    pending = (await client.get("/api/v1/venue-bookings/pending", headers=auth(staff))).json()["bookings"]
    assert [booking["id"] for booking in pending] == [replacement["id"]]
    read = await bookings_of(client, coordinator, event)
    assert read[original.reference]["replacement_booking_id"] == replacement["id"]
    assert read[original.reference]["status"] == "approved"


async def test_tc_us23b_06_only_a_booking_needing_rearrangement_is_replaced(
    client: AsyncClient, db: Session, coordinator: User, event: Event, original: VenueBooking,
) -> None:
    response = await request_replacement(client, coordinator, event, make_venue(db, name="Hall B"), original)

    assert response.status_code == 409
    assert response.json()["code"] == "BOOKING_NOT_REPLACEABLE"


async def test_tc_us23b_06_another_events_booking_is_refused_on_the_field(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    await mark(client, staff, venue)
    other = make_event(db, status=EventStatus.PLANNING, coordinator_id=coordinator.id, start_at=START, end_at=END)

    response = await request_replacement(client, coordinator, other, make_venue(db, name="Hall B"), original)

    assert response.status_code == 422
    assert response.json()["fields"] == ["replaces_booking_id"]


async def test_tc_us23b_06_one_live_replacement_at_a_time(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    await mark(client, staff, venue)
    first = await request_replacement(client, coordinator, event, make_venue(db, name="Hall B"), original)

    second = await request_replacement(client, coordinator, event, make_venue(db, name="Hall C"), original)

    assert second.status_code == 409
    body = second.json()
    assert (body["code"], body["reference"]) == ("REPLACEMENT_EXISTS", first.json()["reference"])
    # Withdrawn, it makes way for another.
    await client.post(f"/api/v1/venue-bookings/{first.json()['id']}/withdraw", headers=auth(coordinator))
    third = await request_replacement(client, coordinator, event, make_venue(db, name="Hall C"), original)
    assert third.status_code == 201, third.text


async def test_tc_us23b_06_a_hold_doesnt_replace_a_booking(
    client: AsyncClient, db: Session, staff: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    await mark(client, staff, venue)

    response = await client.post(
        "/api/v1/venue-holds",
        headers=auth(staff),
        json={
            "event_id": str(event.id), "venue_id": str(make_venue(db, name="Hall B").id),
            "starts_at": START.isoformat(), "ends_at": END.isoformat(), "expected_attendees": 30,
            "room_layout": "theatre", "purpose": "Main venue", "replaces_booking_id": str(original.id),
            "hold_expires_at": (NOW + timedelta(days=2)).isoformat(),
        },
    )

    assert response.status_code == 422
    assert response.json()["fields"] == ["replaces_booking_id"]


# --- AC 4: Replaced once the replacement is approved ---


async def test_tc_us23b_07_approving_the_replacement_replaces_the_original(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    await mark(client, staff, venue)
    hall_b = make_venue(db, name="Hall B")
    replacement = (await request_replacement(client, coordinator, event, hall_b, original)).json()

    approved = await client.post(f"/api/v1/venue-bookings/{replacement['id']}/approve", headers=auth(staff))

    assert approved.status_code == 200, approved.text
    assert (approved.json()["status"], approved.json()["is_primary"]) == ("approved", True)
    read = await bookings_of(client, coordinator, event)
    old = read[original.reference]
    assert (old["status"], old["unavailability"], old["next_action"]) == ("replaced", None, "none")
    assert datetime.fromisoformat(old["replaced_at"]) == NOW
    # Its details stay for the history: venue, times and who approved it.
    assert (old["venue"]["name"], old["decided_by_user_id"]) == ("Hall A", str(staff.id))
    assert datetime.fromisoformat(old["starts_at"]) == START
    db.expire_all()
    assert venues_arranged(db, event)


async def test_tc_us23b_07_a_replaced_booking_frees_its_window(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    block = await mark(client, staff, venue)
    replacement = (await request_replacement(client, coordinator, event, make_venue(db, name="Hall B"), original)).json()
    await client.post(f"/api/v1/venue-bookings/{replacement['id']}/approve", headers=auth(staff))
    await end_early(client, staff, venue, block["id"])

    again = make_event(db, status=EventStatus.PLANNING, coordinator_id=coordinator.id, start_at=START, end_at=END)
    response = await client.post(
        "/api/v1/venue-bookings",
        headers=auth(coordinator),
        json={
            "event_id": str(again.id), "venue_id": str(venue.id), "starts_at": START.isoformat(),
            "ends_at": END.isoformat(), "expected_attendees": 30, "room_layout": "theatre", "purpose": "Main venue",
        },
    )

    assert response.status_code == 201, response.text


async def test_tc_us23b_07_a_rejected_replacement_leaves_the_original_needing_rearrangement(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    await mark(client, staff, venue)
    replacement = (await request_replacement(client, coordinator, event, make_venue(db, name="Hall B"), original)).json()

    await client.post(f"/api/v1/venue-bookings/{replacement['id']}/reject", headers=auth(staff), json={"reason": "Full"})

    old = (await bookings_of(client, coordinator, event))[original.reference]
    assert (old["status"], old["next_action"], old["replacement_booking_id"]) == ("approved", "coordinator_to_rebook", None)


# --- AC 7: attendees hear only once a replacement changes what they see ---


async def test_tc_us23b_08_attendees_hear_when_the_primary_venue_changes(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    original: VenueBooking, notifier: FakeNotifier,
) -> None:
    registered = make_attendee(db)
    waitlisted = make_attendee(db)
    withdrawn = make_attendee(db)
    make_registration(db, event, registered)
    make_registration(db, event, waitlisted, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW)
    make_registration(db, event, withdrawn, status=RegistrationStatus.WITHDRAWN)
    await mark(client, staff, venue)
    assert notifier.venue_changes == []
    replacement = (await request_replacement(client, coordinator, event, make_venue(db, name="Hall B"), original)).json()
    assert notifier.venue_changes == []

    await client.post(f"/api/v1/venue-bookings/{replacement['id']}/approve", headers=auth(staff))

    assert sorted(call["email"] for call in notifier.venue_changes) == sorted([registered.email, waitlisted.email])
    assert {(call["venue_name"], call["event_name"]) for call in notifier.venue_changes} == {
        ("Hall B", "Data Science Summit")
    }


async def test_tc_us23b_08_attendees_arent_told_about_a_venue_they_dont_see(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    original: VenueBooking, notifier: FakeNotifier,
) -> None:
    make_registration(db, event, make_attendee(db))
    breakout = make_venue(db, name="Breakout")
    side = make_venue_booking(
        db, event=event, venue=breakout, user=coordinator, starts_at=START, ends_at=END,
        status=VenueBookingStatus.APPROVED, decided_by_user_id=staff.id, purpose="Breakout",
    )
    await mark(client, staff, breakout)
    replacement = (
        await request_replacement(client, coordinator, event, make_venue(db, name="Breakout 2"), side, purpose="Breakout")
    ).json()

    await client.post(f"/api/v1/venue-bookings/{replacement['id']}/approve", headers=auth(staff))

    assert notifier.venue_changes == []
    db.refresh(original)
    assert original.is_primary


async def test_tc_us23b_08_a_failed_attendee_notice_leaves_the_replacement_approved(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    original: VenueBooking, notifier: FakeNotifier,
) -> None:
    make_registration(db, event, make_attendee(db))
    await mark(client, staff, venue)
    replacement = (await request_replacement(client, coordinator, event, make_venue(db, name="Hall B"), original)).json()
    notifier.fail = True

    approved = await client.post(f"/api/v1/venue-bookings/{replacement['id']}/approve", headers=auth(staff))

    assert approved.status_code == 200, approved.text
    db.refresh(original)
    assert original.status == VenueBookingStatus.REPLACED


# --- AC 5: Venue staff end a period early ---


async def test_tc_us23b_09_venue_staff_end_a_period_early(
    client: AsyncClient, db: Session, staff: User, venue: Venue, original: VenueBooking,
) -> None:
    block = await mark(client, staff, venue, starts_at=NOW - timedelta(hours=1), ends_at=END)

    response = await end_early(client, staff, venue, block["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert datetime.fromisoformat(body["ends_at"]) == NOW
    assert datetime.fromisoformat(body["scheduled_ends_at"]) == END
    assert datetime.fromisoformat(body["ended_early_at"]) == NOW
    assert [booking["reference"] for booking in body["affected_bookings"]] == [original.reference]
    stored = db.get(VenueBlock, uuid.UUID(block["id"]))
    db.refresh(stored)
    assert stored.ended_early_by_user_id == staff.id


async def test_tc_us23b_09_a_period_ended_before_it_began_is_empty(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue, original: VenueBooking,
) -> None:
    block = await mark(client, staff, venue)

    body = (await end_early(client, staff, venue, block["id"])).json()

    assert body["starts_at"] == body["ends_at"]
    calendar = await client.get(
        f"/api/v1/venues/{venue.id}/calendar",
        headers=auth(staff),
        params={"from": START.date().isoformat(), "to": START.date().isoformat()},
    )
    assert [item["kind"] for item in calendar.json()["items"]] == ["booking"]


async def test_tc_us23b_09_ending_is_refused_once_over_or_at_another_venue(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue,
) -> None:
    over = make_venue_block(db, venue, NOW - timedelta(hours=3), NOW - timedelta(hours=1))
    block = await mark(client, staff, venue)

    ended = await end_early(client, staff, venue, str(over.id))
    elsewhere = await end_early(client, staff, make_venue(db, name="Hall B"), block["id"])
    as_coordinator = await end_early(client, coordinator, venue, block["id"])

    assert (ended.status_code, ended.json()["code"]) == (409, "BLOCK_ENDED")
    assert (elsewhere.status_code, elsewhere.json()["code"]) == (404, "NOT_FOUND")
    assert as_coordinator.status_code == 403


async def test_tc_us23b_09_a_booking_another_period_still_overlaps_names_that_period(
    client: AsyncClient, db: Session, staff: User, venue: Venue, original: VenueBooking,
) -> None:
    """Matt's #131 review: two periods over one booking. Ending the one that marked it leaves the other named."""
    first = await mark(client, staff, venue)
    second = await mark(client, staff, venue, starts_at=START + timedelta(hours=1), ends_at=END + timedelta(hours=2))

    body = (await end_early(client, staff, venue, first["id"])).json()

    assert body["affected_bookings"] == []
    db.refresh(original)
    assert str(original.rearrangement_block_id) == second["id"]
    assert original.rearrangement_flagged_at == NOW


# --- AC 5: the coordinator asks to restore; Venue staff confirm or decline ---


async def test_tc_us23b_10_restoring_is_refused_while_the_venue_is_still_unavailable(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue, original: VenueBooking,
) -> None:
    await mark(client, staff, venue)

    response = await client.post(f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(coordinator))

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_UNAVAILABLE"


async def test_tc_us23b_10_the_whole_occupied_window_must_be_free(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue, original: VenueBooking,
) -> None:
    """A period only over the setup before the booking still keeps it from its venue."""
    block = await mark(client, staff, venue)
    await end_early(client, staff, venue, block["id"])
    make_venue_block(db, venue, START - timedelta(minutes=45), START - timedelta(minutes=10))

    response = await client.post(f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(coordinator))

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_UNAVAILABLE"


async def test_tc_us23b_10_the_coordinator_asks_once_the_venue_is_free(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    original: VenueBooking, notifier: FakeNotifier,
) -> None:
    block = await mark(client, staff, venue)
    await end_early(client, staff, venue, block["id"])

    response = await client.post(f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(coordinator))

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["next_action"], body["restore_requested_by_user_id"]) == ("venue_staff_to_restore", str(coordinator.id))
    assert [(call["email"], call["booking_reference"]) for call in notifier.restore_requests] == [
        (staff.email, original.reference)
    ]
    listed = (await client.get("/api/v1/venue-bookings/restore-requests", headers=auth(staff))).json()["bookings"]
    assert [booking["id"] for booking in listed] == [str(original.id)]
    again = await client.post(f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(coordinator))
    assert (again.status_code, again.json()["code"]) == (409, "RESTORE_ALREADY_REQUESTED")


async def test_tc_us23b_10_restoring_waits_for_a_live_replacement_to_be_withdrawn(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    block = await mark(client, staff, venue)
    await request_replacement(client, coordinator, event, make_venue(db, name="Hall B"), original)
    await end_early(client, staff, venue, block["id"])

    response = await client.post(f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(coordinator))

    assert (response.status_code, response.json()["code"]) == (409, "REPLACEMENT_EXISTS")


async def test_tc_us23b_10_only_the_events_coordinator_asks(
    client: AsyncClient, db: Session, staff: User, venue: Venue, original: VenueBooking,
) -> None:
    block = await mark(client, staff, venue)
    await end_early(client, staff, venue, block["id"])

    response = await client.post(
        f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(make_user(db, UserRole.COORDINATOR))
    )

    assert response.status_code == 404


async def test_tc_us23b_11_venue_staff_confirm_and_the_booking_is_restored(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    original: VenueBooking, notifier: FakeNotifier,
) -> None:
    block = await mark(client, staff, venue)
    await end_early(client, staff, venue, block["id"])
    await client.post(f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(coordinator))
    decider = make_user(db, UserRole.VENUE_STAFF)

    response = await client.post(f"/api/v1/venue-bookings/{original.id}/restore/confirm", headers=auth(decider))

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["unavailability"], body["next_action"], body["is_primary"]) == (
        "approved", None, "none", True,
    )
    assert body["restore_requested_at"] is None
    db.refresh(original)
    assert (original.rearrangement_block_id, original.rearrangement_flagged_at) == (None, None)
    assert [(call["email"], call["decision"]) for call in notifier.restore_decisions] == [(coordinator.email, "confirmed")]
    db.expire_all()
    assert venues_arranged(db, event)


async def test_tc_us23b_11_a_period_recorded_meanwhile_refuses_the_restore(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue, original: VenueBooking,
) -> None:
    block = await mark(client, staff, venue)
    await end_early(client, staff, venue, block["id"])
    await client.post(f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(coordinator))
    make_venue_block(db, venue, START, END)

    response = await client.post(f"/api/v1/venue-bookings/{original.id}/restore/confirm", headers=auth(staff))

    assert (response.status_code, response.json()["code"]) == (409, "VENUE_UNAVAILABLE")
    db.refresh(original)
    assert original.rearrangement_block_id is not None and original.restore_requested_at is not None


async def test_tc_us23b_11_venue_staff_decline_with_a_reason(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue,
    original: VenueBooking, notifier: FakeNotifier,
) -> None:
    block = await mark(client, staff, venue)
    await end_early(client, staff, venue, block["id"])
    await client.post(f"/api/v1/venue-bookings/{original.id}/restore", headers=auth(coordinator))

    response = await client.post(
        f"/api/v1/venue-bookings/{original.id}/restore/decline", headers=auth(staff), json={"reason": "  Still testing  "}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["next_action"], body["restore_requested_at"]) == ("coordinator_to_rebook", None)
    assert body["unavailability"]["kind"] == "venue_unavailable"
    assert [(call["decision"], call["reason"]) for call in notifier.restore_decisions] == [("declined", "Still testing")]


async def test_tc_us23b_11_nothing_to_decide_without_a_request(
    client: AsyncClient, db: Session, staff: User, venue: Venue, original: VenueBooking,
) -> None:
    await mark(client, staff, venue)

    response = await client.post(f"/api/v1/venue-bookings/{original.id}/restore/confirm", headers=auth(staff))

    assert (response.status_code, response.json()["code"]) == (409, "RESTORE_NOT_REQUESTED")


# --- AC 6: the event is never cancelled for it ---


async def test_tc_us23b_12_no_replacement_never_cancels_the_event(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, original: VenueBooking,
) -> None:
    event.status = EventStatus.CONFIRMED
    event.confirmed_at = NOW
    event.confirmed_by_user_id = coordinator.id
    db.flush()
    await mark(client, staff, venue)
    replacement = (await request_replacement(client, coordinator, event, make_venue(db, name="Hall B"), original)).json()
    await client.post(f"/api/v1/venue-bookings/{replacement['id']}/reject", headers=auth(staff))

    db.refresh(event)
    db.refresh(original)
    assert event.status == EventStatus.PLANNING
    assert original.status == VenueBookingStatus.APPROVED
    # The coordinator may still cancel it the normal way (US9).
    cancelled = await client.post(
        f"/api/v1/event-requests/{event.id}/cancel", headers=auth(coordinator), json={"reason": "No venue."}
    )
    assert cancelled.status_code in (200, 201), cancelled.text


# --- TC-US23B-20's reset: the E2E's event starts clean on every reseed ---


def test_tc_us23b_20_the_seed_clears_the_replacement_demo(db: Session, staff: User) -> None:
    from app.seed import REPLACEMENT_EVENT, seed, seed_id

    seed(db, now=NOW)
    event = db.get(Event, seed_id("event", REPLACEMENT_EVENT.slug))
    assert (event.name, event.status, event.coordinator_id) == (
        "Replacement Venue Demo", EventStatus.APPROVED, seed_id("user", "event-coordinator"),
    )
    hall_a, hall_b = make_venue(db, name="Hall Y"), make_venue(db, name="Hall Z")
    block = make_venue_block(db, hall_a, START, END, created_by_user_id=staff.id)
    replaced = make_venue_booking(
        db, event=event, venue=hall_a, user=staff, starts_at=START, ends_at=END, status=VenueBookingStatus.REPLACED,
        decided_at=NOW, is_primary=True, rearrangement_block_id=block.id, rearrangement_flagged_at=NOW,
    )
    make_venue_booking(
        db, event=event, venue=hall_b, user=staff, starts_at=START, ends_at=END, status=VenueBookingStatus.APPROVED,
        is_primary=True, replaces_booking_id=replaced.id,
    )
    event_id, block_id = event.id, block.id

    seed(db, now=NOW)

    db.expire_all()
    assert db.scalars(select(VenueBooking).where(VenueBooking.event_id == event_id)).all() == []
    assert db.get(VenueBlock, block_id) is None
