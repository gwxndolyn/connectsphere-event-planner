import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import EventStatus
from app.user.models import User, UserRole
from tests.event.test_event_request_clarification_api import BODY as CLARIFICATION, make_request, make_user, send
from tests.event.test_event_requests import auth, complete_request
from tests.factories import NOW, make_event

pytestmark = pytest.mark.anyio

UNASSIGNED = "/api/v1/event-requests/unassigned"


def assignment_url(request_id: uuid.UUID) -> str:
    return f"/api/v1/event-requests/{request_id}/assignment"


async def assign(client: AsyncClient, user: User | None, request_id: uuid.UUID, coordinator_id: uuid.UUID):
    headers = auth(user) if user else {}
    return await client.post(assignment_url(request_id), headers=headers, json={"coordinator_id": str(coordinator_id)})


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def lead(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR_LEAD)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


async def test_tc_us10a_05_submitting_leaves_the_request_unassigned_and_queued(
    client: AsyncClient, organiser: User, lead: User
) -> None:
    created = await client.post("/api/v1/event-requests", headers=auth(organiser), json=complete_request())
    request_id = created.json()["id"]
    submitted = await client.post(f"/api/v1/event-requests/{request_id}/submit", headers=auth(organiser))

    assert submitted.status_code == 200
    assert submitted.json()["coordinator"] is None  # AC 1, AC 8: the organiser sees "Unassigned"

    queue = await client.get(UNASSIGNED, headers=auth(lead))
    assert queue.status_code == 200
    assert [row["id"] for row in queue.json()["event_requests"]] == [request_id]


async def test_tc_us10a_06_queue_rows_carry_what_the_lead_needs_oldest_first(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    older = make_request(db, organiser)
    older.name, older.expected_attendees = "Older request", 30
    older.preferred_dates = [(NOW + timedelta(days=9)).date()]
    newer = make_request(db, organiser)
    newer.submitted_at = NOW
    db.flush()

    response = await client.get(UNASSIGNED, headers=auth(lead))

    rows = response.json()["event_requests"]
    assert [row["id"] for row in rows] == [str(older.id), str(newer.id)]
    first = rows[0]
    assert first["name"] == "Older request"
    assert first["organiser"]["id"] == str(organiser.id)
    assert first["organiser"]["email"] == organiser.email
    assert first["preferred_dates"] == [older.preferred_dates[0].isoformat()]
    assert first["expected_attendees"] == 30
    assert first["status"] == "submitted"


async def test_tc_us10a_07_queue_leaves_out_drafts_assigned_and_later_statuses(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    waiting = make_request(db, organiser)
    make_request(db, organiser, EventStatus.DRAFT)
    make_request(db, organiser, EventStatus.UNDER_REVIEW)
    owned = make_request(db, organiser)
    owned.coordinator_id = coordinator.id
    db.flush()

    response = await client.get(UNASSIGNED, headers=auth(lead))

    assert [row["id"] for row in response.json()["event_requests"]] == [str(waiting.id)]


async def test_tc_us10a_08_lead_assigns_an_active_coordinator(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    event = make_request(db, organiser)

    response = await assign(client, lead, event.id, coordinator.id)

    assert response.status_code == 200
    body = response.json()
    assert body["coordinator"] == {"id": str(coordinator.id), "name": coordinator.email}  # AC 3, 8
    assert body["status"] == "under_review"  # D26
    db.refresh(event)
    assert event.coordinator_id == coordinator.id and event.status == EventStatus.UNDER_REVIEW
    # AC 5: it has left the queue.
    queue = await client.get(UNASSIGNED, headers=auth(lead))
    assert queue.json()["event_requests"] == []


async def test_tc_us10a_09_organiser_sees_the_coordinators_name_not_email(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    coordinator.full_name = "Casey Tan"
    event = make_request(db, organiser)
    db.flush()
    await assign(client, lead, event.id, coordinator.id)

    mine = await client.get("/api/v1/me/event-requests", headers=auth(organiser))

    assert mine.json()["event_requests"][0]["coordinator"] == {"id": str(coordinator.id), "name": "Casey Tan"}


@pytest.mark.parametrize(
    ("role", "active", "reason"),
    [
        (UserRole.COORDINATOR, False, "inactive"),
        (UserRole.ORGANISER, True, "not_a_coordinator"),
        (UserRole.ATTENDEE, True, "not_a_coordinator"),
        (UserRole.COORDINATOR_LEAD, True, "not_a_coordinator"),
    ],
)
async def test_tc_us10a_10_ineligible_users_are_refused_with_a_reason(
    client: AsyncClient, db: Session, organiser: User, lead: User, role: UserRole, active: bool, reason: str
) -> None:
    event = make_request(db, organiser)
    target = make_user(db, role, active=active)

    response = await assign(client, lead, event.id, target.id)

    assert response.status_code == 422
    assert response.json() == {"code": "INVALID_COORDINATOR", "reason": reason}
    db.refresh(event)
    assert event.coordinator_id is None and event.status == EventStatus.SUBMITTED


async def test_tc_us10a_11_unknown_user_is_refused_and_nothing_changes(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    event = make_request(db, organiser)

    response = await assign(client, lead, event.id, uuid.uuid4())

    assert response.status_code == 422
    assert response.json()["reason"] == "unknown_user"
    db.refresh(event)
    assert event.coordinator_id is None


async def test_tc_us10a_12_lead_cannot_assign_themselves(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    event = make_request(db, organiser)

    response = await assign(client, lead, event.id, lead.id)

    assert response.status_code == 422
    assert response.json() == {"code": "INVALID_COORDINATOR", "reason": "self_assignment"}
    db.refresh(event)
    assert event.coordinator_id is None


async def test_tc_us10a_13_only_the_lead_can_assign_list_or_pick(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = make_request(db, organiser)
    ops = make_user(db, UserRole.OPERATIONS_MANAGER)
    attendee = make_user(db, UserRole.ATTENDEE)

    for user in (organiser, coordinator, ops, attendee):
        assert (await assign(client, user, event.id, coordinator.id)).status_code == 403
        assert (await client.get(UNASSIGNED, headers=auth(user))).status_code == 403
        assert (await client.get("/api/v1/coordinators", headers=auth(user))).status_code == 403
    assert (await assign(client, None, event.id, coordinator.id)).status_code == 401
    assert (await client.get(UNASSIGNED)).status_code == 401
    db.refresh(event)
    assert event.coordinator_id is None


async def test_tc_us10a_14_picker_lists_only_active_coordinators(
    client: AsyncClient, db: Session, lead: User, coordinator: User
) -> None:
    make_user(db, UserRole.COORDINATOR, active=False)
    make_user(db, UserRole.ORGANISER)

    response = await client.get("/api/v1/coordinators", headers=auth(lead))

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()["coordinators"]]
    assert str(coordinator.id) in ids and str(lead.id) not in ids
    assert len(ids) == len({*ids}) == 1


@pytest.mark.parametrize("status", [EventStatus.UNDER_REVIEW, EventStatus.AWAITING_CLARIFICATION, EventStatus.APPROVED])
async def test_tc_us10a_15_only_a_submitted_request_can_be_assigned(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User, status: EventStatus
) -> None:
    event = make_request(db, organiser, status)

    response = await assign(client, lead, event.id, coordinator.id)

    assert response.status_code == 409
    assert response.json() == {"code": "ASSIGNMENT_NOT_ALLOWED", "status": status.value}
    db.refresh(event)
    assert event.coordinator_id is None and event.status == status


async def test_tc_us10a_16_an_assigned_request_cannot_be_assigned_again(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    event = make_request(db, organiser)
    await assign(client, lead, event.id, coordinator.id)
    other = make_user(db, UserRole.COORDINATOR)

    response = await assign(client, lead, event.id, other.id)  # reassignment is SCRUM-83

    assert response.status_code == 409
    db.refresh(event)
    assert event.coordinator_id == coordinator.id


@pytest.mark.parametrize("status", [EventStatus.DRAFT, EventStatus.PLANNING, EventStatus.CONFIRMED])
async def test_tc_us10a_17_drafts_and_past_stage_events_and_unknown_ids_are_404(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User, status: EventStatus
) -> None:
    event = make_request(db, organiser, status) if status == EventStatus.DRAFT else make_event(db, status=status)

    assert (await assign(client, lead, event.id, coordinator.id)).status_code == 404
    assert (await assign(client, lead, uuid.uuid4(), coordinator.id)).status_code == 404


async def test_tc_us10a_18_lead_can_read_a_queued_request(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    event = make_request(db, organiser)

    response = await client.get(f"/api/v1/event-requests/{event.id}", headers=auth(lead))

    assert response.status_code == 200
    assert response.json()["coordinator"] is None


async def test_tc_us10a_19_a_returned_request_stays_with_its_coordinator_after_the_reply(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    event = make_request(db, organiser)
    await assign(client, lead, event.id, coordinator.id)
    assert (await send(client, coordinator, event.id, CLARIFICATION)).status_code == 201

    reply = await client.post(
        f"/api/v1/event-requests/{event.id}/clarifications/response",
        headers=auth(organiser),
        json={"comment": "40 people, theatre layout."},
    )

    assert reply.status_code == 201
    db.refresh(event)
    assert event.status == EventStatus.UNDER_REVIEW
    assert event.coordinator_id == coordinator.id  # AC 10: not back in the unassigned queue
    queue = await client.get(UNASSIGNED, headers=auth(lead))
    assert queue.json()["event_requests"] == []


async def test_tc_us10a_20_events_assigned_before_this_change_keep_their_coordinator(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    event = make_request(db, organiser, EventStatus.UNDER_REVIEW)
    event.coordinator_id = coordinator.id
    db.flush()

    mine = await client.get("/api/v1/me/event-requests", headers=auth(organiser))
    queue = await client.get(UNASSIGNED, headers=auth(lead))

    assert mine.json()["event_requests"][0]["coordinator"]["id"] == str(coordinator.id)  # AC 9
    assert queue.json()["event_requests"] == []

