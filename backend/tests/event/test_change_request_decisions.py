"""US29b review an event change request, PR 2 (SCRUM-142, story SCRUM-98): the coordinator, or a Lead for a
coordinator's own US12 edit, lists pending change requests and approves or rejects them; a significant approval
moves a Confirmed event back to Planning, flags its arrangements and clears its safety approval.
See docs/testing/US29b-change-request-review.md (TC-US29B-08 to 21, 23, 24)."""

import logging
import threading
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

import app.event.change_decision_service as decision_module
from app.agenda.models import EventSession
from app.core.exceptions import DomainError
from app.equipment.models import EquipmentLineStatus
from app.event.change_decision_service import change_decision_service
from app.event.change_request_service import _json
from app.event.models import (
    ChangeRequestStatus,
    DeliveryMode,
    Event,
    EventAuditEntry,
    EventChangeRequest,
    EventReviewFlag,
    EventStatus,
)
from app.registration.models import Registration, RegistrationStatus
from app.safety.models import SafetyReview
from app.safety.state import latest_review, safety_state
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.equipment.test_equipment_api import make_line
from tests.equipment.test_equipment_schema import make_type
from tests.event.test_change_requests import submitted_event
from tests.event.test_confirmation import approve_safety, book, reserve
from tests.event.test_event_request_clarification_api import auth
from tests.factories import NOW, make_attendee, make_registration, make_user, make_venue

pytestmark = pytest.mark.anyio

URL = "/api/v1/change-requests"
SAFETY = "/api/v1/safety-reviews"
REASON = "Two more teams are joining."
LATER = timedelta(hours=1)


@pytest.fixture
def organiser(db: Session) -> User:
    user = make_user(db, UserRole.ORGANISER)
    user.full_name = "Olivia Organiser"
    db.flush()
    return user


@pytest.fixture
def coordinator(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.full_name = "Casey Tan"
    db.flush()
    return user


@pytest.fixture
def lead(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR_LEAD)


@pytest.fixture
def venue_staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def tech(db: Session) -> User:
    return make_user(db, UserRole.TECH_SUPPORT)


@pytest.fixture
def officer(db: Session) -> User:
    return make_user(db, UserRole.SAFETY_OFFICER)


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db, name="SCIS Seminar Room 2-1", capacity=60)


def change(event: Event, field: str, new: object) -> dict:
    """One field of a request, its old value in the form US29a and US12 store it."""
    return {"field": field, "old_value": _json(getattr(event, field)), "new_value": new}


def pending(db: Session, event: Event, requester: User, changes: list[dict], reason: str | None = REASON) -> EventChangeRequest:
    request = EventChangeRequest(event_id=event.id, requested_by_user_id=requester.id, changes=changes, reason=reason, created_at=NOW)
    db.add(request)
    db.flush()
    return request


def confirmed_event(db: Session, organiser: User, coordinator: User) -> Event:
    event = submitted_event(db, organiser, EventStatus.CONFIRMED, coordinator=coordinator)
    event.confirmed_at = NOW - timedelta(days=1)
    event.confirmed_by_user_id = coordinator.id
    event.expected_attendees = 40
    db.flush()
    return event


def move(event: Event, hours: int = 1) -> list[dict]:
    """A start-and-end change, later by `hours`: significant (D103)."""
    shift = timedelta(hours=hours)
    return [change(event, "start_at", (event.start_at + shift).isoformat()), change(event, "end_at", (event.end_at + shift).isoformat())]


async def approve(client: AsyncClient, user: User, request: EventChangeRequest):
    return await client.post(f"{URL}/{request.id}/approve", headers=auth(user))


async def reject(client: AsyncClient, user: User, request: EventChangeRequest, reason: object = "The venue is booked that week."):
    return await client.post(f"{URL}/{request.id}/reject", headers=auth(user), json={"reason": reason})


def flags(db: Session, event: Event) -> list[EventReviewFlag]:
    return db.scalars(select(EventReviewFlag).where(EventReviewFlag.event_id == event.id).order_by(EventReviewFlag.kind)).all()


def history(db: Session, event: Event) -> list[EventAuditEntry]:
    return db.scalars(
        select(EventAuditEntry).where(EventAuditEntry.event_id == event.id).order_by(EventAuditEntry.seq)
    ).all()


def approved_review(db: Session, event: Event, officer: User, created_at=None, outcome: str = "approved") -> SafetyReview:
    checklist = {key: {"result": "satisfactory", "comment": None} for key in (
        "attendance_capacity", "layout", "emergency_access", "accessibility", "equipment_placement",
        "crowd_movement", "venue_restrictions",
    )}
    extra = {"areas": ["layout"]} if outcome == "changes_requested" else {}
    review = SafetyReview(
        event_id=event.id, reviewer_id=officer.id, outcome=outcome, checklist=checklist,
        comments="All clear." if outcome == "approved" else "Move the stage.", created_at=created_at or NOW - timedelta(hours=1),
        **extra,
    )
    db.add(review)
    db.flush()
    return review


# --- TC-US29B-08 the coordinator's list: their events, current and proposed values (AC 1) ---


async def test_tc_us29b_08_the_coordinator_lists_pending_requests_on_their_events(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    mine = confirmed_event(db, organiser, coordinator)
    theirs = confirmed_event(db, organiser, make_user(db, UserRole.COORDINATOR))
    request = pending(db, mine, organiser, [change(mine, "name", "Design workshop, round two"), *move(mine)])
    pending(db, theirs, organiser, [change(theirs, "name", "Elsewhere")])
    decided = pending(db, mine, organiser, [change(mine, "purpose", "Old news")])
    decided.status, decided.decided_at, decided.decided_by_user_id = ChangeRequestStatus.APPROVED, NOW, coordinator.id
    db.flush()

    response = await client.get(URL, headers=auth(coordinator))

    assert response.status_code == 200, response.text
    [listed] = response.json()["change_requests"]
    assert listed["id"] == str(request.id)
    assert (listed["source"], listed["status"], listed["reason"], listed["significant"]) == (
        "organiser", "pending_approval", REASON, True
    )
    assert listed["event_status"] == "confirmed" and listed["requested_by"]["id"] == str(organiser.id)
    by_field = {c["field"]: c for c in listed["changes"]}
    assert by_field["name"]["current_value"] == "Community design workshop"
    assert by_field["name"]["new_value"] == "Design workshop, round two"
    assert by_field["start_at"]["label"] == "Start time" and by_field["start_at"]["stale"] is False
    assert listed["impact"]["status_after"] == "planning" and listed["impact"]["safety_review_required"] is False

    # Decided requests on request; one by id.
    everything = await client.get(URL, headers=auth(coordinator), params={"status": "all"})
    assert {r["id"] for r in everything.json()["change_requests"]} == {str(request.id), str(decided.id)}
    one = await client.get(f"{URL}/{request.id}", headers=auth(coordinator))
    assert one.status_code == 200 and one.json()["id"] == str(request.id)


async def test_tc_us29b_08_a_lead_lists_only_coordinators_own_edits_and_a_coordinator_not_their_own(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, lead: User
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    edit = pending(db, event, coordinator, [change(event, "capacity", 60)], reason=None)
    asked = pending(db, event, organiser, [change(event, "name", "Renamed")])

    as_lead = await client.get(URL, headers=auth(lead))
    as_coordinator = await client.get(URL, headers=auth(coordinator))

    assert [(r["id"], r["source"]) for r in as_lead.json()["change_requests"]] == [(str(edit.id), "coordinator")]
    assert [r["id"] for r in as_coordinator.json()["change_requests"]] == [str(asked.id)]


# --- TC-US29B-09 wrong role 403, not theirs 404 ---


async def test_tc_us29b_09_other_roles_are_refused_and_other_coordinators_find_nothing(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, venue_staff: User
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    request = pending(db, event, organiser, [change(event, "name", "Renamed")])
    attendee = make_user(db, UserRole.ATTENDEE)
    other = make_user(db, UserRole.COORDINATOR)

    for user in (organiser, attendee, venue_staff):
        assert (await client.get(URL, headers=auth(user))).status_code == 403
        assert (await client.get(f"{URL}/{request.id}", headers=auth(user))).status_code == 403
        assert (await approve(client, user, request)).status_code == 403
        assert (await reject(client, user, request)).status_code == 403
    for response in (
        await client.get(f"{URL}/{request.id}", headers=auth(other)),
        await approve(client, other, request),
        await reject(client, other, request),
        await approve(client, coordinator, type("R", (), {"id": uuid.uuid4()})()),
    ):
        assert (response.status_code, response.json()) == (404, {"code": "NOT_FOUND"})
    db.refresh(request)
    assert request.status == ChangeRequestStatus.PENDING_APPROVAL


# --- TC-US29B-10 a non-significant change is applied; the request stage just takes the values (AC 2, 4, 5) ---


async def test_tc_us29b_10_a_non_significant_change_is_applied_and_nothing_else_moves(
    client: AsyncClient, db: Session, notifier: FakeNotifier, organiser: User, coordinator: User, officer: User
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    approve_safety(db, event, officer)
    request = pending(db, event, organiser, [change(event, "name", "Design workshop II"), change(event, "purpose", "Round two")])

    response = await approve(client, coordinator, request)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status_change"], body["flags"], body["safety_review_required"]) == (None, [], False)
    assert body["change_request"]["status"] == "approved" and body["change_request"]["decided_by"]["id"] == str(coordinator.id)
    db.refresh(event)
    assert (event.name, event.purpose, event.status) == ("Design workshop II", "Round two", EventStatus.CONFIRMED)
    assert event.safety_approved_at is not None and event.confirmed_at is not None
    assert flags(db, event) == []
    assert [(e.action, e.field_name, e.change_request_id) for e in history(db, event)] == [
        ("applied", "name", request.id), ("applied", "purpose", request.id), ("decided", "change_request", request.id)
    ]
    [notice] = notifier.change_decisions
    assert (notice["email"], notice["decision"], notice["fields"]) == (organiser.email, "approved", ["name", "purpose"])


async def test_tc_us29b_10_a_significant_change_at_the_request_stage_just_takes_the_values(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    """Approved change 1 (D105): no flags, no status change before Approved."""
    event = submitted_event(db, organiser, EventStatus.SUBMITTED, coordinator=coordinator)
    later = NOW.date() + timedelta(days=9)
    request = pending(db, event, organiser, [change(event, "preferred_dates", [later.isoformat()])])

    listed = await client.get(f"{URL}/{request.id}", headers=auth(coordinator))
    assert listed.json()["significant"] is True
    assert listed.json()["impact"] == {
        "status_after": "submitted", "venue_bookings": None, "equipment_reservations": None, "registrations": None,
        "safety_review_required": None,
    }
    response = await approve(client, coordinator, request)

    assert response.status_code == 200, response.text
    assert (response.json()["status_change"], response.json()["flags"]) == (None, [])
    db.refresh(event)
    assert (event.status, event.preferred_dates) == (EventStatus.SUBMITTED, [later])
    assert flags(db, event) == []


# --- TC-US29B-11 a significant change moves a Confirmed event back to Planning and flags its arrangements (AC 3) ---


async def test_tc_us29b_11_a_significant_change_flags_the_live_arrangements_and_resets_nothing(
    client: AsyncClient, db: Session, notifier: FakeNotifier, organiser: User, coordinator: User,
    venue: Venue, venue_staff: User, tech: User,
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    live = book(db, event, venue, coordinator, venue_staff, starts_at=event.start_at, ends_at=event.end_at)
    withdrawn = book(db, event, make_venue(db), coordinator, venue_staff, status=VenueBookingStatus.WITHDRAWN)
    reserved = make_line(db, event=event, equipment_type=make_type(db), requested_by=coordinator,
                         status=EquipmentLineStatus.APPROVED, reviewer=tech)
    reservation = reserve(db, reserved, tech)
    unreserved = make_line(db, event=event, equipment_type=make_type(db), requested_by=coordinator,
                           status=EquipmentLineStatus.APPROVED, reviewer=tech)
    registrations = [make_registration(db, event, make_attendee(db)) for _ in range(2)]
    request = pending(db, event, organiser, move(event))

    response = await approve(client, coordinator, request)

    assert response.status_code == 200, response.text
    assert response.json()["status_change"] == {"from": "confirmed", "to": "planning"}
    db.refresh(event)
    assert (event.status, event.confirmed_at, event.confirmed_by_user_id) == (EventStatus.PLANNING, None, None)
    raised = flags(db, event)
    assert [(f.kind, f.venue_booking_id, f.equipment_request_line_id, f.fields) for f in raised] == [
        ("equipment_reservation", None, reserved.id, ["start_at", "end_at"]),
        ("registrations", None, None, ["start_at", "end_at"]),
        ("venue_booking", live.id, None, ["start_at", "end_at"]),
    ]
    assert all(f.change_request_id == request.id and f.cleared_at is None for f in raised)
    assert unreserved.id not in {f.equipment_request_line_id for f in raised}
    assert withdrawn.id not in {f.venue_booking_id for f in raised}
    # Nothing reset or deleted (AC 3).
    db.refresh(live)
    assert live.status == VenueBookingStatus.APPROVED and db.get(type(reservation), reservation.id) is not None
    assert {db.get(Registration, r.id).status for r in registrations} == {RegistrationStatus.CONFIRMED}
    # D104: Venue staff hear about the booking, Tech support about the reservation (log-only).
    assert {(n["email"], n["kind"]) for n in notifier.arrangement_flags} >= {
        (venue_staff.email, "venue_booking"), (tech.email, "equipment_reservation")
    }


async def test_tc_us29b_11_agenda_sessions_outside_the_moved_window_are_shown_not_flagged(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    """US15 D94: a session left outside the new window reads outside_window; D103 flags no sessions."""
    event = confirmed_event(db, organiser, coordinator)
    session = EventSession(
        event_id=event.id, title="Keynote", session_type="presentation", speaker_name="Dr Tan",
        starts_at=event.start_at, ends_at=event.start_at + timedelta(minutes=30),
    )
    db.add(session)
    db.flush()
    request = pending(db, event, organiser, move(event, hours=3))

    assert (await approve(client, coordinator, request)).status_code == 200
    agenda = await client.get(f"/api/v1/event-requests/{event.id}/sessions", headers=auth(organiser))

    assert agenda.status_code == 200, agenda.text
    assert [s["outside_window"] for s in agenda.json()["sessions"]] == [True]
    assert all(f.kind != "session" for f in flags(db, event))


# --- TC-US29B-12, 13 the safety approval (AC 6, D106, D99) ---


async def test_tc_us29b_12_a_significant_change_clears_the_safety_approval_and_keeps_the_review(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, officer: User,
    venue: Venue, venue_staff: User,
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    book(db, event, venue, coordinator, venue_staff, starts_at=event.start_at, ends_at=event.end_at)
    # US30b: changes were requested once, then the officer approved; the approval is the latest review.
    approved_review(db, event, officer, created_at=NOW - timedelta(hours=3), outcome="changes_requested")
    approved_review(db, event, officer, created_at=NOW - timedelta(hours=2))
    approve_safety(db, event, officer)
    request = pending(db, event, organiser, move(event))

    response = await approve(client, coordinator, request)

    assert response.status_code == 200, response.text
    assert response.json()["safety_review_required"] is True
    db.refresh(event)
    assert (event.safety_approved_at, event.safety_approved_by_user_id) == (None, None)
    # D106: pending, not changes_requested, though an earlier review asked for changes (D99).
    assert safety_state(event, latest_review(db, event.id)) == "pending"
    assert db.scalar(select(func.count()).where(SafetyReview.event_id == event.id)) == 2
    readiness = (await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(coordinator))).json()
    assert {i["kind"]: i["complete"] for i in readiness["items"]}["safety"] is False
    confirm = await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(coordinator))
    assert (confirm.status_code, confirm.json()["code"]) == (409, "EVENT_NOT_READY")

    # Out of the safety queue, and its review refused, while a flag is open (D106; approved change 2).
    def queued() -> list[str]:
        return [row["event_id"] for row in queue.json()["events"]]

    queue = await client.get(SAFETY, headers=auth(officer))
    assert str(event.id) not in queued()
    refused = await client.post(f"{SAFETY}/{event.id}", headers=auth(officer), json={})
    assert (refused.status_code, refused.json()) == (
        409, {"code": "SAFETY_REVIEW_NOT_ALLOWED", "reason": "review_flags_open", "status": "planning"}
    )
    for flag in flags(db, event):
        cleared = await client.post(f"/api/v1/review-flags/{flag.id}/clear", headers=auth(coordinator), json={})
        assert cleared.status_code == 200, cleared.text
    queue = await client.get(SAFETY, headers=auth(officer))
    assert str(event.id) in queued()


async def test_tc_us29b_13_the_approval_stays_without_a_significant_change_or_an_approval(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, officer: User
) -> None:
    approved = confirmed_event(db, organiser, coordinator)
    approve_safety(db, approved, officer)
    kept = approved.safety_approved_at
    never = confirmed_event(db, organiser, coordinator)

    assert (await approve(client, coordinator, pending(db, approved, organiser, [change(approved, "name", "Renamed")]))).status_code == 200
    response = await approve(client, coordinator, pending(db, never, organiser, move(never)))

    assert response.status_code == 200 and response.json()["safety_review_required"] is False
    db.refresh(approved)
    db.refresh(never)
    assert approved.safety_approved_at == kept
    assert (never.safety_approved_at, never.safety_approved_by_user_id) == (None, None)
    assert "safety_approval_cleared" not in {e.action for e in history(db, never)}


# --- TC-US29B-14, 15 rejecting, and a decided request (AC 2, 4, 5) ---


async def test_tc_us29b_14_rejecting_needs_a_reason_and_leaves_the_event_alone(
    client: AsyncClient, db: Session, notifier: FakeNotifier, organiser: User, coordinator: User
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    request = pending(db, event, organiser, move(event))
    starts = event.start_at

    missing = await reject(client, coordinator, request, reason="   ")
    too_long = await reject(client, coordinator, request, reason="x" * 1001)
    response = await reject(client, coordinator, request)

    assert (missing.status_code, missing.json()) == (422, {"code": "MISSING_REQUIRED_FIELD", "fields": ["reason"]})
    assert too_long.status_code == 422 and too_long.json()["code"] == "INVALID_CHANGE_DECISION"
    assert response.status_code == 200, response.text
    assert response.json()["change_request"]["rejection_reason"] == "The venue is booked that week."
    db.refresh(event)
    db.refresh(request)
    assert (event.start_at, event.status) == (starts, EventStatus.CONFIRMED)
    assert (request.status, request.decided_by_user_id) == (ChangeRequestStatus.REJECTED, coordinator.id)
    assert [(e.action, e.new_value) for e in history(db, event)] == [
        ("decided", {"decision": "rejected", "reason": "The venue is booked that week."})
    ]
    assert flags(db, event) == []
    [notice] = notifier.change_decisions
    assert (notice["decision"], notice["rejection_reason"]) == ("rejected", "The venue is booked that week.")


async def test_tc_us29b_15_a_decided_request_is_not_decided_again(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    request = pending(db, event, organiser, [change(event, "name", "Renamed")])
    assert (await approve(client, coordinator, request)).status_code == 200

    for response in (await approve(client, coordinator, request), await reject(client, coordinator, request)):
        assert (response.status_code, response.json()) == (409, {"code": "CHANGE_REQUEST_NOT_PENDING", "status": "approved"})


# --- TC-US29B-16, 17 two decisions at once (real races on two connections, as TC-US27-11) ---


class Committed:
    def __init__(self, ids: dict[str, list[uuid.UUID]]) -> None:
        self.ids = ids

    def decide(self, engine: Engine, decision: str, request_id: uuid.UUID) -> object:
        with Session(engine) as session:
            coordinator = session.get(User, self.ids["coordinator"][0])
            try:
                if decision == "approve":
                    change_decision_service.approve(session, coordinator, request_id, NOW, FakeNotifier())
                else:
                    change_decision_service.reject(session, coordinator, request_id, "Not now.", NOW, FakeNotifier())
                return 200
            except DomainError as error:
                return (error.status_code, error.code)


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    with Session(engine) as setup:
        organiser = make_user(setup, UserRole.ORGANISER)
        coordinator = make_user(setup, UserRole.COORDINATOR)
        event = confirmed_event(setup, organiser, coordinator)
        event.expected_attendees = 50
        setup.flush()
        requests = [
            pending(setup, event, organiser, [change(event, "expected_attendees", 60)]),
            pending(setup, event, organiser, [change(event, "expected_attendees", 70)]),
        ]
        setup.commit()
        rows = Committed({
            "coordinator": [coordinator.id], "users": [organiser.id, coordinator.id], "event": [event.id],
            "requests": [r.id for r in requests],
        })
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            event_id = rows.ids["event"][0]
            cleanup.execute(delete(EventReviewFlag).where(EventReviewFlag.event_id == event_id))
            cleanup.execute(delete(EventAuditEntry).where(EventAuditEntry.event_id == event_id))
            cleanup.execute(delete(EventChangeRequest).where(EventChangeRequest.event_id == event_id))
            cleanup.execute(delete(Event).where(Event.id == event_id))
            cleanup.execute(delete(User).where(User.id.in_(rows.ids["users"])))
            cleanup.commit()


def race(engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch, calls: list[tuple[str, uuid.UUID]]) -> list[object]:
    """Both sessions wait at a barrier just before locking the event, then both go."""
    barrier = threading.Barrier(2, timeout=10)
    original = decision_module._lock_event

    def wait_then_lock(*args: object, **kwargs: object) -> object:
        barrier.wait()
        return original(*args, **kwargs)

    monkeypatch.setattr(decision_module, "_lock_event", wait_then_lock)
    outcomes: list[object] = []
    threads = [threading.Thread(target=lambda c=c: outcomes.append(committed.decide(engine, *c))) for c in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return outcomes


def test_tc_us29b_16_approve_and_reject_at_once_decide_once(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_id = committed.ids["requests"][0]
    outcomes = race(engine, committed, monkeypatch, [("approve", request_id), ("reject", request_id)])

    assert sorted(outcomes, key=str) == sorted([200, (409, "CHANGE_REQUEST_NOT_PENDING")], key=str)
    with Session(engine) as check:
        decided = check.scalar(select(func.count()).where(
            EventAuditEntry.change_request_id == request_id, EventAuditEntry.action == "decided"
        ))
        request = check.get(EventChangeRequest, request_id)
        event = check.get(Event, committed.ids["event"][0])
        assert decided == 1
        assert event.expected_attendees == (60 if request.status == ChangeRequestStatus.APPROVED else 50)


def test_tc_us29b_16_two_approvals_at_once_apply_once(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_id = committed.ids["requests"][0]
    outcomes = race(engine, committed, monkeypatch, [("approve", request_id), ("approve", request_id)])

    assert sorted(outcomes, key=str) == sorted([200, (409, "CHANGE_REQUEST_NOT_PENDING")], key=str)
    with Session(engine) as check:
        applied = check.scalar(select(func.count()).where(
            EventAuditEntry.change_request_id == request_id, EventAuditEntry.action == "applied"
        ))
        assert applied == 1


def test_tc_us29b_17_two_requests_on_one_field_approved_at_once_the_second_is_stale(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = committed.ids["requests"]
    outcomes = race(engine, committed, monkeypatch, [("approve", first), ("approve", second)])

    assert sorted(outcomes, key=str) == sorted([200, (409, "CHANGE_REQUEST_STALE")], key=str)
    with Session(engine) as check:
        statuses = {check.get(EventChangeRequest, r).status for r in (first, second)}
        assert statuses == {ChangeRequestStatus.APPROVED, ChangeRequestStatus.PENDING_APPROVAL}
        assert check.get(Event, committed.ids["event"][0]).expected_attendees in (60, 70)


# --- TC-US29B-18 the event changed since the request (D107) ---


async def test_tc_us29b_18_a_field_saved_since_the_request_makes_it_stale(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = submitted_event(db, organiser, EventStatus.PLANNING, coordinator=coordinator)
    request = pending(db, event, organiser, [change(event, "purpose", "A new purpose"), change(event, "name", "Renamed")])
    saved = await client.patch(f"/api/v1/events/{event.id}", headers=auth(coordinator), json={"purpose": "Saved meanwhile"})
    assert saved.status_code == 200, saved.text

    response = await approve(client, coordinator, request)

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "CHANGE_REQUEST_STALE" and body["message"]
    assert body["fields"] == [{
        "field": "purpose", "reason": "changed", "requested_from": "Plan a community design session",
        "current": "Saved meanwhile", "proposed": "A new purpose",
    }]
    db.refresh(event)
    assert event.name == "Community design workshop"  # nothing applied
    assert (await reject(client, coordinator, request)).status_code == 200


async def test_tc_us29b_18_a_preference_on_an_event_now_in_planning_is_not_at_this_stage(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = submitted_event(db, organiser, EventStatus.APPROVED, coordinator=coordinator)
    request = pending(db, event, organiser, [change(event, "preferred_start_time", "10:00:00")])
    event.status = EventStatus.PLANNING
    event.start_at, event.end_at = NOW + timedelta(days=10), NOW + timedelta(days=10, hours=2)
    event.capacity, event.delivery_mode = 40, DeliveryMode.IN_PERSON
    db.flush()

    response = await approve(client, coordinator, request)

    assert response.status_code == 409
    assert [(f["field"], f["reason"]) for f in response.json()["fields"]] == [("preferred_start_time", "not_at_this_stage")]


async def test_tc_us29b_18_a_list_field_compares_its_values_in_order(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    """Approved change 3: preferred_dates is compared as a list of dates, in the stored order."""
    event = submitted_event(db, organiser, EventStatus.SUBMITTED, coordinator=coordinator)
    first, second = NOW.date() + timedelta(days=8), NOW.date() + timedelta(days=9)
    event.preferred_dates = [first, second]
    db.flush()
    same = pending(db, event, organiser, [change(event, "preferred_dates", [second.isoformat()])])
    stale = pending(db, event, organiser, [change(event, "preferred_dates", [first.isoformat()])])
    stale.changes = [{"field": "preferred_dates", "old_value": [first.isoformat(), (second + timedelta(days=1)).isoformat()],
                      "new_value": [first.isoformat()]}]
    db.flush()

    refused = await approve(client, coordinator, stale)
    accepted = await approve(client, coordinator, same)

    assert refused.status_code == 409
    assert [(f["field"], f["reason"]) for f in refused.json()["fields"]] == [("preferred_dates", "changed")]
    assert accepted.status_code == 200, accepted.text
    db.refresh(event)
    assert event.preferred_dates == [second]


async def test_tc_us29b_18_a_value_no_longer_valid_is_invalid(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    """The end asked for is now before a start that moved meanwhile; the end itself didn't change."""
    event = submitted_event(db, organiser, EventStatus.PLANNING, coordinator=coordinator)
    request = pending(db, event, organiser, [change(event, "end_at", (event.start_at + timedelta(hours=1)).isoformat())])
    event.start_at = event.start_at + timedelta(minutes=90)
    db.flush()

    response = await approve(client, coordinator, request)

    assert response.status_code == 409
    assert [(f["field"], f["reason"]) for f in response.json()["fields"]] == [("end_at", "invalid")]


# --- TC-US29B-19 approving is refused once the event is past changing (D105) ---


@pytest.mark.parametrize("status", [EventStatus.PREPARATION, EventStatus.CANCELLED, EventStatus.COMPLETED, EventStatus.REJECTED])
async def test_tc_us29b_19_approving_is_refused_late_but_rejecting_is_not(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, status: EventStatus
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    request = pending(db, event, organiser, [change(event, "name", "Renamed")])
    event.status = status
    db.flush()

    refused = await approve(client, coordinator, request)
    rejected = await reject(client, coordinator, request)

    assert (refused.status_code, refused.json()) == (409, {"code": "CHANGE_NOT_ALLOWED", "status": status.value})
    assert rejected.status_code == 200, rejected.text


# --- TC-US29B-20 a coordinator's own US12 edit goes to a Lead (D102, D51) ---


async def test_tc_us29b_20_a_coordinators_own_edit_is_decided_by_a_lead(
    client: AsyncClient, db: Session, notifier: FakeNotifier, organiser: User, coordinator: User, lead: User
) -> None:
    event = submitted_event(db, organiser, EventStatus.PLANNING, coordinator=coordinator)
    edit = pending(db, event, coordinator, [change(event, "capacity", 60)], reason=None)
    asked = pending(db, event, organiser, [change(event, "name", "Renamed")])

    own = await approve(client, coordinator, edit)
    not_theirs = await approve(client, lead, asked)
    by_lead = await approve(client, lead, edit)

    assert (own.status_code, own.json()) == (403, {"code": "SELF_DECISION_NOT_ALLOWED"})
    assert (not_theirs.status_code, not_theirs.json()) == (404, {"code": "NOT_FOUND"})
    assert by_lead.status_code == 200, by_lead.text
    db.refresh(event)
    assert event.capacity == 60
    # The requester hears, and the organiser too, since the edit changed their event (unclear point 4).
    assert {(n["email"], n["decision"]) for n in notifier.change_decisions} == {
        (coordinator.email, "approved"), (organiser.email, "approved")
    }


# --- TC-US29B-21 History records the decision and what it changed (AC 5) ---


async def test_tc_us29b_21_history_lists_the_decision_and_its_effects(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, officer: User
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    approve_safety(db, event, officer)
    approved_at, confirmed_at = event.safety_approved_at, event.confirmed_at
    request = pending(db, event, organiser, move(event))
    assert (await approve(client, coordinator, request)).status_code == 200

    response = await client.get(f"/api/v1/events/{event.id}/history", headers=auth(coordinator))

    assert response.status_code == 200, response.text
    entries = response.json()["entries"]
    assert [(e["action"], e["field"]) for e in entries] == [
        ("safety_approval_cleared", "safety_approval"),
        ("confirmation_cleared", "confirmation"),
        ("status_changed", "status"),
        ("decided", "change_request"),
        ("applied", "end_at"),
        ("applied", "start_at"),
    ]
    assert all(e["change_request_id"] == str(request.id) and e["user"]["id"] == str(coordinator.id) for e in entries)
    by_action = {e["action"]: e for e in entries}
    assert (by_action["status_changed"]["previous_value"], by_action["status_changed"]["new_value"]) == ("confirmed", "planning")
    # The same instants, in whatever offset the database gave them back in.
    safety = by_action["safety_approval_cleared"]["previous_value"]
    assert (datetime.fromisoformat(safety["approved_at"]), safety["approved_by"]) == (approved_at, str(officer.id))
    confirmation = by_action["confirmation_cleared"]["previous_value"]
    assert (datetime.fromisoformat(confirmation["confirmed_at"]), confirmation["confirmed_by"]) == (confirmed_at, str(coordinator.id))
    assert by_action["decided"]["new_value"] == {"decision": "approved"}


# --- TC-US29B-23 the organiser sees the outcome (AC 4) ---


async def test_tc_us29b_23_the_organiser_sees_each_decision(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    approved = pending(db, event, organiser, [change(event, "name", "Renamed")])
    rejected = pending(db, event, organiser, [change(event, "purpose", "Something else")])
    assert (await approve(client, coordinator, approved)).status_code == 200
    assert (await reject(client, coordinator, rejected, reason="Purpose is fixed by the faculty.")).status_code == 200

    response = await client.get("/api/v1/me/change-requests", headers=auth(organiser))

    by_id = {r["id"]: r for r in response.json()["change_requests"]}
    assert (by_id[str(approved.id)]["status"], by_id[str(approved.id)]["rejection_reason"]) == ("approved", None)
    assert by_id[str(approved.id)]["decided_at"] is not None
    assert (by_id[str(rejected.id)]["status"], by_id[str(rejected.id)]["rejection_reason"]) == (
        "rejected", "Purpose is fixed by the faculty."
    )


# --- TC-US29B-24 a notice that fails doesn't undo the decision (AC 4) ---


async def test_tc_us29b_24_a_failed_notice_is_logged_and_the_decision_stands(
    client: AsyncClient, db: Session, notifier: FakeNotifier, organiser: User, coordinator: User,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    request = pending(db, event, organiser, [change(event, "name", "Renamed")])
    notifier.fail = True

    with caplog.at_level(logging.ERROR):
        response = await approve(client, coordinator, request)

    assert response.status_code == 200, response.text
    db.refresh(request)
    assert request.status == ChangeRequestStatus.APPROVED
    assert "could not tell" in caplog.text
