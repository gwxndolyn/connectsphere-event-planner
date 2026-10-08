import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import Event, EventRequestClarification, EventStatus
from app.user.models import User, UserRole
from tests.factories import NOW, make_event

pytestmark = pytest.mark.anyio


def make_user(db: Session, role: UserRole, *, active: bool = True) -> User:
    user = User(email=f"{uuid.uuid4().hex}@smu.edu.sg", role=role, is_active=active)
    db.add(user)
    db.flush()
    return user


def make_request(db: Session, organiser: User, status: EventStatus = EventStatus.SUBMITTED) -> Event:
    event = Event(
        name="Community design workshop",
        status=status,
        registration_enabled=False,
        created_by_user_id=organiser.id,
        submitted_by_user_id=None if status == EventStatus.DRAFT else organiser.id,
        submitted_at=None if status == EventStatus.DRAFT else NOW - timedelta(days=1),
    )
    db.add(event)
    db.flush()
    return event


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


BODY = {"sections": ["attendance", "layout"], "comment": "How many people, and what layout?"}


async def send(client: AsyncClient, user: User | None, request_id: uuid.UUID, body: dict = BODY):
    headers = auth(user) if user else {}
    return await client.post(f"/api/v1/event-requests/{request_id}/clarifications", headers=headers, json=body)


def stored(db: Session, event: Event) -> list[EventRequestClarification]:
    return list(db.scalars(select(EventRequestClarification).where(EventRequestClarification.event_id == event.id)))


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.mark.parametrize("status", [EventStatus.SUBMITTED, EventStatus.UNDER_REVIEW])
async def test_tc_us8_09_coordinator_sends_from_submitted_or_under_review(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, status: EventStatus
) -> None:
    event = make_request(db, organiser, status)

    response = await send(client, coordinator, event.id)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "awaiting_clarification"
    assert body["clarification"]["round"] == 1
    assert body["clarification"]["kind"] == "request"
    assert body["clarification"]["sections"] == ["attendance", "layout"]
    assert body["clarification"]["author_user_id"] == str(coordinator.id)
    assert body["clarification"]["created_at"] == NOW.isoformat()


async def test_tc_us8_10_owner_sees_awaiting_clarification(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = make_request(db, organiser)
    await send(client, coordinator, event.id)

    response = await client.get(f"/api/v1/event-requests/{event.id}", headers=auth(organiser))

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_clarification"
    assert len(stored(db, event)) == 1


@pytest.mark.parametrize(
    "status", [EventStatus.AWAITING_CLARIFICATION, EventStatus.APPROVED, EventStatus.REJECTED]
)
async def test_tc_us8_11_refused_in_other_request_statuses(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, status: EventStatus
) -> None:
    event = make_request(db, organiser, status)

    response = await send(client, coordinator, event.id)

    assert response.status_code == 409
    assert response.json() == {"code": "CLARIFICATION_NOT_ALLOWED", "status": status.value}
    db.refresh(event)
    assert event.status == status
    assert stored(db, event) == []


async def test_tc_us8_12_drafts_events_and_unknown_ids_are_not_found(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    draft = make_request(db, organiser, EventStatus.DRAFT)
    confirmed = make_event(db)

    for request_id in (draft.id, confirmed.id, uuid.uuid4()):
        response = await send(client, coordinator, request_id)
        assert response.status_code == 404
        assert response.json() == {"code": "NOT_FOUND"}
    assert stored(db, draft) == [] and stored(db, confirmed) == []


async def test_tc_us8_13_only_active_coordinators_may_send(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    event = make_request(db, organiser)
    callers = {
        "no identity": (None, 401),
        "organiser": (organiser, 403),
        "operations manager": (make_user(db, UserRole.OPERATIONS_MANAGER), 403),
        "attendee": (make_user(db, UserRole.ATTENDEE), 403),
        "inactive coordinator": (make_user(db, UserRole.COORDINATOR, active=False), 403),
    }

    for caller, expected in callers.values():
        response = await send(client, caller, event.id)
        assert response.status_code == expected

    db.refresh(event)
    assert event.status == EventStatus.SUBMITTED
    assert stored(db, event) == []


async def test_tc_us8_14_invalid_body_leaves_the_request_unchanged(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = make_request(db, organiser)

    missing = await send(client, coordinator, event.id, {"sections": [], "comment": " "})
    unknown = await send(client, coordinator, event.id, {"sections": ["catering"], "comment": "Food?"})

    assert missing.status_code == 422
    assert missing.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": ["sections", "comment"]}
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "INVALID_CLARIFICATION"
    db.refresh(event)
    assert event.status == EventStatus.SUBMITTED
    assert stored(db, event) == []
