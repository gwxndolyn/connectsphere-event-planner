"""US17 (SCRUM-84): the assigned coordinator approves or rejects an event request under review."""

import uuid
from datetime import date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.final_fields import preferred_window
from app.event.models import AssignmentKind, CoordinatorAssignment, DeliveryMode, Event, EventStatus
from app.user.models import User, UserRole
from tests.conftest import FakeNotifier
from tests.equipment.test_equipment_api import make_type
from tests.event.test_confirmation import approve_safety, book
from tests.event.test_event_request_clarification_api import auth, make_request
from tests.factories import NOW, SGT, make_user, make_venue

# What a submitted request always holds (its REQUIRED_FIELDS): approving turns them into the event's date (D123).
PREFERRED_DATE = date(2026, 10, 12)
PREFERRED_START, PREFERRED_END = time(10, 0), time(12, 0)
EXPECTED_ATTENDEES = 35
APPROVED_START = datetime.combine(PREFERRED_DATE, PREFERRED_START, tzinfo=SGT)
APPROVED_END = datetime.combine(PREFERRED_DATE, PREFERRED_END, tzinfo=SGT)

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
    past_request_stage = status in (EventStatus.CANCELLED, EventStatus.PLANNING, EventStatus.CONFIRMED)
    event = make_request(db, organiser, EventStatus.UNDER_REVIEW if past_request_stage else status)
    event.request_reference = f"ER-2026-{uuid.uuid4().int % 900000 + 100000}"
    event.coordinator_id = coordinator.id if coordinator else None
    event.preferred_dates = [PREFERRED_DATE]
    event.preferred_start_time, event.preferred_end_time = PREFERRED_START, PREFERRED_END
    event.expected_attendees = EXPECTED_ATTENDEES
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
    assert body["status"] == "planning"
    assert body["decided_by"] == {"id": str(coordinator.id), "name": "Casey Tan"}
    assert body["decided_at"] is not None
    assert body["rejection_reason"] is None
    db.refresh(event)
    assert (event.status, event.decided_at, event.decided_by_user_id) == (EventStatus.PLANNING, NOW, coordinator.id)


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


@pytest.mark.parametrize(
    "status",
    [EventStatus.APPROVED, EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.REJECTED, EventStatus.CANCELLED],
)
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
    assert event.status == EventStatus.PLANNING


async def test_tc_us17_13_the_organiser_sees_the_outcome_and_reason_on_their_request(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = assigned_request(db, organiser, coordinator)
    approved = assigned_request(db, organiser, coordinator)
    await reject(client, coordinator, event.id)
    await approve(client, coordinator, approved.id)

    def get(request_id: uuid.UUID):
        return client.get(f"/api/v1/event-requests/{request_id}", headers=auth(organiser))

    mine = {
        row["id"]: row
        for row in (await client.get("/api/v1/me/event-requests", headers=auth(organiser))).json()["event_requests"]
    }

    for seen in ((await get(event.id)).json(), mine[str(event.id)]):
        assert seen["status"] == "rejected"
        assert seen["rejection_reason"] == "The date clashes with exams."
        assert seen["decided_by"]["name"] == "Casey Tan"
        assert seen["decided_at"] is not None
    # An approved request is past the request stage (Planning), and its organiser still reads it and its decision.
    for seen in ((await get(approved.id)).json(), mine[str(approved.id)]):
        assert (seen["status"], seen["rejection_reason"], seen["decided_by"]["name"]) == ("planning", None, "Casey Tan")
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


# --- Approving moves a request to Planning (SCRUM-84 reopened: AC 2 corrected, D53, D123) ---


async def test_tc_us17_18_approving_gives_the_event_its_date_capacity_and_delivery_mode(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = assigned_request(db, organiser, coordinator)

    body = (await approve(client, coordinator, event.id)).json()

    db.refresh(event)
    # 10:00 to 12:00 on the preferred day, Singapore time (02:00 to 04:00 UTC).
    assert (event.start_at, event.end_at) == (APPROVED_START, APPROVED_END)
    assert (event.capacity, event.delivery_mode) == (EXPECTED_ATTENDEES, DeliveryMode.IN_PERSON)
    assert (datetime.fromisoformat(body["start_at"]), datetime.fromisoformat(body["end_at"])) == (APPROVED_START, APPROVED_END)


async def test_tc_us17_19_with_several_preferred_dates_the_earliest_is_used(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = assigned_request(db, organiser, coordinator)
    event.preferred_dates = [date(2026, 10, 20), PREFERRED_DATE, date(2026, 10, 15)]
    db.flush()

    await approve(client, coordinator, event.id)

    db.refresh(event)
    assert (event.start_at, event.end_at) == (APPROVED_START, APPROVED_END)


async def test_tc_us17_20_a_request_already_approved_into_planning_is_not_decided_again(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier
) -> None:
    event = assigned_request(db, organiser, coordinator)
    await approve(client, coordinator, event.id)
    notifier.request_decisions.clear()

    for response in (await approve(client, coordinator, event.id), await reject(client, coordinator, event.id)):
        assert response.status_code == 409
        assert response.json() == {"code": "REQUEST_NOT_DECIDABLE", "status": "planning"}
    db.refresh(event)
    assert (event.status, event.decided_at, event.decided_by_user_id, event.rejection_reason) == (
        EventStatus.PLANNING,
        NOW,
        coordinator.id,
        None,
    )
    assert (event.start_at, event.capacity) == (APPROVED_START, EXPECTED_ATTENDEES)
    assert notifier.request_decisions == []


async def test_tc_us17_21_a_just_approved_event_takes_equipment(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    """The bug that reopened SCRUM-84: equipment takes only Planning and Confirmed events, and an approved
    request stayed Approved, so Coordinator → Equipment never listed it."""
    event = assigned_request(db, organiser, coordinator)
    await approve(client, coordinator, event.id)

    listed = (await client.get("/api/v1/me/equipment-events", headers=auth(coordinator))).json()["events"]
    line = await client.post(
        f"/api/v1/events/{event.id}/equipment-lines",
        headers=auth(coordinator),
        json={"equipment_type_id": str(make_type(db, "Projector").id), "quantity": 1},
    )

    assert [(item["id"], item["status"]) for item in listed] == [(str(event.id), "planning")]
    assert line.status_code == 201


async def test_tc_us17_22_confirming_keeps_the_times_set_at_approval(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = assigned_request(db, organiser, coordinator)
    await approve(client, coordinator, event.id)
    # The booking sits inside the event's times (D65), shorter than them.
    book(
        db, event, make_venue(db), coordinator, make_user(db, UserRole.VENUE_STAFF),
        starts_at=APPROVED_START + timedelta(minutes=30), ends_at=APPROVED_END - timedelta(minutes=30),
    )
    approve_safety(db, event, make_user(db, UserRole.SAFETY_OFFICER))

    response = await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(coordinator))

    assert response.status_code == 200
    db.refresh(event)
    assert (event.status, event.start_at, event.end_at) == (EventStatus.CONFIRMED, APPROVED_START, APPROVED_END)


async def test_tc_us17_23_the_lead_sees_a_just_approved_request_on_the_assigned_tab(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    event = assigned_request(db, organiser, coordinator)
    db.add(
        CoordinatorAssignment(
            event_id=event.id, assigned_by_user_id=lead.id, coordinator_id=coordinator.id, kind=AssignmentKind.ASSIGNMENT
        )
    )
    db.flush()
    await approve(client, coordinator, event.id)

    response = await client.get("/api/v1/event-requests/assigned", headers=auth(lead))

    [row] = response.json()["event_requests"]
    assert (row["id"], row["status"], row["decided_by"]["name"]) == (str(event.id), "planning", "Casey Tan")
    assert row["decided_at"] is not None


async def test_tc_us17_24_the_confirmation_notice_gives_the_events_own_times(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier
) -> None:
    """US18 AC 4, after SCRUM-84: the event keeps the times set at approval, so the notice gives those, not
    its bookings' span, and agrees with the event page."""
    event = assigned_request(db, organiser, coordinator)
    await approve(client, coordinator, event.id)
    book(
        db, event, make_venue(db, name="SCIS Seminar Room 2-1"), coordinator, make_user(db, UserRole.VENUE_STAFF),
        starts_at=APPROVED_START + timedelta(minutes=30), ends_at=APPROVED_END - timedelta(minutes=30),
    )
    approve_safety(db, event, make_user(db, UserRole.SAFETY_OFFICER))

    await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(coordinator))

    [notice] = notifier.confirmations
    assert (notice["starts_at"], notice["ends_at"], notice["venues"]) == (
        APPROVED_START,
        APPROVED_END,
        ["SCIS Seminar Room 2-1"],
    )


def test_tc_us17_25_the_date_rule_needs_every_preference() -> None:
    """D123's rule on its own: without preferred dates, or a preferred time, there is no date to plan for. A
    submitted request always holds them (REQUIRED_FIELDS), so the API never meets these."""
    no_dates = Event(preferred_dates=None, preferred_start_time=PREFERRED_START, preferred_end_time=PREFERRED_END)
    no_end = Event(preferred_dates=[PREFERRED_DATE], preferred_start_time=PREFERRED_START, preferred_end_time=None)

    assert preferred_window(no_dates, NOW) == (None, None)
    assert preferred_window(no_end, NOW) == (None, None)


async def test_tc_us17_26_a_preferred_date_that_has_passed_is_skipped(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    """PR #142 review: a request can wait in review past its first option. NOW is 1 Oct, 09:00: 28 Sep has
    passed, and so has 1 Oct at 08:00, so 20 Oct is the first date that can still be planned and booked."""
    event = assigned_request(db, organiser, coordinator)
    event.preferred_dates = [date(2026, 9, 28), date(2026, 10, 1), date(2026, 10, 20)]
    event.preferred_start_time, event.preferred_end_time = time(8, 0), time(10, 0)
    db.flush()

    response = await approve(client, coordinator, event.id)

    assert response.status_code == 200
    db.refresh(event)
    assert (event.status, event.start_at, event.end_at) == (
        EventStatus.PLANNING,
        datetime(2026, 10, 20, 8, 0, tzinfo=SGT),
        datetime(2026, 10, 20, 10, 0, tzinfo=SGT),
    )


async def test_tc_us17_27_approving_is_refused_once_every_preferred_date_has_passed(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier
) -> None:
    event = assigned_request(db, organiser, coordinator)
    event.preferred_dates = [date(2026, 9, 28), date(2026, 9, 30)]
    db.flush()

    response = await approve(client, coordinator, event.id)

    assert response.status_code == 409
    assert response.json() == {"code": "PREFERRED_DATES_PASSED"}
    unchanged(db, event, EventStatus.UNDER_REVIEW)
    assert (event.start_at, event.capacity) == (None, None)
    assert notifier.request_decisions == []
    # Rejecting doesn't need a date, so it still works.
    assert (await reject(client, coordinator, event.id)).status_code == 200
