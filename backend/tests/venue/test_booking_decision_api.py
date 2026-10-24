"""US4 approve or reject a venue booking request (SCRUM-8): Venue Staff's decision on a US22
request, its refusals and the coordinator's notice. See docs/testing/US4-booking-decision.md."""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBooking, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_block, make_venue_booking

pytestmark = pytest.mark.anyio

PENDING_URL = "/api/v1/venue-bookings/pending"
START = NOW + timedelta(days=7)
END = START + timedelta(hours=2)
NOT_PENDING = [VenueBookingStatus.APPROVED, VenueBookingStatus.REJECTED, VenueBookingStatus.WITHDRAWN]


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def approve_url(booking_id: uuid.UUID) -> str:
    return f"/api/v1/venue-bookings/{booking_id}/approve"


def reject_url(booking_id: uuid.UUID) -> str:
    return f"/api/v1/venue-bookings/{booking_id}/reject"


def stored(db: Session, booking: VenueBooking) -> VenueBooking:
    db.expire_all()
    return db.get(VenueBooking, booking.id)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def staff(db: Session) -> User:
    # DECISION-PENDING: D19 — operations_manager stands in for Venue Staff until US16b.
    return make_user(db, UserRole.OPERATIONS_MANAGER)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    # DECISION-PENDING: D24 — nothing approves a request until US17, so tests create it approved.
    return make_event(db, name="Data Science Summit", status=EventStatus.APPROVED, coordinator_id=coordinator.id)


@pytest.fixture
def venue(db: Session) -> Venue:
    # Capacity 40, setup 30 minutes, turnaround 15 (make_venue's defaults).
    return make_venue(db, name="Hall A")


@pytest.fixture
def booking(db: Session, event: Event, venue: Venue, coordinator: User) -> VenueBooking:
    return make_venue_booking(
        db,
        event=event,
        venue=venue,
        user=coordinator,
        starts_at=START,
        ends_at=END,
        required_facilities=["projector"],
        special_requirements="Lectern at the front.",
    )


# --- TC-US4-01 the request shows its timing and requirements ---


async def test_tc_us4_01_pending_list_shows_timing_and_requirements(
    client: AsyncClient, staff: User, booking: VenueBooking
) -> None:
    response = await client.get(PENDING_URL, headers=auth(staff))

    [row] = response.json()["bookings"]
    assert row["id"] == str(booking.id)
    assert row["event"]["name"] == "Data Science Summit"
    assert row["venue"]["name"] == "Hall A"
    assert (datetime.fromisoformat(row["starts_at"]), datetime.fromisoformat(row["ends_at"])) == (START, END)
    assert row["expected_attendees"] == 30
    assert row["room_layout"] == "theatre"
    assert row["required_facilities"] == ["projector"]
    assert row["special_requirements"] == "Lectern at the front."
    # Nothing decided yet.
    assert (row["decided_at"], row["decided_by_user_id"], row["rejection_reason"], row["alternative_suggestion"]) == (
        None,
        None,
        None,
        None,
    )


# --- TC-US4-02 approve ---


async def test_tc_us4_02_approving_reserves_the_venue(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, booking: VenueBooking
) -> None:
    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["decided_by_user_id"] == str(staff.id)
    assert body["rejection_reason"] is None
    saved = stored(db, booking)
    assert saved.status == VenueBookingStatus.APPROVED
    assert saved.decided_at == NOW
    assert saved.decided_by_user_id == staff.id
    # Reserved: no other request can take the window, and it leaves the pending list.
    pending = await client.get(PENDING_URL, headers=auth(staff))
    assert pending.json()["bookings"] == []
    clash = await client.post(
        "/api/v1/venue-bookings",
        headers=auth(coordinator),
        json={
            "event_id": str(event.id),
            "venue_id": str(venue.id),
            "starts_at": START.isoformat(),
            "ends_at": END.isoformat(),
            "expected_attendees": 30,
            "room_layout": "theatre",
        },
    )
    assert clash.status_code == 409
    assert clash.json()["code"] == "VENUE_UNAVAILABLE"


async def test_tc_us4_02_approving_without_a_body_or_with_an_empty_one(
    client: AsyncClient, db: Session, staff: User, event: Event, venue: Venue, coordinator: User
) -> None:
    first = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START)
    second = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START + timedelta(days=1))

    assert (await client.post(approve_url(first.id), headers=auth(staff))).status_code == 200
    assert (await client.post(approve_url(second.id), headers=auth(staff), json={})).status_code == 200


async def test_tc_us4_02_approving_leaves_the_event_status(
    client: AsyncClient, db: Session, staff: User, event: Event, booking: VenueBooking
) -> None:
    await client.post(approve_url(booking.id), headers=auth(staff))

    db.expire_all()
    assert db.get(Event, event.id).status == EventStatus.APPROVED


# --- TC-US4-03 no approval over a conflict, no override ---


@pytest.mark.parametrize(
    ("other_starts", "other_ends"),
    [
        # Ends 10 minutes before this starts: inside its turnaround (15) and this one's setup (30).
        (START - timedelta(hours=2, minutes=10), START - timedelta(minutes=10)),
        # Starts 30 minutes after this ends: inside this one's turnaround (15) plus its setup (30).
        (END + timedelta(minutes=30), END + timedelta(hours=2)),
    ],
    ids=["before", "after"],
)
@pytest.mark.parametrize("other_status", [VenueBookingStatus.APPROVED, VenueBookingStatus.REQUESTED])
async def test_tc_us4_03_a_clash_with_another_booking_is_refused(
    client: AsyncClient,
    db: Session,
    staff: User,
    coordinator: User,
    venue: Venue,
    booking: VenueBooking,
    notifier: FakeNotifier,
    other_starts: datetime,
    other_ends: datetime,
    other_status: VenueBookingStatus,
) -> None:
    """The plain windows don't overlap (that is refused already at request time, US22), but the
    venue's setup and turnaround do: approving would leave no time to turn the venue round."""
    other = make_venue_booking(
        db,
        event=make_event(db, status=EventStatus.APPROVED),
        venue=venue,
        user=coordinator,
        starts_at=other_starts,
        ends_at=other_ends,
        status=other_status,
    )

    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "VENUE_UNAVAILABLE"
    assert datetime.fromisoformat(body["conflict"]["starts_at"]) == other.starts_at
    assert "already booked" in body["message"]
    # The request stays pending, to be rejected or withdrawn; nobody is told anything.
    saved = stored(db, booking)
    assert (saved.status, saved.decided_at) == (VenueBookingStatus.REQUESTED, None)
    assert notifier.booking_decisions == []


async def test_tc_us4_03_back_to_back_with_buffers_clear_is_approved(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue, booking: VenueBooking
) -> None:
    # The other ends 45 minutes before this starts: exactly its turnaround (15) plus this setup (30).
    make_venue_booking(
        db,
        event=make_event(db, status=EventStatus.APPROVED),
        venue=venue,
        user=coordinator,
        starts_at=START - timedelta(hours=2, minutes=45),
        ends_at=START - timedelta(minutes=45),
        status=VenueBookingStatus.APPROVED,
    )
    # And one that starts exactly 45 minutes after this ends.
    make_venue_booking(
        db,
        event=make_event(db, status=EventStatus.APPROVED),
        venue=venue,
        user=coordinator,
        starts_at=END + timedelta(minutes=45),
    )

    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 200


async def test_tc_us4_03_zero_buffers_allow_touching_windows(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event
) -> None:
    venue = make_venue(db, setup_minutes=0, turnaround_minutes=0)
    make_venue_booking(
        db,
        event=event,
        venue=venue,
        user=coordinator,
        starts_at=START - timedelta(hours=2),
        ends_at=START,
        status=VenueBookingStatus.APPROVED,
    )
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START, ends_at=END)

    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("block_starts", "block_ends"),
    [
        (START + timedelta(minutes=30), START + timedelta(hours=1)),  # inside the window
        (START - timedelta(hours=1), START - timedelta(minutes=10)),  # inside the 30-minute setup
        (END + timedelta(minutes=10), END + timedelta(hours=1)),  # inside the 15-minute turnaround
    ],
    ids=["window", "setup", "turnaround"],
)
async def test_tc_us4_03_a_venue_block_is_refused(
    client: AsyncClient,
    db: Session,
    staff: User,
    venue: Venue,
    booking: VenueBooking,
    block_starts: datetime,
    block_ends: datetime,
) -> None:
    make_venue_block(db, venue, block_starts, block_ends, note="AV maintenance")

    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_UNAVAILABLE"
    assert "unavailable" in response.json()["message"]
    assert stored(db, booking).status == VenueBookingStatus.REQUESTED


async def test_tc_us4_03_a_block_clear_of_the_buffers_is_fine(
    client: AsyncClient, db: Session, staff: User, venue: Venue, booking: VenueBooking
) -> None:
    make_venue_block(db, venue, START - timedelta(hours=1), START - timedelta(minutes=30))
    make_venue_block(db, venue, END + timedelta(minutes=15), END + timedelta(hours=1))
    make_venue_block(db, make_venue(db), START, END)

    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 200


async def test_tc_us4_03_an_inactive_venue_cannot_be_reserved(
    client: AsyncClient, db: Session, staff: User, venue: Venue, booking: VenueBooking
) -> None:
    venue.is_active = False
    db.flush()

    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_UNAVAILABLE"
    assert stored(db, booking).status == VenueBookingStatus.REQUESTED


@pytest.mark.parametrize("field", ["override", "room_layout", "starts_at"])
async def test_tc_us4_03_and_07_approve_takes_no_fields(
    client: AsyncClient, db: Session, staff: User, booking: VenueBooking, field: str
) -> None:
    """No override flag (AC 3) and no partial approval of a changed layout or time (AC 7)."""
    response = await client.post(approve_url(booking.id), headers=auth(staff), json={field: True})

    assert response.status_code == 422
    assert stored(db, booking).status == VenueBookingStatus.REQUESTED


# --- TC-US4-04 and 05 reject ---


async def test_tc_us4_04_rejecting_without_notes(
    client: AsyncClient, db: Session, staff: User, booking: VenueBooking
) -> None:
    response = await client.post(reject_url(booking.id), headers=auth(staff))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["decided_by_user_id"] == str(staff.id)
    assert (body["rejection_reason"], body["alternative_suggestion"]) == (None, None)
    assert stored(db, booking).decided_at == NOW


async def test_tc_us4_04_a_rejected_window_is_free_again(
    client: AsyncClient, db: Session, staff: User, coordinator: User, event: Event, venue: Venue, booking: VenueBooking
) -> None:
    await client.post(reject_url(booking.id), headers=auth(staff))

    again = await client.post(
        "/api/v1/venue-bookings",
        headers=auth(coordinator),
        json={
            "event_id": str(event.id),
            "venue_id": str(venue.id),
            "starts_at": START.isoformat(),
            "ends_at": END.isoformat(),
            "expected_attendees": 30,
            "room_layout": "theatre",
        },
    )
    assert again.status_code == 201


async def test_tc_us4_04_a_conflicted_request_can_still_be_rejected(
    client: AsyncClient, db: Session, staff: User, venue: Venue, booking: VenueBooking
) -> None:
    make_venue_block(db, venue, START, END)

    assert (await client.post(approve_url(booking.id), headers=auth(staff))).status_code == 409
    response = await client.post(reject_url(booking.id), headers=auth(staff), json={"reason": "Closed that day."})

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_tc_us4_05_rejecting_with_a_reason_and_an_alternative(
    client: AsyncClient, db: Session, staff: User, booking: VenueBooking
) -> None:
    response = await client.post(
        reject_url(booking.id),
        headers=auth(staff),
        json={"reason": "  Hall A is being repainted.  ", "alternative_suggestion": " Hall B is free then. "},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rejection_reason"] == "Hall A is being repainted."
    assert body["alternative_suggestion"] == "Hall B is free then."
    saved = stored(db, booking)
    assert (saved.rejection_reason, saved.alternative_suggestion) == ("Hall A is being repainted.", "Hall B is free then.")


@pytest.mark.parametrize(
    "body",
    [{"reason": "No AV that week."}, {"alternative_suggestion": "Try the morning."}, {"reason": "   ", "alternative_suggestion": ""}],
    ids=["reason-only", "alternative-only", "blank"],
)
async def test_tc_us4_05_either_note_is_optional(
    client: AsyncClient, db: Session, staff: User, booking: VenueBooking, body: dict[str, str]
) -> None:
    response = await client.post(reject_url(booking.id), headers=auth(staff), json=body)

    assert response.status_code == 200
    saved = response.json()
    assert saved["rejection_reason"] == ((body.get("reason") or "").strip() or None)
    assert saved["alternative_suggestion"] == ((body.get("alternative_suggestion") or "").strip() or None)


async def test_tc_us4_05_reject_takes_no_other_fields(
    client: AsyncClient, db: Session, staff: User, booking: VenueBooking
) -> None:
    response = await client.post(reject_url(booking.id), headers=auth(staff), json={"room_layout": "classroom"})

    assert response.status_code == 422
    assert stored(db, booking).status == VenueBookingStatus.REQUESTED


def test_tc_us4_05_notes_only_go_with_a_rejection(db: Session, booking: VenueBooking) -> None:
    """venue_bookings_rejection_notes_only_when_rejected: the database refuses a reason on any other
    status, and venue_bookings_decided_consistent a decision time on a pending booking."""
    for change, constraint in (
        ({"rejection_reason": "No."}, "venue_bookings_rejection_notes_only_when_rejected"),
        ({"alternative_suggestion": "Hall B."}, "venue_bookings_rejection_notes_only_when_rejected"),
        ({"decided_at": NOW}, "venue_bookings_decided_consistent"),
        ({"status": VenueBookingStatus.APPROVED}, "venue_bookings_decided_consistent"),
    ):
        with pytest.raises(IntegrityError) as refused:
            with db.begin_nested():
                db.execute(VenueBooking.__table__.update().where(VenueBooking.id == booking.id).values(**change))
        assert refused.value.orig.diag.constraint_name == constraint


def test_tc_us4_05_schema_has_the_decision_columns(db: Session) -> None:
    columns = {column["name"]: column for column in inspect(db.get_bind()).get_columns("venue_bookings")}
    for name in ("decided_at", "decided_by_user_id", "rejection_reason", "alternative_suggestion"):
        assert columns[name]["nullable"] is True


# --- TC-US4-06 the coordinator is told ---


async def test_tc_us4_06_approval_notifies_the_coordinator(
    client: AsyncClient, notifier: FakeNotifier, staff: User, coordinator: User, booking: VenueBooking
) -> None:
    await client.post(approve_url(booking.id), headers=auth(staff))

    assert notifier.booking_decisions == [
        {
            "email": coordinator.email,
            "booking_id": booking.id,
            "decision": "approved",
            "event_name": "Data Science Summit",
            "venue_name": "Hall A",
            "starts_at": START,
            "ends_at": END,
            "reason": None,
            "alternative_suggestion": None,
        }
    ]


async def test_tc_us4_06_rejection_notifies_with_the_notes(
    client: AsyncClient, notifier: FakeNotifier, staff: User, coordinator: User, booking: VenueBooking
) -> None:
    await client.post(
        reject_url(booking.id), headers=auth(staff), json={"reason": "Repainting.", "alternative_suggestion": "Hall B."}
    )

    [call] = notifier.booking_decisions
    assert call["email"] == coordinator.email
    assert call["decision"] == "rejected"
    assert (call["reason"], call["alternative_suggestion"]) == ("Repainting.", "Hall B.")


async def test_tc_us4_06_a_reassigned_event_tells_both_coordinators_once(
    client: AsyncClient, db: Session, notifier: FakeNotifier, staff: User, coordinator: User, event: Event, booking: VenueBooking
) -> None:
    now_assigned = make_user(db, UserRole.COORDINATOR)
    event.coordinator_id = now_assigned.id
    db.flush()

    await client.post(approve_url(booking.id), headers=auth(staff))

    assert sorted(call["email"] for call in notifier.booking_decisions) == sorted([coordinator.email, now_assigned.email])


async def test_tc_us4_06_a_notice_failure_keeps_the_decision(
    client: AsyncClient, db: Session, notifier: FakeNotifier, staff: User, booking: VenueBooking
) -> None:
    notifier.fail = True

    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 200
    assert stored(db, booking).status == VenueBookingStatus.APPROVED


# --- TC-US4-07 a request is decided once, as a whole ---


@pytest.mark.parametrize("status", NOT_PENDING, ids=[status.value for status in NOT_PENDING])
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_tc_us4_07_only_a_pending_request_can_be_decided(
    client: AsyncClient,
    db: Session,
    notifier: FakeNotifier,
    staff: User,
    event: Event,
    venue: Venue,
    coordinator: User,
    status: VenueBookingStatus,
    action: str,
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, status=status)
    url = approve_url(booking.id) if action == "approve" else reject_url(booking.id)

    response = await client.post(url, headers=auth(staff))

    assert response.status_code == 409
    assert response.json() == {"code": "BOOKING_NOT_PENDING", "status": status.value}
    assert stored(db, booking).status == status
    assert notifier.booking_decisions == []


async def test_tc_us4_07_a_decided_request_cannot_be_withdrawn(
    client: AsyncClient, db: Session, staff: User, coordinator: User, booking: VenueBooking
) -> None:
    await client.post(reject_url(booking.id), headers=auth(staff))

    response = await client.post(f"/api/v1/venue-bookings/{booking.id}/withdraw", headers=auth(coordinator))

    assert response.status_code == 409
    assert response.json() == {"code": "BOOKING_NOT_PENDING", "status": "rejected"}


# --- TC-US4-08 a rejection leaves the event in Planning ---


@pytest.mark.parametrize("status", [EventStatus.APPROVED, EventStatus.PLANNING])
async def test_tc_us4_08_rejecting_keeps_the_event_bookable(
    client: AsyncClient, db: Session, staff: User, coordinator: User, venue: Venue, status: EventStatus
) -> None:
    event = make_event(db, status=status, coordinator_id=coordinator.id)
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=START)

    await client.post(reject_url(booking.id), headers=auth(staff))

    db.expire_all()
    assert db.get(Event, event.id).status == status
    other = make_venue(db, name="Hall B")
    again = await client.post(
        "/api/v1/venue-bookings",
        headers=auth(coordinator),
        json={
            "event_id": str(event.id),
            "venue_id": str(other.id),
            "starts_at": START.isoformat(),
            "ends_at": END.isoformat(),
            "expected_attendees": 30,
            "room_layout": "theatre",
        },
    )
    assert again.status_code == 201


@pytest.mark.parametrize("status", [EventStatus.CANCELLED, EventStatus.COMPLETED, EventStatus.CONFIRMED])
async def test_tc_us4_08_an_event_no_longer_bookable_cannot_be_approved(
    client: AsyncClient, db: Session, staff: User, event: Event, booking: VenueBooking, status: EventStatus
) -> None:
    event.status = status
    db.flush()

    response = await client.post(approve_url(booking.id), headers=auth(staff))

    assert response.status_code == 409
    assert response.json() == {"code": "EVENT_NOT_BOOKABLE", "status": status.value}
    assert stored(db, booking).status == VenueBookingStatus.REQUESTED
    # It can still be rejected, which frees the venue.
    assert (await client.post(reject_url(booking.id), headers=auth(staff))).status_code == 200


# --- TC-US4-09 who may decide ---


@pytest.mark.parametrize(
    "role", [UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD, UserRole.ORGANISER, UserRole.ATTENDEE]
)
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_tc_us4_09_only_venue_staff_may_decide(
    client: AsyncClient, db: Session, booking: VenueBooking, role: UserRole, action: str
) -> None:
    url = approve_url(booking.id) if action == "approve" else reject_url(booking.id)

    response = await client.post(url, headers=auth(make_user(db, role)))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert stored(db, booking).status == VenueBookingStatus.REQUESTED


async def test_tc_us4_09_the_requesting_coordinator_cannot_approve_their_own(
    client: AsyncClient, db: Session, coordinator: User, booking: VenueBooking
) -> None:
    response = await client.post(approve_url(booking.id), headers=auth(coordinator))

    assert response.status_code == 403


async def test_tc_us4_09_inactive_staff_and_no_identity_are_refused(
    client: AsyncClient, db: Session, booking: VenueBooking
) -> None:
    inactive = make_user(db, UserRole.OPERATIONS_MANAGER, active=False)

    assert (await client.post(approve_url(booking.id), headers=auth(inactive))).status_code == 403
    assert (await client.post(approve_url(booking.id))).status_code == 401
    assert stored(db, booking).status == VenueBookingStatus.REQUESTED


@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_tc_us4_09_an_unknown_booking_is_not_found(client: AsyncClient, staff: User, action: str) -> None:
    unknown = uuid.uuid4()
    url = approve_url(unknown) if action == "approve" else reject_url(unknown)

    response = await client.post(url, headers=auth(staff))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}
