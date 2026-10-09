import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import ClarificationKind, Event, EventRequestClarification, EventStatus
from app.user.models import User, UserRole
from tests.factories import NOW

pytestmark = pytest.mark.anyio

QUESTION = {"sections": ["attendance"], "comment": "Is 40 the final headcount?"}
ANSWER = {"comment": "Yes, 40 including speakers."}


def make_user(db: Session, role: UserRole) -> User:
    user = User(email=f"{uuid.uuid4().hex}@smu.edu.sg", role=role)
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


def auth(user: User | None) -> dict[str, str]:
    return {"X-User-Id": str(user.id)} if user else {}


async def ask(client: AsyncClient, coordinator: User, event: Event):
    response = await client.post(
        f"/api/v1/event-requests/{event.id}/clarifications", headers=auth(coordinator), json=QUESTION
    )
    assert response.status_code == 201
    return response


async def answer(client: AsyncClient, user: User | None, event_id: uuid.UUID, body: dict = ANSWER):
    return await client.post(
        f"/api/v1/event-requests/{event_id}/clarifications/response", headers=auth(user), json=body
    )


async def thread(client: AsyncClient, user: User | None, event_id: uuid.UUID):
    return await client.get(f"/api/v1/event-requests/{event_id}/clarifications", headers=auth(user))


def responses(db: Session, event: Event) -> list[EventRequestClarification]:
    return list(
        db.scalars(
            select(EventRequestClarification).where(
                EventRequestClarification.event_id == event.id,
                EventRequestClarification.kind == ClarificationKind.RESPONSE,
            )
        )
    )


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
async def awaiting(client: AsyncClient, db: Session, organiser: User, coordinator: User) -> Event:
    event = make_request(db, organiser)
    await ask(client, coordinator, event)
    return event


async def test_tc_us8_17_owner_answers_and_the_request_returns_to_review(
    client: AsyncClient, db: Session, organiser: User, awaiting: Event
) -> None:
    response = await answer(client, organiser, awaiting.id, {"comment": "  Yes, 40 including speakers.  "})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "under_review"
    assert body["clarification"]["kind"] == "response"
    assert body["clarification"]["round"] == 1
    assert body["clarification"]["sections"] is None
    assert body["clarification"]["comment"] == "Yes, 40 including speakers."
    assert body["clarification"]["author_user_id"] == str(organiser.id)
    assert body["clarification"]["created_at"] == NOW.isoformat()
    db.refresh(awaiting)
    assert awaiting.status == EventStatus.UNDER_REVIEW


async def test_tc_us8_18_thread_shows_the_question_above_the_answer(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, awaiting: Event
) -> None:
    await answer(client, organiser, awaiting.id)

    for reader in (coordinator, organiser, make_user(db, UserRole.OPERATIONS_MANAGER)):
        response = await thread(client, reader, awaiting.id)
        assert response.status_code == 200
        messages = response.json()["clarifications"]
        assert [(m["round"], m["kind"]) for m in messages] == [(1, "request"), (1, "response")]
        assert messages[0]["comment"] == QUESTION["comment"]
        assert messages[1]["comment"] == ANSWER["comment"]


@pytest.mark.parametrize(
    "status", [EventStatus.SUBMITTED, EventStatus.UNDER_REVIEW, EventStatus.APPROVED, EventStatus.REJECTED]
)
async def test_tc_us8_19_only_an_open_clarification_can_be_answered(
    client: AsyncClient, db: Session, organiser: User, status: EventStatus
) -> None:
    event = make_request(db, organiser, status)

    response = await answer(client, organiser, event.id)

    assert response.status_code == 409
    assert response.json() == {"code": "NO_OPEN_CLARIFICATION", "status": status.value}
    db.refresh(event)
    assert event.status == status
    assert responses(db, event) == []


async def test_tc_us8_20_answering_twice_is_refused(
    client: AsyncClient, db: Session, organiser: User, awaiting: Event
) -> None:
    await answer(client, organiser, awaiting.id)

    again = await answer(client, organiser, awaiting.id)

    assert again.status_code == 409
    assert again.json() == {"code": "NO_OPEN_CLARIFICATION", "status": "under_review"}
    assert len(responses(db, awaiting)) == 1


async def test_tc_us8_21_only_the_owner_may_answer(
    client: AsyncClient, db: Session, coordinator: User, awaiting: Event
) -> None:
    cases = [
        (make_user(db, UserRole.ORGANISER), awaiting.id, 404),
        (coordinator, awaiting.id, 403),
        (None, awaiting.id, 401),
        (make_user(db, UserRole.ORGANISER), uuid.uuid4(), 404),
    ]

    for user, event_id, expected in cases:
        assert (await answer(client, user, event_id)).status_code == expected

    db.refresh(awaiting)
    assert awaiting.status == EventStatus.AWAITING_CLARIFICATION
    assert responses(db, awaiting) == []


async def test_tc_us8_22_blank_answer_leaves_the_request_waiting(
    client: AsyncClient, db: Session, organiser: User, awaiting: Event
) -> None:
    response = await answer(client, organiser, awaiting.id, {"comment": "   "})

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": ["comment"]}
    db.refresh(awaiting)
    assert awaiting.status == EventStatus.AWAITING_CLARIFICATION
    assert responses(db, awaiting) == []


async def test_tc_us8_23_after_an_answer_the_coordinator_can_ask_again(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, awaiting: Event
) -> None:
    await answer(client, organiser, awaiting.id)

    second = await ask(client, coordinator, awaiting)

    assert second.json()["clarification"]["round"] == 2
    assert second.json()["status"] == "awaiting_clarification"


async def test_tc_us8_24_thread_is_hidden_from_other_organisers_and_attendees(
    client: AsyncClient, db: Session, awaiting: Event
) -> None:
    for reader in (make_user(db, UserRole.ORGANISER), make_user(db, UserRole.ATTENDEE)):
        response = await thread(client, reader, awaiting.id)
        assert response.status_code == 404
        assert response.json() == {"code": "NOT_FOUND"}
    assert (await thread(client, None, awaiting.id)).status_code == 401


async def three_rounds(client: AsyncClient, organiser: User, coordinator: User, event: Event) -> list[dict]:
    """Question → reply → question → reply → question, each with its own comment (8d AC 1)."""
    sent = []
    for round in (1, 2, 3):
        question = await client.post(
            f"/api/v1/event-requests/{event.id}/clarifications",
            headers=auth(coordinator),
            json={"sections": ["attendance"], "comment": f"Question {round}"},
        )
        assert question.status_code == 201
        sent.append(question.json())
        if round < 3:
            reply = await answer(client, organiser, event.id, {"comment": f"Answer {round}"})
            assert reply.status_code == 201
            sent.append(reply.json())
    return sent


async def test_tc_us8_31_coordinator_can_ask_again_after_every_answer(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = make_request(db, organiser)

    sent = await three_rounds(client, organiser, coordinator, event)

    assert [(s["clarification"]["kind"], s["clarification"]["round"]) for s in sent] == [
        ("request", 1),
        ("response", 1),
        ("request", 2),
        ("response", 2),
        ("request", 3),
    ]
    assert [s["status"] for s in sent] == ["awaiting_clarification", "under_review"] * 2 + ["awaiting_clarification"]
    db.refresh(event)
    assert event.status == EventStatus.AWAITING_CLARIFICATION


async def test_tc_us8_32_thread_keeps_every_round_in_order(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = make_request(db, organiser)
    await three_rounds(client, organiser, coordinator, event)

    response = await thread(client, coordinator, event.id)

    assert response.status_code == 200
    assert [(m["round"], m["kind"], m["comment"]) for m in response.json()["clarifications"]] == [
        (1, "request", "Question 1"),
        (1, "response", "Answer 1"),
        (2, "request", "Question 2"),
        (2, "response", "Answer 2"),
        (3, "request", "Question 3"),
    ]
