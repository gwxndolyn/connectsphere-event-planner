"""US9 (SCRUM-12) PR 2: request, decide and cancel an event, and what cancelling releases and tells.
See docs/testing/US9-cancel-event.md."""

import uuid
from datetime import date, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentReservation, TechStaffAssignment
from app.event.models import (
    CancellationStatus,
    ChangeRequestStatus,
    Event,
    EventCancellation,
    EventChangeRequest,
    EventStatus,
)
from app.registration.models import Registration, RegistrationStatus
from app.safety.models import SafetyReview
from app.registration.service import WAITLIST_OFFER_WINDOW
from app.user.models import Attendee, User, UserRole
from app.venue.models import VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.equipment.test_equipment_reservation_schema import make_approved_line, reserve
from tests.event.test_event_request_clarification_api import auth
from tests.safety.test_safety_review import approval
from tests.factories import NOW, make_attendee, make_event, make_registration, make_user, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

REASON = "The keynote speaker can't travel"


@pytest.fixture
def organiser(db: Session) -> User:
    user = make_user(db, UserRole.ORGANISER)
    user.full_name = "Olivia Ong"
    db.flush()
    return user


@pytest.fixture
def coordinator(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.full_name = "Casey Tan"
    db.flush()
    return user


def owned_event(
    db: Session, organiser: User, coordinator: User | None, status: EventStatus = EventStatus.PLANNING, **fields
) -> Event:
    event = make_event(
        db, name="Design Thinking Lab", status=status, coordinator_id=coordinator.id if coordinator else None, **fields
    )
    event.created_by_user_id = organiser.id
    event.request_reference = f"ER-{uuid.uuid4().hex[:6]}"
    db.flush()
    return event


@pytest.fixture
def event(db: Session, organiser: User, coordinator: User) -> Event:
    return owned_event(db, organiser, coordinator)


def attendee_auth(attendee: Attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


async def ask(client: AsyncClient, event: Event | uuid.UUID, user: User, reason: object = REASON):
    event_id = event.id if isinstance(event, Event) else event
    body = {} if reason is None else {"reason": reason}
    return await client.post(f"/api/v1/event-requests/{event_id}/cancellation-requests", headers=auth(user), json=body)


async def cancel(client: AsyncClient, event: Event, user: User, reason: object = REASON):
    body = {} if reason is None else {"reason": reason}
    return await client.post(f"/api/v1/event-requests/{event.id}/cancel", headers=auth(user), json=body)


async def decide(client: AsyncClient, cancellation_id: str, user: User, verb: str, reason: object = None):
    body = {} if reason is None else {"reason": reason}
    return await client.post(f"/api/v1/event-cancellations/{cancellation_id}/{verb}", headers=auth(user), json=body)


def rows(db: Session, event: Event) -> int:
    return db.scalar(select(func.count()).select_from(EventCancellation).where(EventCancellation.event_id == event.id))


# --- AC 1: the organiser asks ---


@pytest.mark.parametrize(
    "status", [EventStatus.APPROVED, EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.PREPARATION]
)
async def test_tc_us9_09_the_organiser_requests_cancellation(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier, status: EventStatus
) -> None:
    event = owned_event(db, organiser, coordinator, status)

    response = await ask(client, event, organiser, f"  {REASON}  ")

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["status"], body["reason"], body["event_status"], body["direct"]) == (
        "pending",
        REASON,
        status.value,
        False,
    )
    assert body["requested_by"] == {"id": str(organiser.id), "name": "Olivia Ong"}
    assert (body["decided_by"], body["decided_at"], body["rejection_reason"]) == (None, None, None)
    db.refresh(event)
    assert event.status == status  # nothing is released until the coordinator approves
    assert notifier.cancellation_requests == [
        {
            "email": coordinator.email,
            "event_id": event.id,
            "event_name": "Design Thinking Lab",
            "organiser_name": "Olivia Ong",
            "reason": REASON,
        }
    ]


@pytest.mark.parametrize(
    "status",
    [
        EventStatus.SUBMITTED,
        EventStatus.UNDER_REVIEW,
        EventStatus.AWAITING_CLARIFICATION,
        EventStatus.REJECTED,
        EventStatus.CANCELLED,
        EventStatus.COMPLETED,
    ],
)
async def test_tc_us9_10_not_before_approval_nor_once_over(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier, status: EventStatus
) -> None:
    event = owned_event(db, organiser, coordinator, status)

    response = await ask(client, event, organiser)

    assert (response.status_code, response.json()) == (
        409,
        {"code": "CANCELLATION_NOT_ALLOWED", "status": status.value},
    )
    assert rows(db, event) == 0
    assert notifier.cancellation_requests == []


async def test_tc_us9_11_a_draft_someone_elses_or_unknown_event_is_not_found(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    draft = owned_event(db, organiser, None, EventStatus.DRAFT)
    other = make_user(db, UserRole.ORGANISER)

    for target, user in ((draft, organiser), (event, other), (uuid.uuid4(), organiser)):
        response = await ask(client, target, user)
        assert (response.status_code, response.json()) == (404, {"code": "NOT_FOUND"})
    assert rows(db, event) == 0


@pytest.mark.parametrize(("reason", "code"), [(None, "MISSING_REQUIRED_FIELD"), ("   ", "MISSING_REQUIRED_FIELD"),
                                              ("x" * 1001, "INVALID_CANCELLATION")])
async def test_tc_us9_12_a_reason_is_required(
    client: AsyncClient, db: Session, organiser: User, event: Event, reason: str | None, code: str
) -> None:
    response = await ask(client, event, organiser, reason)

    assert response.status_code == 422
    assert (response.json()["code"], response.json()["fields"]) == (code, ["reason"])
    assert rows(db, event) == 0


async def test_tc_us9_12_unknown_fields_are_refused(client: AsyncClient, organiser: User, event: Event) -> None:
    response = await client.post(
        f"/api/v1/event-requests/{event.id}/cancellation-requests",
        headers=auth(organiser),
        json={"reason": REASON, "status": "approved"},
    )

    assert response.status_code == 422


async def test_tc_us9_13_one_request_at_a_time(client: AsyncClient, db: Session, organiser: User, event: Event) -> None:
    first = (await ask(client, event, organiser)).json()

    response = await ask(client, event, organiser, "Asking again")

    assert (response.status_code, response.json()) == (
        409,
        {"code": "CANCELLATION_PENDING", "cancellation_id": first["id"]},
    )
    assert rows(db, event) == 1


# --- AC 2: the coordinator decides ---


async def test_tc_us9_14_approving_cancels_the_event(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event, notifier: FakeNotifier
) -> None:
    requested = (await ask(client, event, organiser)).json()

    response = await decide(client, requested["id"], coordinator, "approve")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["event_status"], body["direct"]) == ("approved", "cancelled", False)
    assert body["requested_by"]["id"] == str(organiser.id)
    assert body["decided_by"] == {"id": str(coordinator.id), "name": "Casey Tan"}
    assert body["decided_at"] is not None
    db.refresh(event)
    assert event.status == EventStatus.CANCELLED
    assert {"email": organiser.email, "recipient": "organiser"}.items() <= notifier.cancellations[0].items()
    assert notifier.cancellations[0]["reason"] == REASON


async def test_tc_us9_15_rejecting_keeps_the_event_and_tells_the_organiser_why(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event, notifier: FakeNotifier
) -> None:
    requested = (await ask(client, event, organiser)).json()

    missing = await decide(client, requested["id"], coordinator, "reject")
    response = await decide(client, requested["id"], coordinator, "reject", " Registrations are strong ")

    assert (missing.status_code, missing.json()["code"]) == (422, "MISSING_REQUIRED_FIELD")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["rejection_reason"], body["event_status"]) == (
        "rejected",
        "Registrations are strong",
        "planning",
    )
    db.refresh(event)
    assert event.status == EventStatus.PLANNING
    assert notifier.cancellation_rejections == [
        {
            "email": organiser.email,
            "event_id": event.id,
            "event_name": "Design Thinking Lab",
            "reason": REASON,
            "rejection_reason": "Registrations are strong",
        }
    ]
    assert notifier.cancellations == []
    # A rejected request doesn't stop the organiser asking again.
    assert (await ask(client, event, organiser, "Asking again")).status_code == 201


async def test_tc_us9_16_a_request_is_decided_once_and_only_by_its_coordinator(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    requested = (await ask(client, event, organiser)).json()
    stranger = make_user(db, UserRole.COORDINATOR)

    by_stranger = await decide(client, requested["id"], stranger, "approve")
    unknown = await decide(client, str(uuid.uuid4()), coordinator, "approve")
    await decide(client, requested["id"], coordinator, "reject", "No")
    again = await decide(client, requested["id"], coordinator, "approve")

    assert (by_stranger.status_code, by_stranger.json()) == (404, {"code": "NOT_FOUND"})
    assert (unknown.status_code, unknown.json()) == (404, {"code": "NOT_FOUND"})
    assert (again.status_code, again.json()) == (409, {"code": "CANCELLATION_NOT_PENDING", "status": "rejected"})
    db.refresh(event)
    assert event.status == EventStatus.PLANNING


# --- AC 3, 4: the coordinator cancels; it can't be undone ---


async def test_tc_us9_17_the_coordinator_cancels_directly(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event, notifier: FakeNotifier
) -> None:
    response = await cancel(client, event, coordinator)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["direct"], body["event_status"], body["reason"]) == (
        "approved",
        True,
        "cancelled",
        REASON,
    )
    assert body["requested_by"] == body["decided_by"] == {"id": str(coordinator.id), "name": "Casey Tan"}
    assert body["requested_at"] == body["decided_at"]
    assert [call["email"] for call in notifier.cancellations] == [organiser.email]


async def test_tc_us9_17_a_direct_cancel_needs_a_reason_and_the_events_coordinator(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    missing = await cancel(client, event, coordinator, None)
    stranger = await cancel(client, event, make_user(db, UserRole.COORDINATOR))

    assert (missing.status_code, missing.json()["code"]) == (422, "MISSING_REQUIRED_FIELD")
    assert (stranger.status_code, stranger.json()) == (404, {"code": "NOT_FOUND"})
    db.refresh(event)
    assert event.status == EventStatus.PLANNING


async def test_tc_us9_17_a_waiting_request_is_decided_not_bypassed(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    requested = (await ask(client, event, organiser)).json()

    response = await cancel(client, event, coordinator)

    assert (response.status_code, response.json()) == (
        409,
        {"code": "CANCELLATION_PENDING", "cancellation_id": requested["id"]},
    )


async def test_tc_us9_21_a_cancelled_event_stays_cancelled(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    await cancel(client, event, coordinator)

    again = await cancel(client, event, coordinator, "Again")
    asked = await ask(client, event, organiser)

    for response in (again, asked):
        assert (response.status_code, response.json()) == (
            409,
            {"code": "CANCELLATION_NOT_ALLOWED", "status": "cancelled"},
        )
    assert rows(db, event) == 1


# --- AC 5: what cancelling releases ---


async def test_tc_us9_18_cancelling_releases_every_venue_and_the_equipment(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    staff = make_user(db, UserRole.VENUE_STAFF)
    approved = make_venue_booking(
        db, event=event, venue=make_venue(db), user=coordinator, status=VenueBookingStatus.APPROVED,
        decided_by_user_id=staff.id,
    )
    requested = make_venue_booking(db, event=event, venue=make_venue(db), user=coordinator, is_primary=False)
    rejected = make_venue_booking(
        db, event=event, venue=make_venue(db), user=coordinator, status=VenueBookingStatus.REJECTED,
        decided_by_user_id=staff.id, is_primary=False,
    )
    line = make_approved_line(db, event)
    reserve(db, line)
    other_line = make_approved_line(db)
    other_reservation = reserve(db, other_line)

    response = await cancel(client, event, coordinator)

    assert response.status_code == 200, response.text
    for booking in (approved, requested, rejected):
        db.refresh(booking)
    assert (approved.status, approved.withdrawn_at, approved.decided_at is not None) == (
        VenueBookingStatus.WITHDRAWN,
        NOW,
        True,
    )
    assert (requested.status, requested.withdrawn_at) == (VenueBookingStatus.WITHDRAWN, NOW)
    assert (rejected.status, rejected.withdrawn_at) == (VenueBookingStatus.REJECTED, None)
    remaining = db.scalars(select(EquipmentReservation.id)).all()
    assert remaining == [other_reservation.id]  # another event's reservation is untouched


async def test_tc_us9_18_tech_support_assignments_are_kept(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    tech = make_user(db, UserRole.TECH_SUPPORT)
    db.add(TechStaffAssignment(event_id=event.id, staff_user_id=tech.id, assigned_by_user_id=coordinator.id))
    db.flush()

    await cancel(client, event, coordinator)

    assignment = db.scalars(select(TechStaffAssignment).where(TechStaffAssignment.event_id == event.id)).one()
    assert assignment.unassigned_at is None


async def test_tc_us9_18_a_refused_cancel_releases_nothing(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    booking = make_venue_booking(db, event=event, venue=make_venue(db), user=coordinator)
    reserve(db, make_approved_line(db, event))

    response = await cancel(client, event, coordinator, "   ")

    assert response.status_code == 422
    db.refresh(booking)
    assert booking.status == VenueBookingStatus.REQUESTED
    assert db.scalar(select(func.count()).select_from(EquipmentReservation)) == 1


# --- AC 6: who hears ---


async def test_tc_us9_19_everyone_involved_hears_once(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event, notifier: FakeNotifier
) -> None:
    venue_staff = make_user(db, UserRole.VENUE_STAFF)
    make_user(db, UserRole.VENUE_STAFF, active=False)
    make_venue_booking(
        db, event=event, venue=make_venue(db), user=coordinator, status=VenueBookingStatus.APPROVED,
        decided_by_user_id=venue_staff.id,
    )
    tech = make_user(db, UserRole.TECH_SUPPORT)
    gone = make_user(db, UserRole.TECH_SUPPORT)
    deactivated = make_user(db, UserRole.TECH_SUPPORT, active=False)
    db.add(TechStaffAssignment(event_id=event.id, staff_user_id=tech.id, assigned_by_user_id=coordinator.id))
    db.add(TechStaffAssignment(event_id=event.id, staff_user_id=deactivated.id, assigned_by_user_id=coordinator.id))
    db.add(
        TechStaffAssignment(
            event_id=event.id, staff_user_id=gone.id, assigned_by_user_id=coordinator.id,
            unassigned_by_user_id=coordinator.id, unassigned_at=NOW - timedelta(days=1),
        )
    )
    registered, waiting, offered, lapsed, withdrawn = (make_attendee(db) for _ in range(5))
    make_registration(db, event, registered)
    make_registration(db, event, waiting, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW)
    make_registration(db, event, offered, status=RegistrationStatus.OFFERED, offer_expires_at=NOW + timedelta(hours=1))
    # Past its window, but no read has swept it yet (D2): it holds no place, so isn't told.
    make_registration(db, event, lapsed, status=RegistrationStatus.OFFERED, offer_expires_at=NOW - timedelta(hours=1))
    make_registration(db, event, withdrawn, status=RegistrationStatus.WITHDRAWN)

    await cancel(client, event, coordinator)

    told = {(call["email"], call["recipient"]) for call in notifier.cancellations}
    assert told == {
        (organiser.email, "organiser"),
        (venue_staff.email, "venue_staff"),
        (tech.email, "tech_support"),
        (registered.email, "attendee"),
        (waiting.email, "attendee"),
        (offered.email, "attendee"),
    }
    assert len(notifier.cancellations) == len(told)
    assert {(call["event_name"], call["reason"], call["event_id"]) for call in notifier.cancellations} == {
        ("Design Thinking Lab", REASON, event.id)
    }


async def test_tc_us9_19_venue_staff_hear_only_when_an_approved_venue_was_released(
    client: AsyncClient, db: Session, coordinator: User, event: Event, notifier: FakeNotifier
) -> None:
    make_user(db, UserRole.VENUE_STAFF)
    # A request they hadn't decided yet just leaves their queue, as a withdrawn one does (D69).
    make_venue_booking(db, event=event, venue=make_venue(db), user=coordinator)

    await cancel(client, event, coordinator)

    assert {call["recipient"] for call in notifier.cancellations} == {"organiser"}


async def test_tc_us9_19_a_failed_notice_doesnt_undo_the_cancel(
    client: AsyncClient, db: Session, coordinator: User, event: Event, notifier: FakeNotifier
) -> None:
    notifier.fail = True

    response = await cancel(client, event, coordinator)

    assert response.status_code == 200
    db.refresh(event)
    assert event.status == EventStatus.CANCELLED


# --- AC 7: once it has started ---


async def test_tc_us9_20_an_event_that_has_started_cant_be_cancelled(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    started = owned_event(db, organiser, coordinator, start_at=NOW - timedelta(minutes=1))

    asked = await ask(client, started, organiser)
    cancelled = await cancel(client, started, coordinator)

    for response in (asked, cancelled):
        assert response.status_code == 409
        assert response.json()["code"] == "EVENT_STARTED"
    db.refresh(started)
    assert started.status == EventStatus.PLANNING
    assert rows(db, started) == 0


async def test_tc_us9_20_a_request_cant_be_approved_once_the_event_starts(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    requested = (await ask(client, event, organiser)).json()
    event.start_at = NOW - timedelta(minutes=1)
    db.flush()

    response = await decide(client, requested["id"], coordinator, "approve")

    assert (response.status_code, response.json()["code"]) == (409, "EVENT_STARTED")
    row = db.get(EventCancellation, uuid.UUID(requested["id"]))
    db.refresh(row)
    assert row.status == CancellationStatus.PENDING  # left for the coordinator to reject


def approved_request(db: Session, organiser: User, coordinator: User, *dates: date) -> Event:
    event = owned_event(db, organiser, coordinator, EventStatus.APPROVED)
    event.preferred_dates = list(dates)
    event.preferred_start_time = time(9, 0)
    db.flush()
    return event


async def test_tc_us9_20_an_approved_request_starts_by_its_last_preferred_date(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    past, future = date(2026, 1, 1), NOW.date() + timedelta(days=30)
    still_possible = approved_request(db, organiser, coordinator, past, future)
    all_passed = approved_request(db, organiser, coordinator, past, date(2026, 2, 1))

    ahead = await ask(client, still_possible, organiser)
    passed = await ask(client, all_passed, organiser)

    assert ahead.status_code == 201  # it may be on the later date (D101)
    assert (passed.status_code, passed.json()["code"]) == (409, "EVENT_STARTED")


async def test_tc_us9_20_an_approved_request_with_a_venue_starts_at_its_booking(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    booked = approved_request(db, organiser, coordinator, NOW.date() + timedelta(days=30))
    make_venue_booking(
        db, event=booked, venue=make_venue(db), user=coordinator, starts_at=NOW - timedelta(hours=1),
        status=VenueBookingStatus.APPROVED, decided_by_user_id=make_user(db, UserRole.VENUE_STAFF).id,
    )

    response = await ask(client, booked, organiser)

    assert (response.status_code, response.json()["code"]) == (409, "EVENT_STARTED")


# --- AC 8: the record ---


async def test_tc_us9_22_the_organiser_and_coordinator_read_the_history(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    first = (await ask(client, event, organiser)).json()
    await decide(client, first["id"], coordinator, "reject", "Go ahead")
    second = (await ask(client, event, organiser, "Asking again")).json()
    url = f"/api/v1/event-requests/{event.id}/cancellations"

    for reader in (organiser, coordinator, make_user(db, UserRole.COORDINATOR_LEAD)):
        response = await client.get(url, headers=auth(reader))
        assert response.status_code == 200
        listed = response.json()["cancellations"]
        assert [row["id"] for row in listed] == [second["id"], first["id"]]
    for outsider in (make_user(db, UserRole.ORGANISER), make_user(db, UserRole.COORDINATOR)):
        response = await client.get(url, headers=auth(outsider))
        assert (response.status_code, response.json()) == (404, {"code": "NOT_FOUND"})


# --- The waitlist after a cancel ---


async def test_tc_us9_23_an_offer_on_a_cancelled_event_cant_be_taken_up(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    attendee = make_attendee(db)
    offer = make_registration(
        db, event, attendee, status=RegistrationStatus.OFFERED, offer_expires_at=NOW + WAITLIST_OFFER_WINDOW
    )
    await cancel(client, event, coordinator)

    response = await client.post(f"/api/v1/registrations/{offer.id}/accept", headers=attendee_auth(attendee))

    assert (response.status_code, response.json()) == (409, {"code": "EVENT_CANCELLED"})
    db.refresh(offer)
    assert offer.status == RegistrationStatus.OFFERED


async def test_tc_us9_23_a_freed_place_isnt_offered_on_a_cancelled_event(
    client: AsyncClient, db: Session, coordinator: User, event: Event, notifier: FakeNotifier
) -> None:
    event.capacity = 1
    db.flush()
    holder, waiting = make_attendee(db), make_attendee(db)
    registration = make_registration(db, event, holder)
    queued = make_registration(db, event, waiting, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW)
    await cancel(client, event, coordinator)

    response = await client.post(f"/api/v1/registrations/{registration.id}/withdraw", headers=attendee_auth(holder))

    assert response.status_code == 200, response.text
    db.refresh(queued)
    assert queued.status == RegistrationStatus.WAITLISTED
    assert notifier.offers == []


async def test_tc_us9_22_the_coordinator_opens_a_cancelled_event_from_their_queue(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    dateless = owned_event(db, organiser, coordinator, EventStatus.APPROVED)
    dateless.capacity = None
    db.flush()
    for target in (event, dateless):
        await cancel(client, target, coordinator)

    queue = await client.get("/api/v1/event-requests", headers=auth(coordinator))
    opened = [
        await client.get(f"/api/v1/event-requests/{target.id}", headers=auth(coordinator)) for target in (event, dateless)
    ]
    by_other = await client.get(f"/api/v1/event-requests/{event.id}", headers=auth(make_user(db, UserRole.COORDINATOR)))

    assert {row["id"]: row["status"] for row in queue.json()["event_requests"]} == {
        str(event.id): "cancelled",
        str(dateless.id): "cancelled",
    }
    assert [(response.status_code, response.json()["status"]) for response in opened] == [(200, "cancelled")] * 2
    assert by_other.status_code == 404


# --- AC 4, 8: the two tables agree (Matt's review of #115) ---


async def test_tc_us9_25_every_cancelled_event_has_exactly_one_approved_cancellation(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    by_request, direct, rejected, untouched = (owned_event(db, organiser, coordinator) for _ in range(4))
    asked = (await ask(client, by_request, organiser)).json()
    await decide(client, asked["id"], coordinator, "approve")
    await cancel(client, direct, coordinator)
    refused = (await ask(client, rejected, organiser)).json()
    await decide(client, refused["id"], coordinator, "reject", "Go ahead")
    await cancel(client, by_request, coordinator, "Again")  # refused: already cancelled

    ids = [event.id for event in (by_request, direct, rejected, untouched)]
    statuses = dict(db.execute(select(Event.id, Event.status).where(Event.id.in_(ids))).all())
    approved = dict(
        db.execute(
            select(EventCancellation.event_id, func.count())
            .where(EventCancellation.event_id.in_(ids), EventCancellation.status == CancellationStatus.APPROVED)
            .group_by(EventCancellation.event_id)
        ).all()
    )
    assert {event_id for event_id, status in statuses.items() if status == EventStatus.CANCELLED} == set(approved)
    assert set(approved) == {by_request.id, direct.id}
    assert set(approved.values()) == {1}
    flags = db.scalars(select(EventCancellation.direct).where(EventCancellation.event_id.in_(ids))).all()
    assert sorted(flags) == [False, False, True]  # the approved request, the rejected one, the direct cancel



# --- Work still open on a cancelled event (Matt's review of #117) ---


async def test_tc_us9_33_cancelling_rejects_the_events_pending_change_requests(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    pending = EventChangeRequest(
        event_id=event.id, requested_by_user_id=organiser.id, reason="Bigger room",
        changes=[{"field": "expected_attendees", "old_value": 40, "new_value": 60}],
    )
    other = owned_event(db, organiser, coordinator)
    elsewhere = EventChangeRequest(
        event_id=other.id, requested_by_user_id=organiser.id, reason="Bigger room",
        changes=[{"field": "expected_attendees", "old_value": 40, "new_value": 60}],
    )
    db.add_all([pending, elsewhere])
    db.flush()

    await cancel(client, event, coordinator)

    db.refresh(pending)
    db.refresh(elsewhere)
    assert (pending.status, elsewhere.status) == (ChangeRequestStatus.REJECTED, ChangeRequestStatus.PENDING_APPROVAL)


async def test_tc_us9_33_tech_support_neither_lists_nor_reviews_a_cancelled_events_pending_line(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event
) -> None:
    tech = make_user(db, UserRole.TECH_SUPPORT)
    line = EquipmentRequestLine(
        event_id=event.id, equipment_type_id=make_approved_line(db).equipment_type_id, quantity=1,
        requested_by_user_id=coordinator.id,
    )
    db.add(line)
    db.flush()
    await cancel(client, event, coordinator)

    queue = await client.get("/api/v1/equipment-lines?status=pending", headers=auth(tech))
    reviewed = await client.post(
        f"/api/v1/equipment-lines/{line.id}/review", headers=auth(tech), json={"decision": "approved"}
    )

    assert str(line.id) not in queue.text
    assert (reviewed.status_code, reviewed.json()) == (409, {"code": "EVENT_NOT_ELIGIBLE", "status": "cancelled"})
    db.refresh(line)
    assert line.status == EquipmentLineStatus.PENDING


async def test_tc_us9_33_the_safety_officer_neither_lists_nor_reviews_a_cancelled_event(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    officer = make_user(db, UserRole.SAFETY_OFFICER)
    await cancel(client, event, coordinator)

    queue = await client.get("/api/v1/safety-reviews", headers=auth(officer))
    reviewed = await client.post(f"/api/v1/safety-reviews/{event.id}", headers=auth(officer), json=approval())

    assert str(event.id) not in queue.text
    assert (reviewed.status_code, reviewed.json()) == (
        409,
        {"code": "SAFETY_REVIEW_NOT_ALLOWED", "reason": "status", "status": "cancelled"},
    )
    assert db.scalar(select(func.count()).select_from(SafetyReview).where(SafetyReview.event_id == event.id)) == 0


# --- Nobody to decide, and a stale pending booking (Matt's review of #117) ---


async def test_tc_us9_34_with_no_active_coordinator_the_leads_are_told(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, event: Event, notifier: FakeNotifier
) -> None:
    leads = [make_user(db, UserRole.COORDINATOR_LEAD) for _ in range(2)]
    make_user(db, UserRole.COORDINATOR_LEAD, active=False)
    coordinator.is_active = False
    db.flush()

    response = await ask(client, event, organiser)

    assert response.status_code == 201
    assert sorted(call["email"] for call in notifier.cancellation_requests) == sorted(lead.email for lead in leads)


async def test_tc_us9_35_a_pending_booking_in_the_past_doesnt_count_as_the_start(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    approved = approved_request(db, organiser, coordinator, NOW.date() + timedelta(days=30))
    make_venue_booking(db, event=approved, venue=make_venue(db), user=coordinator, starts_at=NOW - timedelta(hours=1))

    response = await ask(client, approved, organiser)

    assert response.status_code == 201  # never approved, so it doesn't place the event (D101)
