"""US23a (SCRUM-90) PR 2: Venue staff mark a venue unavailable; the bookings and holds it overlaps need rearranging,
their coordinators and organisers are told, and the period refuses new requests and approvals and shows on the
calendar. The schema is PR 1's (test_unavailability_schema.py); see docs/testing/US23a-venue-unavailability.md."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.booking_service import venues_arranged
from app.venue.models import Venue, VenueBlock, VenueBooking, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_block, make_venue_booking

pytestmark = pytest.mark.anyio

# Venue buffers from make_venue: 30 minutes' setup, 15 minutes' turnaround.
START = NOW + timedelta(days=7)
END = START + timedelta(hours=2)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def blocks_url(venue: Venue) -> str:
    return f"/api/v1/venues/{venue.id}/blocks"


def block_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "starts_at": START.isoformat(),
        "ends_at": END.isoformat(),
        "reason": "maintenance",
        "note": "Air-conditioning repair",
    }
    body.update(overrides)
    return body


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


def booking(db: Session, event: Event, venue: Venue, user: User, **overrides: object) -> VenueBooking:
    fields: dict[str, object] = {"starts_at": START, "ends_at": END}
    if overrides.get("status") == VenueBookingStatus.APPROVED:
        fields["decided_at"] = NOW
    fields.update(overrides)
    return make_venue_booking(db, event=event, venue=venue, user=user, **fields)


def hold(db: Session, event: Event, venue: Venue, staff: User, **overrides: object) -> VenueBooking:
    fields: dict[str, object] = {
        "status": VenueBookingStatus.HELD,
        "is_primary": False,
        "hold_expires_at": NOW + timedelta(days=3),
        "held_by_user_id": staff.id,
    }
    fields.update(overrides)
    return booking(db, event, venue, staff, **fields)


async def mark(client: AsyncClient, staff: User, venue: Venue, **overrides: object):
    return await client.post(blocks_url(venue), headers=auth(staff), json=block_body(**overrides))


# --- AC 1: recording a period ---


async def test_tc_us23a_04_venue_staff_record_a_period_with_a_reason(
    client: AsyncClient, db: Session, staff: User, venue: Venue
) -> None:
    response = await mark(client, staff, venue, reason="equipment_failure", note="  Projector failed  ")

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["venue"]["name"], body["reason"], body["note"]) == ("Hall A", "equipment_failure", "Projector failed")
    assert datetime.fromisoformat(body["starts_at"]) == START and datetime.fromisoformat(body["ends_at"]) == END
    assert (body["created_by_user_id"], body["affected_bookings"]) == (str(staff.id), [])
    stored = db.get(VenueBlock, body["id"])
    assert (stored.reason, stored.created_by_user_id) == ("equipment_failure", staff.id)


@pytest.mark.parametrize("reason", ["maintenance", "equipment_failure", "renovation", "safety", "other"])
async def test_tc_us23a_04_each_reason_is_accepted(
    client: AsyncClient, staff: User, venue: Venue, reason: str
) -> None:
    response = await mark(client, staff, venue, reason=reason, note=None)

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("role", [UserRole.COORDINATOR, UserRole.ORGANISER, UserRole.ATTENDEE])
async def test_tc_us23a_04_only_venue_staff_record_a_period(
    client: AsyncClient, db: Session, venue: Venue, role: UserRole
) -> None:
    response = await mark(client, make_user(db, role), venue)

    assert response.status_code == 403


async def test_tc_us23a_04_an_unknown_venue_is_not_found(client: AsyncClient, staff: User) -> None:
    response = await client.post(
        "/api/v1/venues/00000000-0000-0000-0000-000000000000/blocks", headers=auth(staff), json=block_body()
    )

    assert (response.status_code, response.json()["code"]) == (404, "NOT_FOUND")


async def test_tc_us23a_05_every_missing_field_is_named(client: AsyncClient, staff: User, venue: Venue) -> None:
    response = await client.post(blocks_url(venue), headers=auth(staff), json={"reason": "  "})

    assert response.status_code == 422
    assert response.json()["code"] == "MISSING_REQUIRED_FIELD"
    assert response.json()["fields"] == ["starts_at", "ends_at", "reason"]


@pytest.mark.parametrize(
    ("overrides", "errors"),
    [
        ({"reason": "flooding"}, {"reason": "Unknown reason: flooding. Allowed: maintenance, equipment_failure, renovation, safety, other."}),
        ({"note": "x" * 501}, {"note": "Keep the note to 500 characters."}),
        (
            {"starts_at": "2026-10-08T10:00:00"},
            {"starts_at": "Give the time with a timezone offset, e.g. 2026-10-08T10:00:00+08:00."},
        ),
    ],
    ids=["unknown reason", "long note", "no offset"],
)
async def test_tc_us23a_05_invalid_fields_are_named(
    client: AsyncClient, staff: User, venue: Venue, overrides: dict[str, object], errors: dict[str, str]
) -> None:
    response = await mark(client, staff, venue, **overrides)

    assert response.status_code == 422
    assert (response.json()["code"], response.json()["errors"]) == ("INVALID_BLOCK", errors)


# --- AC 2: a period ends after it starts ---


@pytest.mark.parametrize(
    ("ends_at", "message"),
    [
        (START - timedelta(hours=1), "The end must be after the start."),
        (START, "The end must be after the start."),
    ],
    ids=["end before the start", "end at the start"],
)
async def test_tc_us23a_06_a_period_ending_before_it_starts_is_refused(
    client: AsyncClient, db: Session, staff: User, venue: Venue, ends_at: datetime, message: str
) -> None:
    response = await mark(client, staff, venue, ends_at=ends_at.isoformat())

    assert response.status_code == 422
    assert (response.json()["code"], response.json()["errors"]) == ("INVALID_BLOCK", {"ends_at": message})
    assert db.query(VenueBlock).filter_by(venue_id=venue.id).count() == 0


async def test_tc_us23a_06_a_period_already_over_is_refused(client: AsyncClient, staff: User, venue: Venue) -> None:
    response = await mark(
        client, staff, venue,
        starts_at=(NOW - timedelta(hours=3)).isoformat(), ends_at=(NOW - timedelta(hours=1)).isoformat(),
    )

    assert response.json()["errors"] == {"ends_at": "This period has already ended."}


async def test_tc_us23a_06_a_period_under_way_is_accepted(client: AsyncClient, staff: User, venue: Venue) -> None:
    """Equipment can fail mid-day: a period may start in the past as long as it hasn't ended."""
    response = await mark(
        client, staff, venue,
        starts_at=(NOW - timedelta(hours=1)).isoformat(), ends_at=(NOW + timedelta(hours=1)).isoformat(),
    )

    assert response.status_code == 201, response.text


# --- AC 3: overlapping bookings and holds need rearranging ---


async def test_tc_us23a_07_overlapping_bookings_and_holds_are_marked_and_kept(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    requested = booking(db, event, venue, coordinator, is_primary=False)
    approved = booking(
        db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, decided_by_user_id=staff.id,
        starts_at=START + timedelta(days=1), ends_at=END + timedelta(days=1),
    )
    held = hold(db, event, venue, staff, starts_at=START + timedelta(days=2), ends_at=END + timedelta(days=2))

    response = await mark(client, staff, venue, ends_at=(END + timedelta(days=2)).isoformat())

    assert response.status_code == 201, response.text
    block_id = response.json()["id"]
    assert [b["reference"] for b in response.json()["affected_bookings"]] == [
        requested.reference, approved.reference, held.reference,
    ]
    for row, status in ((requested, "requested"), (approved, "approved"), (held, "held")):
        db.refresh(row)
        assert (row.status.value, str(row.rearrangement_block_id), row.rearrangement_flagged_at) == (status, block_id, NOW)
    db.refresh(event)
    assert event.status == EventStatus.PLANNING  # not cancelled (AC 3)


@pytest.mark.parametrize(
    ("starts_at", "ends_at", "marked"),
    [
        # The booking occupies START - 30 min to END + 15 min.
        (END + timedelta(minutes=5), END + timedelta(hours=1), True),  # only its turnaround
        (START - timedelta(hours=1), START - timedelta(minutes=20), True),  # only its setup
        (END + timedelta(minutes=15), END + timedelta(hours=1), False),  # touching its turnaround's end
        (START - timedelta(hours=1), START - timedelta(minutes=30), False),  # touching its setup's start
    ],
    ids=["turnaround", "setup", "touching after", "touching before"],
)
async def test_tc_us23a_07_overlap_is_by_the_occupied_window_and_touching_is_not_overlapping(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    starts_at: datetime, ends_at: datetime, marked: bool,
) -> None:
    row = booking(db, event, venue, coordinator)

    response = await mark(client, staff, venue, starts_at=starts_at.isoformat(), ends_at=ends_at.isoformat())

    db.refresh(row)
    assert (row.rearrangement_block_id is not None) == marked
    assert len(response.json()["affected_bookings"]) == int(marked)


async def test_tc_us23a_07_other_venues_and_closed_bookings_are_untouched(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    elsewhere = booking(db, event, make_venue(db, name="Hall B"), coordinator)
    withdrawn = booking(db, event, venue, coordinator, status=VenueBookingStatus.WITHDRAWN, withdrawn_at=NOW, is_primary=False)
    rejected = booking(
        db, event, venue, coordinator, status=VenueBookingStatus.REJECTED, decided_at=NOW, decided_by_user_id=staff.id,
        is_primary=False,
    )

    response = await mark(client, staff, venue)

    assert response.json()["affected_bookings"] == []
    for row in (elsewhere, withdrawn, rejected):
        db.refresh(row)
        assert row.rearrangement_block_id is None


async def test_tc_us23a_08_the_booking_reads_needs_rearrangement_and_isnt_arranged(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    approved = booking(
        db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, decided_by_user_id=staff.id, is_primary=True
    )
    assert venues_arranged(db, event, NOW)

    await mark(client, staff, venue, reason="safety", note="Ceiling inspection")

    response = await client.get(f"/api/v1/events/{event.id}/venue-bookings", headers=auth(coordinator))
    [read] = [b for b in response.json()["bookings"] if b["id"] == str(approved.id)]
    assert (read["status"], read["next_action"]) == ("approved", "coordinator_to_rebook")
    unavailability = read["unavailability"]
    assert unavailability["kind"] == "venue_unavailable"
    assert (unavailability["block"]["reason"], unavailability["block"]["note"]) == ("safety", "Ceiling inspection")
    assert datetime.fromisoformat(unavailability["flagged_at"]) == NOW
    assert response.json()["venues_arranged"] is False
    db.expire_all()
    assert not venues_arranged(db, event, NOW)


async def test_tc_us23a_08_the_organiser_reads_it_too(
    client: AsyncClient, db: Session, staff: User, coordinator: User, organiser: User, event: Event, venue: Venue
) -> None:
    booking(db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, decided_by_user_id=staff.id)
    await mark(client, staff, venue)

    response = await client.get(f"/api/v1/events/{event.id}/venue-bookings", headers=auth(organiser))

    assert response.status_code == 200, response.text
    assert response.json()["bookings"][0]["unavailability"]["kind"] == "venue_unavailable"


@pytest.mark.parametrize(
    ("status", "fields", "kind", "next_action"),
    [
        (VenueBookingStatus.WITHDRAWN, {}, None, "none"),
        (VenueBookingStatus.REJECTED, {"rejection_reason": "Double-booked"}, "rejected", "coordinator_to_rebook"),
        (VenueBookingStatus.EXPIRED, {"is_primary": False, "expired_at": NOW}, None, "none"),
    ],
    ids=["withdrawn", "rejected", "expired"],
)
async def test_tc_us23a_08_a_marker_on_a_closed_booking_isnt_needs_rearrangement(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    status: VenueBookingStatus, fields: dict[str, object], kind: str | None, next_action: str,
) -> None:
    """Matt's #131 review: a booking that left the live set keeps its marker as history (a cancelled event withdraws
    its bookings, #117), but nothing reads it as needing rearrangement."""
    block = make_venue_block(db, venue, START - timedelta(hours=1), END, created_by_user_id=staff.id)
    extra: dict[str, object] = {"decided_at": NOW, "decided_by_user_id": staff.id} if status == VenueBookingStatus.REJECTED else {}
    if status == VenueBookingStatus.EXPIRED:
        extra = {"hold_expires_at": NOW - timedelta(hours=1), "held_by_user_id": staff.id}
    booking(
        db, event, venue, staff if status == VenueBookingStatus.EXPIRED else coordinator, status=status,
        rearrangement_block_id=block.id, rearrangement_flagged_at=NOW, **extra, **fields,
    )

    response = await client.get(f"/api/v1/events/{event.id}/venue-bookings", headers=auth(coordinator))

    [read] = response.json()["bookings"]
    assert (read["unavailability"] or {}).get("kind") == kind
    assert read["next_action"] == next_action


async def test_tc_us23a_08_a_marked_venue_is_outstanding_on_the_readiness_list(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    """Matt's #131 review: an approved booking that needs rearrangement isn't arranged for US18, so the readiness list
    names it and the event can't be confirmed."""
    approved = booking(
        db, event, venue, coordinator, status=VenueBookingStatus.APPROVED, decided_by_user_id=staff.id, is_primary=True
    )
    officer = make_user(db, UserRole.SAFETY_OFFICER)
    event.safety_approved_at = NOW
    event.safety_approved_by_user_id = officer.id
    db.flush()
    ready = await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(coordinator))
    assert ready.status_code == 200, ready.text
    assert ready.json()["ready"] is True

    await mark(client, staff, venue)

    readiness = (await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(coordinator))).json()
    [venue_item] = [item for item in readiness["items"] if item["kind"] == "venue"]
    assert readiness["ready"] is False
    assert venue_item == {
        "kind": "venue",
        "name": "Hall A, Main venue",
        "complete": False,
        "detail": f"Booking {approved.reference} needs rearrangement: the venue has become unavailable.",
    }
    refused = await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(coordinator))
    assert refused.status_code == 409
    assert refused.json()["code"] == "EVENT_NOT_READY"
    db.refresh(event)
    assert event.status == EventStatus.PLANNING and event.confirmed_at is None


async def test_tc_us23a_09_a_booking_keeps_the_first_period_that_marked_it(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, notifier: FakeNotifier
) -> None:
    row = booking(db, event, venue, coordinator)
    first = (await mark(client, staff, venue)).json()

    second = (await mark(client, staff, venue, reason="renovation")).json()

    db.refresh(row)
    assert str(row.rearrangement_block_id) == first["id"]
    assert second["affected_bookings"] == []
    # Matt's #133 review: the second period did reach it, so Venue staff see that, though nobody is told again.
    assert [b["reference"] for b in second["already_affected_bookings"]] == [row.reference]
    assert first["already_affected_bookings"] == []
    assert len(notifier.unavailable) == 2  # the first period's coordinator and organiser notices only


async def test_tc_us23a_07_a_booking_already_over_isnt_marked(
    client: AsyncClient, db: Session, staff: User, coordinator: User, organiser: User, venue: Venue,
    notifier: FakeNotifier,
) -> None:
    """Matt's #133 review: a period that began in the past doesn't reach back to an event that already took place.
    One still under way is marked."""
    past = make_event(
        db, name="Yesterday's Talk", status=EventStatus.APPROVED, coordinator_id=coordinator.id,
        start_at=NOW - timedelta(days=1), end_at=NOW - timedelta(days=1) + timedelta(hours=2),
    )
    over = booking(
        db, past, venue, coordinator, status=VenueBookingStatus.APPROVED, decided_by_user_id=staff.id,
        starts_at=NOW - timedelta(days=1), ends_at=NOW - timedelta(days=1) + timedelta(hours=2),
    )
    current = make_event(
        db, name="Under Way", status=EventStatus.APPROVED, coordinator_id=coordinator.id,
        start_at=NOW - timedelta(hours=1), end_at=NOW + timedelta(hours=1),
    )
    # Its turnaround runs past now, so it isn't over yet.
    under_way = booking(
        db, current, venue, coordinator, status=VenueBookingStatus.APPROVED, decided_by_user_id=staff.id,
        starts_at=NOW - timedelta(hours=1), ends_at=NOW + timedelta(hours=1),
    )

    response = await mark(
        client, staff, venue, starts_at=(NOW - timedelta(days=2)).isoformat(), ends_at=(NOW + timedelta(days=1)).isoformat()
    )

    assert response.status_code == 201, response.text
    db.refresh(over)
    db.refresh(under_way)
    assert over.rearrangement_block_id is None
    assert str(under_way.rearrangement_block_id) == response.json()["id"]
    assert [b["reference"] for b in response.json()["affected_bookings"]] == [under_way.reference]
    assert {call["event_name"] for call in notifier.unavailable} == {"Under Way"}


async def test_tc_us23a_09_a_lapsed_hold_expires_instead_of_being_marked(
    client: AsyncClient, db: Session, staff: User, event: Event, venue: Venue
) -> None:
    lapsed = hold(db, event, venue, staff, hold_expires_at=NOW - timedelta(minutes=1))

    response = await mark(client, staff, venue)

    db.refresh(lapsed)
    assert (lapsed.status, lapsed.rearrangement_block_id) == (VenueBookingStatus.EXPIRED, None)
    assert response.json()["affected_bookings"] == []


# --- AC 4: the coordinator and organiser are told; attendees aren't ---


async def test_tc_us23a_10_the_coordinator_and_organiser_are_told_once_per_event(
    client: AsyncClient, db: Session, staff: User, coordinator: User, organiser: User, event: Event, venue: Venue,
    notifier: FakeNotifier,
) -> None:
    first = booking(db, event, venue, coordinator)
    second = booking(
        db, event, venue, coordinator, is_primary=False,
        starts_at=START + timedelta(hours=3), ends_at=END + timedelta(hours=3),
    )

    await mark(client, staff, venue, ends_at=(END + timedelta(hours=3)).isoformat(), reason="renovation")

    assert sorted((call["recipient"], call["email"]) for call in notifier.unavailable) == [
        ("coordinator", coordinator.email), ("organiser", organiser.email),
    ]
    for call in notifier.unavailable:
        assert (call["venue_name"], call["reason"], call["event_name"]) == ("Hall A", "renovation", "Data Science Summit")
        assert (call["starts_at"], call["ends_at"]) == (START, END + timedelta(hours=3))
        assert call["booking_references"] == [first.reference, second.reference]
        assert call["next_action"]
    # AC 4: nobody else hears of it at this stage.
    others = {name: calls for name, calls in vars(notifier).items() if isinstance(calls, list) and name != "unavailable"}
    assert all(calls == [] for calls in others.values()), others


async def test_tc_us23a_10_an_organiser_without_a_coordinator_isnt_promised_one(
    client: AsyncClient, db: Session, staff: User, coordinator: User, organiser: User, event: Event, venue: Venue,
    notifier: FakeNotifier,
) -> None:
    """Matt's #133 review: with the coordinator inactive, the organiser hears a Lead assigns one first."""
    booking(db, event, venue, coordinator)
    coordinator.is_active = False
    db.flush()

    await mark(client, staff, venue)

    [call] = notifier.unavailable
    assert (call["recipient"], call["email"]) == ("organiser", organiser.email)
    assert call["next_action"] == (
        "Your event has no active coordinator yet. A Coordinator Lead assigns one, who then arranges a replacement venue."
    )


async def test_tc_us23a_10_each_affected_event_is_told_and_unaffected_ones_arent(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    notifier: FakeNotifier,
) -> None:
    other_coordinator = make_user(db, UserRole.COORDINATOR)
    other = make_event(db, name="Alumni Night", status=EventStatus.APPROVED, coordinator_id=other_coordinator.id)
    booking(db, event, venue, coordinator)
    booking(db, other, venue, other_coordinator, starts_at=START + timedelta(days=1), ends_at=END + timedelta(days=1))
    untouched = make_event(db, name="Later Talk", status=EventStatus.APPROVED, coordinator_id=coordinator.id)
    booking(db, untouched, venue, coordinator, starts_at=START + timedelta(days=5), ends_at=END + timedelta(days=5))

    await mark(client, staff, venue, ends_at=(END + timedelta(days=1)).isoformat())

    told = sorted((call["event_name"], call["recipient"]) for call in notifier.unavailable)
    # Alumni Night has no organiser on record, so only its coordinator hears.
    assert told == [
        ("Alumni Night", "coordinator"), ("Data Science Summit", "coordinator"), ("Data Science Summit", "organiser"),
    ]


async def test_tc_us23a_10_a_failed_notice_leaves_the_period_recorded(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue,
    notifier: FakeNotifier,
) -> None:
    row = booking(db, event, venue, coordinator)
    notifier.fail = True

    response = await mark(client, staff, venue)

    assert response.status_code == 201, response.text
    db.refresh(row)
    assert row.rearrangement_block_id is not None


# --- AC 5: new requests and approvals in the period are refused ---


async def test_tc_us23a_11_a_new_request_in_the_period_is_refused(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    await mark(client, staff, venue)

    response = await client.post(
        "/api/v1/venue-bookings",
        headers=auth(coordinator),
        json={
            "event_id": str(event.id), "venue_id": str(venue.id), "starts_at": START.isoformat(),
            "ends_at": END.isoformat(), "expected_attendees": 30, "room_layout": "theatre", "purpose": "Main venue",
        },
    )

    assert (response.status_code, response.json()["code"]) == (409, "VENUE_UNAVAILABLE")


async def test_tc_us23a_11_approving_a_marked_request_is_refused(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    requested = booking(db, event, venue, coordinator)
    await mark(client, staff, venue)

    response = await client.post(f"/api/v1/venue-bookings/{requested.id}/approve", headers=auth(staff), json={})

    assert (response.status_code, response.json()["code"]) == (409, "VENUE_UNAVAILABLE")
    db.refresh(requested)
    assert requested.status == VenueBookingStatus.REQUESTED


async def test_tc_us23a_11_confirming_a_marked_hold_is_refused(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    held = hold(db, event, venue, staff)
    await mark(client, staff, venue)

    response = await client.post(f"/api/v1/venue-bookings/{held.id}/confirm", headers=auth(coordinator))

    assert (response.status_code, response.json()["code"]) == (409, "VENUE_UNAVAILABLE")
    db.refresh(held)
    assert held.status == VenueBookingStatus.HELD


async def test_tc_us23a_11_the_coordinator_can_still_withdraw_a_marked_booking(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue
) -> None:
    requested = booking(db, event, venue, coordinator)
    await mark(client, staff, venue)

    response = await client.post(f"/api/v1/venue-bookings/{requested.id}/withdraw", headers=auth(coordinator))

    assert response.status_code == 200, response.text
    assert (response.json()["status"], response.json()["unavailability"]) == ("withdrawn", None)


# --- AC 6: the calendar shows the period ---


async def test_tc_us23a_12_the_calendar_shows_the_period_with_its_reason(
    client: AsyncClient, db: Session, staff: User, venue: Venue
) -> None:
    await mark(client, staff, venue, reason="renovation", note="Repainting")
    day = START.date().isoformat()

    response = await client.get(f"/api/v1/venues/{venue.id}/calendar?from={day}&to={day}", headers=auth(staff))

    assert response.status_code == 200, response.text
    [item] = [item for item in response.json()["items"] if item["kind"] == "block"]
    assert (item["label"], item["reason"], item["note"]) == ("Unavailable", "renovation", "Repainting")


async def test_tc_us23a_12_a_seeded_style_block_without_a_recorder_still_shows(
    client: AsyncClient, db: Session, staff: User, venue: Venue
) -> None:
    make_venue_block(db, venue, START, END, note="Closed")
    day = START.date().isoformat()

    response = await client.get(f"/api/v1/venues/{venue.id}/calendar?from={day}&to={day}", headers=auth(staff))

    [item] = [item for item in response.json()["items"] if item["kind"] == "block"]
    assert item["reason"] == "maintenance"


# --- TC-US23A-20's reset: the E2E's event starts clean on every reseed ---


def test_tc_us23a_20_the_seed_clears_the_unavailability_demo(db: Session, staff: User) -> None:
    from app.seed import UNAVAILABILITY_EVENT, seed, seed_id

    seed(db, now=NOW)
    event = db.get(Event, seed_id("event", UNAVAILABILITY_EVENT.slug))
    assert (event.name, event.status, event.coordinator_id) == (
        "Venue Unavailability Demo", EventStatus.APPROVED, seed_id("user", "event-coordinator"),
    )
    venue = make_venue(db, name="Hall Z")
    own = make_venue_block(db, venue, START, END, created_by_user_id=staff.id)
    shared = make_venue_block(db, venue, START + timedelta(days=1), END + timedelta(days=1), created_by_user_id=staff.id)
    booking(db, event, venue, staff, rearrangement_block_id=own.id, rearrangement_flagged_at=NOW)
    other = make_event(db, name="Someone Else's", status=EventStatus.APPROVED)
    kept = booking(
        db, other, venue, staff, starts_at=START + timedelta(days=1), ends_at=END + timedelta(days=1),
        rearrangement_block_id=shared.id, rearrangement_flagged_at=NOW,
    )
    booking(
        db, event, venue, staff, is_primary=False, starts_at=START + timedelta(days=2), ends_at=END + timedelta(days=2),
        rearrangement_block_id=shared.id, rearrangement_flagged_at=NOW,
    )
    own_id, shared_id = own.id, shared.id

    seed(db, now=NOW)

    db.expire_all()
    assert db.query(VenueBooking).filter(VenueBooking.event_id == event.id).count() == 0
    assert db.get(VenueBlock, own_id) is None  # marked only the demo's booking
    assert db.get(VenueBlock, shared_id) is not None  # still marks another event's booking
    assert db.get(VenueBooking, kept.id) is not None
