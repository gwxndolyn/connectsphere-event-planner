"""US17 (SCRUM-84): the assigned coordinator approves or rejects an event request under review."""

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import DeliveryMode, Event, EventStatus
from app.user.models import User, UserRole
from tests.conftest import FakeNotifier
from tests.event.test_event_request_clarification_api import auth, make_request
from tests.factories import NOW, make_user

pytestmark = pytest.mark.anyio


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def coordinator(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.full_name = "Casey Tan"
    db.flush()
    return user


def assigned_request(
    db: Session, organiser: User, coordinator: User | None, status: EventStatus = EventStatus.UNDER_REVIEW
) -> Event:
    past_request_stage = status in (EventStatus.CANCELLED, EventStatus.PLANNING)
    event = make_request(db, organiser, EventStatus.UNDER_REVIEW if past_request_stage else status)
    event.request_reference = f"ER-2026-{uuid.uuid4().int % 900000 + 100000}"
    event.coordinator_id = coordinator.id if coordinator else None
    if past_request_stage:
        # Past the request stage, an event needs its final fields (events_final_fields_required).
        event.start_at = NOW + timedelta(days=10)
        event.end_at = event.start_at + timedelta(hours=2)
        event.capacity = 40
        event.delivery_mode = DeliveryMode.IN_PERSON
        event.status = status
    db.flush()
    return event


async def approve(client: AsyncClient, user: User | None, request_id: uuid.UUID):
    return await client.post(
        f"/api/v1/event-requests/{request_id}/approve", headers=auth(user) if user else {}
    )


async def reject(client: AsyncClient, user: User | None, request_id: uuid.UUID, body: dict | None = None):
    return await client.post(
        f"/api/v1/event-requests/{request_id}/reject",
        json={"reason": "The date clashes with exams."} if body is None else body,
        headers=auth(user) if user else {},
    )


def unchanged(db: Session, event: Event, status: EventStatus) -> None:
    db.refresh(event)
    assert (event.status, event.decided_at, event.decided_by_user_id, event.rejection_reason) == (
        status,
        None,
        None,
        None,
    )


async def test_tc_us17_01_the_assigned_coordinator_approves_a_request_under_review(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = assigned_request(db, organiser, coordinator)

    response = await approve(client, coordinator, event.id)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["decided_by"] == {"id": str(coordinator.id), "name": "Casey Tan"}
    assert body["decided_at"] is not None
    assert body["rejection_reason"] is None
    db.refresh(event)
    assert (event.status, event.decided_at, event.decided_by_user_id) == (EventStatus.APPROVED, NOW, coordinator.id)


async def test_tc_us17_02_rejecting_stores_the_trimmed_reason(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = assigned_request(db, organiser, coordinator)

    response = await reject(client, coordinator, event.id, {"reason": "  The date clashes with exams. "})

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["rejection_reason"]) == (
        "rejected",
        "The date clashes with exams.",
    )
    db.refresh(event)
    assert (event.status, event.rejection_reason, event.decided_by_user_id, event.decided_at) == (
        EventStatus.REJECTED,
        "The date clashes with exams.",
        coordinator.id,
        NOW,
    )


@pytest.mark.parametrize("body", [{}, {"reason": None}, {"reason": "   "}])
async def test_tc_us17_03_a_rejection_without_a_reason_is_refused(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier, body: dict
) -> None:
    event = assigned_request(db, organiser, coordinator)

    response = await reject(client, coordinator, event.id, body)

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": ["reason"]}
    unchanged(db, event, EventStatus.UNDER_REVIEW)
    assert notifier.request_decisions == []


async def test_tc_us17_04_another_coordinators_or_an_unassigned_request_is_not_found(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    theirs = assigned_request(db, organiser, make_user(db, UserRole.COORDINATOR))
    unassigned = assigned_request(db, organiser, None, EventStatus.SUBMITTED)

    for event, status in ((theirs, EventStatus.UNDER_REVIEW), (unassigned, EventStatus.SUBMITTED)):
        for response in (await approve(client, coordinator, event.id), await reject(client, coordinator, event.id)):
            assert response.status_code == 404
            assert response.json() == {"code": "NOT_FOUND"}
        unchanged(db, event, status)


async def test_tc_us17_05_awaiting_clarification_can_not_be_decided(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = assigned_request(db, organiser, coordinator, EventStatus.AWAITING_CLARIFICATION)

    for response in (await approve(client, coordinator, event.id), await reject(client, coordinator, event.id)):
        assert response.status_code == 409
        assert response.json() == {"code": "REQUEST_NOT_DECIDABLE", "status": "awaiting_clarification"}
    unchanged(db, event, EventStatus.AWAITING_CLARIFICATION)


@pytest.mark.parametrize("status", [EventStatus.APPROVED, EventStatus.REJECTED, EventStatus.CANCELLED])
async def test_tc_us17_06_an_already_decided_or_cancelled_request_is_refused_and_unchanged(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, status: EventStatus
) -> None:
    event = assigned_request(db, organiser, coordinator, status)

    for response in (await approve(client, coordinator, event.id), await reject(client, coordinator, event.id)):
        assert response.status_code == 409
        assert response.json() == {"code": "REQUEST_NOT_DECIDABLE", "status": status.value}
    unchanged(db, event, status)


async def test_tc_us17_07_a_draft_or_unknown_request_is_not_found(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    draft = assigned_request(db, organiser, coordinator, EventStatus.DRAFT)

    for request_id in (draft.id, uuid.uuid4()):
        assert (await approve(client, coordinator, request_id)).status_code == 404
        assert (await reject(client, coordinator, request_id)).status_code == 404


@pytest.mark.parametrize(
    "role", [UserRole.ORGANISER, UserRole.COORDINATOR_LEAD, UserRole.VENUE_STAFF, UserRole.ATTENDEE]
)
async def test_tc_us17_08_only_coordinators_may_decide(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, role: UserRole
) -> None:
    event = assigned_request(db, organiser, coordinator)
    other = make_user(db, role)

    for response in (await approve(client, other, event.id), await reject(client, other, event.id)):
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"
    assert (await approve(client, None, event.id)).status_code == 401
    unchanged(db, event, EventStatus.UNDER_REVIEW)


async def test_tc_us17_09_no_one_decides_a_request_they_created(client: AsyncClient, db: Session) -> None:
    both = make_user(db, UserRole.ORGANISER, UserRole.COORDINATOR)
    event = assigned_request(db, both, both)

    for response in (await approve(client, both, event.id), await reject(client, both, event.id)):
        # D51, checked before the status: the refusal doesn't depend on the request's state.
        assert response.status_code == 403
        assert response.json() == {"code": "SELF_DECISION_NOT_ALLOWED"}
    unchanged(db, event, EventStatus.UNDER_REVIEW)


async def test_tc_us17_10_the_organiser_is_told_the_outcome_and_a_rejections_reason(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier
) -> None:
    approved = assigned_request(db, organiser, coordinator)
    rejected = assigned_request(db, organiser, coordinator)

    await approve(client, coordinator, approved.id)
    await reject(client, coordinator, rejected.id)

    assert notifier.request_decisions == [
        {
            "email": organiser.email,
            "request_reference": approved.request_reference,
            "event_name": "Community design workshop",
            "decision": "approved",
            "reason": None,
        },
        {
            "email": organiser.email,
            "request_reference": rejected.request_reference,
            "event_name": "Community design workshop",
            "decision": "rejected",
            "reason": "The date clashes with exams.",
        },
    ]


async def test_tc_us17_11_a_refused_decision_tells_no_one(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier
) -> None:
    event = assigned_request(db, organiser, coordinator, EventStatus.AWAITING_CLARIFICATION)

    await approve(client, coordinator, event.id)
    await reject(client, coordinator, event.id)

    assert notifier.request_decisions == []


async def test_tc_us17_12_a_failed_notice_does_not_undo_the_decision(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier
) -> None:
    notifier.fail = True
    event = assigned_request(db, organiser, coordinator)

    response = await approve(client, coordinator, event.id)

    assert response.status_code == 200
    db.refresh(event)
    assert event.status == EventStatus.APPROVED


async def test_tc_us17_13_the_organiser_sees_the_outcome_and_reason_on_their_request(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = assigned_request(db, organiser, coordinator)
    await reject(client, coordinator, event.id)

    one = (await client.get(f"/api/v1/event-requests/{event.id}", headers=auth(organiser))).json()
    [mine] = (await client.get("/api/v1/me/event-requests", headers=auth(organiser))).json()["event_requests"]

    for seen in (one, mine):
        assert seen["status"] == "rejected"
        assert seen["rejection_reason"] == "The date clashes with exams."
        assert seen["decided_by"]["name"] == "Casey Tan"
        assert seen["decided_at"] is not None


@pytest.mark.parametrize("body", [{"reason": "x", "status": "approved"}, {"reason": "x" * 1001}])
async def test_tc_us17_14_an_unknown_field_or_an_overlong_reason_is_rejected(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, body: dict
) -> None:
    event = assigned_request(db, organiser, coordinator)

    response = await reject(client, coordinator, event.id, body)

    assert response.status_code == 422
    unchanged(db, event, EventStatus.UNDER_REVIEW)


@pytest.mark.parametrize(
    "change",
    [
        {"status": EventStatus.UNDER_REVIEW, "rejection_reason": "Not rejected"},
        {"status": EventStatus.APPROVED, "decided_by_user_id": "creator"},
    ],
)
def test_tc_us17_15_the_database_keeps_reasons_to_rejections_and_deciders_off_their_own_requests(
    db: Session, organiser: User, coordinator: User, change: dict
) -> None:
    event = assigned_request(db, organiser, coordinator)
    for field, value in change.items():
        setattr(event, field, organiser.id if value == "creator" else value)

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
