"""US26 equipment requests, PR 2 (SCRUM-109, story SCRUM-94): the catalogue, a coordinator's lines,
Tech Support's queue and review, and the coordinator's notice. The tables are PR 1's
(test_equipment_schema.py); see docs/testing/US26-equipment-requests.md."""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentType
from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user

pytestmark = pytest.mark.anyio

TYPES_URL = "/api/v1/equipment-types"
QUEUE_URL = "/api/v1/equipment-lines"
# Every status that isn't eligible and isn't a draft (a draft is 404, D11).
NOT_ELIGIBLE = [
    EventStatus.SUBMITTED,
    EventStatus.UNDER_REVIEW,
    EventStatus.AWAITING_CLARIFICATION,
    EventStatus.APPROVED,
    EventStatus.REJECTED,
    EventStatus.CANCELLED,
    EventStatus.COMPLETED,
]
REVIEWED = [EquipmentLineStatus.APPROVED, EquipmentLineStatus.REJECTED]


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def lines_url(event_id: uuid.UUID) -> str:
    return f"/api/v1/events/{event_id}/equipment-lines"


def line_url(line_id: uuid.UUID) -> str:
    return f"/api/v1/equipment-lines/{line_id}"


def review_url(line_id: uuid.UUID) -> str:
    return f"/api/v1/equipment-lines/{line_id}/review"


def when(value: str) -> datetime:
    return datetime.fromisoformat(value)


def make_type(db: Session, name: str | None = None) -> EquipmentType:
    equipment_type = EquipmentType(name=name or f"Test type {uuid.uuid4().hex[:8]}")
    db.add(equipment_type)
    db.flush()
    return equipment_type


def make_line(
    db: Session,
    *,
    event: Event,
    equipment_type: EquipmentType,
    requested_by: User,
    status: EquipmentLineStatus = EquipmentLineStatus.PENDING,
    reviewer: User | None = None,
    **overrides: object,
) -> EquipmentRequestLine:
    fields: dict[str, object] = {
        "event_id": event.id,
        "equipment_type_id": equipment_type.id,
        "quantity": 2,
        "notes": "Front of the room",
        "requested_by_user_id": requested_by.id,
        "status": status,
    }
    if status != EquipmentLineStatus.PENDING:
        # equipment_request_lines_reviewed_consistent: a reviewed line has its reviewer and time.
        reviewer = reviewer or make_user(db, UserRole.TECH_SUPPORT)
        fields |= {"reviewed_by_user_id": reviewer.id, "reviewed_at": NOW - timedelta(hours=1)}
    line = EquipmentRequestLine(**(fields | overrides))
    db.add(line)
    db.flush()
    return line


def line_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(EquipmentRequestLine))


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def tech(db: Session) -> User:
    return make_user(db, UserRole.TECH_SUPPORT)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    # Assigned to `coordinator`: only the event's assigned coordinator manages its equipment (AC 1, D20).
    return make_event(db, name="Data Science Summit", status=EventStatus.CONFIRMED, coordinator_id=coordinator.id)


@pytest.fixture
def projector(db: Session) -> EquipmentType:
    return make_type(db, "Projector")


@pytest.fixture
def microphone(db: Session) -> EquipmentType:
    return make_type(db, "Wireless microphone")


@pytest.fixture
def line(db: Session, event: Event, projector: EquipmentType, coordinator: User) -> EquipmentRequestLine:
    return make_line(db, event=event, equipment_type=projector, requested_by=coordinator)


# --- TC-US26-06 a coordinator adds lines ---


async def test_tc_us26_06_coordinator_adds_a_line_to_a_confirmed_event(
    client: AsyncClient, db: Session, coordinator: User, event: Event, projector: EquipmentType
) -> None:
    response = await client.post(
        lines_url(event.id),
        headers=auth(coordinator),
        json={"equipment_type_id": str(projector.id), "quantity": 2, "notes": "  HDMI, front of the room.  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["event"]["id"] == str(event.id)
    assert body["event"]["name"] == "Data Science Summit"
    assert body["equipment_type"] == {"id": str(projector.id), "name": "Projector"}
    assert body["quantity"] == 2
    assert body["notes"] == "HDMI, front of the room."
    assert body["status"] == "pending"
    assert body["requested_by_user_id"] == str(coordinator.id)
    assert (body["review_note"], body["reviewed_by_user_id"], body["reviewed_at"]) == (None, None, None)
    stored = db.get(EquipmentRequestLine, uuid.UUID(body["id"]))
    assert stored.status == EquipmentLineStatus.PENDING
    assert stored.requested_by_user_id == coordinator.id
    assert (stored.event_id, stored.equipment_type_id, stored.quantity) == (event.id, projector.id, 2)


async def test_tc_us26_06_a_planning_event_takes_lines_too(
    client: AsyncClient, db: Session, coordinator: User, projector: EquipmentType
) -> None:
    planning = make_event(db, status=EventStatus.PLANNING, coordinator_id=coordinator.id)

    response = await client.post(
        lines_url(planning.id), headers=auth(coordinator), json={"equipment_type_id": str(projector.id), "quantity": 1}
    )

    assert response.status_code == 201


@pytest.mark.parametrize("notes", [None, "   "], ids=["no notes", "blank notes"])
async def test_tc_us26_06_notes_are_optional(
    client: AsyncClient, coordinator: User, event: Event, projector: EquipmentType, notes: str | None
) -> None:
    body: dict[str, object] = {"equipment_type_id": str(projector.id), "quantity": 1}
    if notes is not None:
        body["notes"] = notes

    response = await client.post(lines_url(event.id), headers=auth(coordinator), json=body)

    assert response.status_code == 201
    assert response.json()["notes"] is None


async def test_tc_us26_06_the_coordinator_sees_every_line_of_the_event_oldest_first(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    projector: EquipmentType,
    microphone: EquipmentType,
) -> None:
    speaker = make_type(db, "Speaker")
    newest = make_line(db, event=event, equipment_type=projector, requested_by=coordinator, created_at=NOW)
    oldest = make_line(
        db,
        event=event,
        equipment_type=microphone,
        requested_by=coordinator,
        status=EquipmentLineStatus.APPROVED,
        created_at=NOW - timedelta(days=2),
    )
    middle = make_line(
        db,
        event=event,
        equipment_type=speaker,
        requested_by=coordinator,
        status=EquipmentLineStatus.REJECTED,
        created_at=NOW - timedelta(days=1),
    )
    other_event = make_event(db, coordinator_id=coordinator.id)
    make_line(db, event=other_event, equipment_type=projector, requested_by=coordinator)

    response = await client.get(lines_url(event.id), headers=auth(coordinator))

    assert response.status_code == 200
    lines = response.json()["lines"]
    assert [item["id"] for item in lines] == [str(oldest.id), str(middle.id), str(newest.id)]
    assert [item["status"] for item in lines] == ["approved", "rejected", "pending"]


# --- TC-US26-07 quantity and type are checked ---


async def test_tc_us26_07_the_catalogue_lists_every_type_by_name(
    client: AsyncClient, coordinator: User, projector: EquipmentType, microphone: EquipmentType, db: Session
) -> None:
    laptop = make_type(db, "Laptop")

    response = await client.get(TYPES_URL, headers=auth(coordinator))

    assert response.status_code == 200
    assert response.json()["equipment_types"] == [
        {"id": str(laptop.id), "name": "Laptop"},
        {"id": str(projector.id), "name": "Projector"},
        {"id": str(microphone.id), "name": "Wireless microphone"},
    ]


@pytest.mark.parametrize(
    ("overrides", "fields"),
    [
        ({"quantity": 0}, ["quantity"]),
        ({"quantity": -1}, ["quantity"]),
        ({"quantity": 1.5}, ["quantity"]),
        ({"quantity": "two"}, ["quantity"]),
        ({"quantity": None}, ["quantity"]),
        ({"equipment_type_id": str(uuid.UUID(int=1))}, ["equipment_type_id"]),
        ({"equipment_type_id": "projector"}, ["equipment_type_id"]),
        ({"equipment_type_id": None}, ["equipment_type_id"]),
        ({"equipment_type_id": str(uuid.UUID(int=1)), "quantity": 0}, ["equipment_type_id", "quantity"]),
    ],
    ids=[
        "zero",
        "negative",
        "not a whole number",
        "not a number",
        "no quantity",
        "unknown type",
        "type not an id",
        "no type",
        "both at once",
    ],
)
async def test_tc_us26_07_invalid_lines_are_refused(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    projector: EquipmentType,
    overrides: dict[str, object],
    fields: list[str],
) -> None:
    body = {"equipment_type_id": str(projector.id), "quantity": 2} | overrides
    body = {key: value for key, value in body.items() if value is not None}

    response = await client.post(lines_url(event.id), headers=auth(coordinator), json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_EQUIPMENT_LINE"
    assert response.json()["fields"] == fields
    assert set(response.json()["errors"]) == set(fields)
    assert line_count(db) == 0


@pytest.mark.parametrize(
    ("change", "field"),
    [({"quantity": 0}, "quantity"), ({"equipment_type_id": str(uuid.UUID(int=1))}, "equipment_type_id")],
    ids=["zero quantity", "unknown type"],
)
async def test_tc_us26_07_an_invalid_edit_is_refused(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    line: EquipmentRequestLine,
    projector: EquipmentType,
    change: dict[str, object],
    field: str,
) -> None:
    response = await client.patch(line_url(line.id), headers=auth(coordinator), json=change)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_EQUIPMENT_LINE"
    assert response.json()["fields"] == [field]
    db.refresh(line)
    assert (line.quantity, line.equipment_type_id) == (2, projector.id)


async def test_tc_us26_07_a_coordinator_cannot_set_review_fields(
    client: AsyncClient, db: Session, coordinator: User, event: Event, projector: EquipmentType, line: EquipmentRequestLine
) -> None:
    """Unknown fields are refused, so a coordinator can't send a line's status or review (AC 3)."""
    added = await client.post(
        lines_url(event.id),
        headers=auth(coordinator),
        json={"equipment_type_id": str(make_type(db).id), "quantity": 1, "status": "approved"},
    )
    edited = await client.patch(line_url(line.id), headers=auth(coordinator), json={"status": "approved"})

    assert (added.status_code, edited.status_code) == (422, 422)
    assert line_count(db) == 1
    db.refresh(line)
    assert line.status == EquipmentLineStatus.PENDING


# --- TC-US26-08 edit or remove a pending line ---


async def test_tc_us26_08_coordinator_edits_a_pending_line(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    line: EquipmentRequestLine,
    microphone: EquipmentType,
) -> None:
    response = await client.patch(
        line_url(line.id),
        headers=auth(coordinator),
        json={"equipment_type_id": str(microphone.id), "quantity": 4, "notes": "  Two for the panel.  "},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["equipment_type"] == {"id": str(microphone.id), "name": "Wireless microphone"}
    assert (body["quantity"], body["notes"], body["status"]) == (4, "Two for the panel.", "pending")
    db.refresh(line)
    assert (line.equipment_type_id, line.quantity, line.notes) == (microphone.id, 4, "Two for the panel.")


async def test_tc_us26_08_an_edit_changes_only_what_it_sends(
    client: AsyncClient, db: Session, coordinator: User, line: EquipmentRequestLine, projector: EquipmentType
) -> None:
    response = await client.patch(line_url(line.id), headers=auth(coordinator), json={"quantity": 3})

    assert response.status_code == 200
    db.refresh(line)
    assert (line.equipment_type_id, line.quantity, line.notes) == (projector.id, 3, "Front of the room")


async def test_tc_us26_08_coordinator_removes_a_pending_line(
    client: AsyncClient, db: Session, coordinator: User, line: EquipmentRequestLine
) -> None:
    response = await client.delete(line_url(line.id), headers=auth(coordinator))

    assert response.status_code == 204
    db.expire_all()
    assert db.get(EquipmentRequestLine, line.id) is None


async def test_tc_us26_08_the_events_coordinator_manages_a_line_another_coordinator_asked_for(
    client: AsyncClient, db: Session, coordinator: User, event: Event, projector: EquipmentType
) -> None:
    """The event's assigned coordinator manages all of its lines, whoever added them (AC 1: "an event
    they manage"), e.g. after the event is reassigned."""
    previous = make_user(db, UserRole.COORDINATOR)
    line = make_line(db, event=event, equipment_type=projector, requested_by=previous)

    response = await client.patch(line_url(line.id), headers=auth(coordinator), json={"quantity": 5})

    assert response.status_code == 200
    db.refresh(line)
    assert (line.quantity, line.requested_by_user_id) == (5, previous.id)


# --- TC-US26-09 a reviewed line is final ---


@pytest.mark.parametrize("status", REVIEWED)
async def test_tc_us26_09_a_reviewed_line_cannot_be_edited(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    projector: EquipmentType,
    status: EquipmentLineStatus,
) -> None:
    line = make_line(db, event=event, equipment_type=projector, requested_by=coordinator, status=status)

    response = await client.patch(line_url(line.id), headers=auth(coordinator), json={"quantity": 9})

    assert response.status_code == 409
    assert response.json()["code"] == "LINE_NOT_PENDING"
    assert response.json()["status"] == status.value
    db.refresh(line)
    assert (line.quantity, line.status) == (2, status)


@pytest.mark.parametrize("status", REVIEWED)
async def test_tc_us26_09_a_reviewed_line_cannot_be_removed(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    projector: EquipmentType,
    status: EquipmentLineStatus,
) -> None:
    line = make_line(db, event=event, equipment_type=projector, requested_by=coordinator, status=status)

    response = await client.delete(line_url(line.id), headers=auth(coordinator))

    assert response.status_code == 409
    assert response.json()["code"] == "LINE_NOT_PENDING"
    db.expire_all()
    assert db.get(EquipmentRequestLine, line.id) is not None


# --- TC-US26-10 only planning or confirmed events ---


@pytest.mark.parametrize("status", NOT_ELIGIBLE)
async def test_tc_us26_10_other_statuses_are_not_eligible(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    projector: EquipmentType,
    status: EventStatus,
) -> None:
    event = make_event(db, status=status, coordinator_id=coordinator.id)

    response = await client.post(
        lines_url(event.id), headers=auth(coordinator), json={"equipment_type_id": str(projector.id), "quantity": 1}
    )

    assert response.status_code == 409
    assert response.json() == {"code": "EVENT_NOT_ELIGIBLE", "status": status.value}
    assert line_count(db) == 0


async def test_tc_us26_10_a_draft_or_unknown_event_is_not_found(
    client: AsyncClient, db: Session, coordinator: User, projector: EquipmentType
) -> None:
    """A draft is owner-only (D11), so it's 404 like an unknown event, never 409."""
    draft = make_event(db, status=EventStatus.DRAFT, coordinator_id=coordinator.id)
    body = {"equipment_type_id": str(projector.id), "quantity": 1}

    for event_id in (draft.id, uuid.uuid4()):
        added = await client.post(lines_url(event_id), headers=auth(coordinator), json=body)
        listed = await client.get(lines_url(event_id), headers=auth(coordinator))
        assert (added.status_code, listed.status_code) == (404, 404)
        assert added.json() == {"code": "NOT_FOUND"}
    assert line_count(db) == 0


async def test_tc_us26_10_an_unknown_line_is_not_found(client: AsyncClient, coordinator: User, tech: User) -> None:
    unknown = uuid.uuid4()

    assert (await client.patch(line_url(unknown), headers=auth(coordinator), json={"quantity": 1})).status_code == 404
    assert (await client.delete(line_url(unknown), headers=auth(coordinator))).status_code == 404
    reviewed = await client.post(review_url(unknown), headers=auth(tech), json={"decision": "approved"})
    assert reviewed.status_code == 404


# --- TC-US26-11 Tech Support's queue ---


async def test_tc_us26_11_the_queue_holds_pending_lines_oldest_first(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    tech: User,
    event: Event,
    projector: EquipmentType,
    microphone: EquipmentType,
) -> None:
    other_event = make_event(db, name="Career Fair", status=EventStatus.PLANNING, coordinator_id=coordinator.id)
    newer = make_line(db, event=event, equipment_type=projector, requested_by=coordinator, created_at=NOW)
    older = make_line(
        db, event=other_event, equipment_type=microphone, requested_by=coordinator, created_at=NOW - timedelta(days=1)
    )
    make_line(db, event=event, equipment_type=microphone, requested_by=coordinator, status=EquipmentLineStatus.APPROVED)
    make_line(
        db, event=other_event, equipment_type=projector, requested_by=coordinator, status=EquipmentLineStatus.REJECTED
    )

    response = await client.get(QUEUE_URL, headers=auth(tech), params={"status": "pending"})

    assert response.status_code == 200
    lines = response.json()["lines"]
    assert [item["id"] for item in lines] == [str(older.id), str(newer.id)]
    assert [item["status"] for item in lines] == ["pending", "pending"]
    first = lines[0]
    assert (first["event"]["id"], first["event"]["name"]) == (str(other_event.id), "Career Fair")
    assert when(first["event"]["start_at"]) == other_event.start_at
    assert first["equipment_type"] == {"id": str(microphone.id), "name": "Wireless microphone"}
    assert (first["quantity"], first["notes"]) == (2, "Front of the room")


# --- TC-US26-12 Tech Support approves or rejects ---


@pytest.mark.parametrize("decision", ["approved", "rejected"])
async def test_tc_us26_12_tech_support_reviews_a_line_with_a_note(
    client: AsyncClient, db: Session, tech: User, line: EquipmentRequestLine, decision: str
) -> None:
    response = await client.post(
        review_url(line.id), headers=auth(tech), json={"decision": decision, "note": "  From the AV store.  "}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["review_note"]) == (decision, "From the AV store.")
    assert body["reviewed_by_user_id"] == str(tech.id)
    assert when(body["reviewed_at"]) == NOW
    assert body["quantity"] == 2
    db.refresh(line)
    assert (line.status, line.review_note, line.reviewed_by_user_id, line.reviewed_at) == (
        EquipmentLineStatus(decision),
        "From the AV store.",
        tech.id,
        NOW,
    )


@pytest.mark.parametrize("note", [None, "   "], ids=["no note", "blank note"])
async def test_tc_us26_12_the_note_is_optional(
    client: AsyncClient, db: Session, tech: User, line: EquipmentRequestLine, note: str | None
) -> None:
    """AC 3 says "with a note" but doesn't require one (D43, DECISION-PENDING)."""
    body: dict[str, object] = {"decision": "rejected"}
    if note is not None:
        body["note"] = note

    response = await client.post(review_url(line.id), headers=auth(tech), json=body)

    assert response.status_code == 200
    db.refresh(line)
    assert (line.status, line.review_note) == (EquipmentLineStatus.REJECTED, None)


@pytest.mark.parametrize("status", REVIEWED)
async def test_tc_us26_12_a_second_review_is_refused(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    tech: User,
    event: Event,
    projector: EquipmentType,
    status: EquipmentLineStatus,
) -> None:
    first_reviewer = make_user(db, UserRole.TECH_SUPPORT)
    line = make_line(
        db, event=event, equipment_type=projector, requested_by=coordinator, status=status, reviewer=first_reviewer
    )

    response = await client.post(review_url(line.id), headers=auth(tech), json={"decision": "approved", "note": "Again"})

    assert response.status_code == 409
    assert response.json()["code"] == "LINE_NOT_PENDING"
    assert response.json()["status"] == status.value
    db.refresh(line)
    assert (line.status, line.reviewed_by_user_id, line.review_note) == (status, first_reviewer.id, None)


@pytest.mark.parametrize("body", [{}, {"decision": "pending"}, {"decision": "maybe"}], ids=["none", "pending", "other"])
async def test_tc_us26_12_a_decision_must_be_approved_or_rejected(
    client: AsyncClient, db: Session, tech: User, line: EquipmentRequestLine, body: dict[str, object]
) -> None:
    response = await client.post(review_url(line.id), headers=auth(tech), json=body)

    assert response.status_code == 422
    db.refresh(line)
    assert line.status == EquipmentLineStatus.PENDING


# --- TC-US26-13 approval is always the full quantity ---


@pytest.mark.parametrize("quantity", [1, 2], ids=["less", "the same"])
async def test_tc_us26_13_a_review_cannot_carry_a_quantity(
    client: AsyncClient, db: Session, tech: User, line: EquipmentRequestLine, quantity: int
) -> None:
    response = await client.post(review_url(line.id), headers=auth(tech), json={"decision": "approved", "quantity": quantity})

    assert response.status_code == 422
    db.refresh(line)
    assert (line.status, line.quantity) == (EquipmentLineStatus.PENDING, 2)


# --- TC-US26-14 the requesting coordinator is notified ---


@pytest.mark.parametrize("decision", ["approved", "rejected"])
async def test_tc_us26_14_the_requesting_coordinator_is_notified(
    client: AsyncClient,
    db: Session,
    notifier: FakeNotifier,
    coordinator: User,
    tech: User,
    event: Event,
    projector: EquipmentType,
    decision: str,
) -> None:
    line = make_line(db, event=event, equipment_type=projector, requested_by=coordinator, quantity=3)

    await client.post(review_url(line.id), headers=auth(tech), json={"decision": decision, "note": "Only two in stock."})

    assert notifier.equipment_reviews == [
        {
            "email": coordinator.email,
            "line_id": line.id,
            "event_name": "Data Science Summit",
            "equipment_type": "Projector",
            "quantity": 3,
            "decision": decision,
            "note": "Only two in stock.",
        }
    ]


async def test_tc_us26_14_the_coordinator_who_asked_is_notified_after_a_reassignment(
    client: AsyncClient,
    db: Session,
    notifier: FakeNotifier,
    coordinator: User,
    tech: User,
    event: Event,
    projector: EquipmentType,
) -> None:
    previous = make_user(db, UserRole.COORDINATOR)
    line = make_line(db, event=event, equipment_type=projector, requested_by=previous)

    await client.post(review_url(line.id), headers=auth(tech), json={"decision": "approved"})

    assert [call["email"] for call in notifier.equipment_reviews] == [previous.email]
    assert notifier.equipment_reviews[0]["note"] is None


async def test_tc_us26_14_a_notifier_failure_keeps_the_review(
    client: AsyncClient, db: Session, notifier: FakeNotifier, tech: User, line: EquipmentRequestLine
) -> None:
    notifier.fail = True

    response = await client.post(review_url(line.id), headers=auth(tech), json={"decision": "approved"})

    assert response.status_code == 200
    db.refresh(line)
    assert line.status == EquipmentLineStatus.APPROVED


async def test_tc_us26_14_a_refused_review_notifies_nobody(
    client: AsyncClient,
    db: Session,
    notifier: FakeNotifier,
    coordinator: User,
    tech: User,
    event: Event,
    projector: EquipmentType,
    line: EquipmentRequestLine,
) -> None:
    reviewed = make_line(
        db, event=event, equipment_type=make_type(db), requested_by=coordinator, status=EquipmentLineStatus.APPROVED
    )

    assert (await client.post(review_url(reviewed.id), headers=auth(tech), json={"decision": "rejected"})).status_code == 409
    assert (
        await client.post(review_url(line.id), headers=auth(tech), json={"decision": "approved", "quantity": 1})
    ).status_code == 422

    assert notifier.equipment_reviews == []


# --- TC-US26-15 roles and identity ---


@pytest.mark.parametrize(
    "role",
    [UserRole.ORGANISER, UserRole.COORDINATOR_LEAD, UserRole.OPERATIONS_MANAGER, UserRole.ATTENDEE, UserRole.TECH_SUPPORT],
)
async def test_tc_us26_15_only_coordinators_manage_lines(
    client: AsyncClient, db: Session, event: Event, projector: EquipmentType, line: EquipmentRequestLine, role: UserRole
) -> None:
    user = make_user(db, role)
    body = {"equipment_type_id": str(make_type(db).id), "quantity": 1}

    for response in (
        await client.post(lines_url(event.id), headers=auth(user), json=body),
        await client.get(lines_url(event.id), headers=auth(user)),
        await client.patch(line_url(line.id), headers=auth(user), json={"quantity": 5}),
        await client.delete(line_url(line.id), headers=auth(user)),
    ):
        assert response.status_code == 403
        assert response.json() == {"code": "FORBIDDEN"}
    assert line_count(db) == 1
    db.refresh(line)
    assert line.quantity == 2


@pytest.mark.parametrize(
    "role",
    [UserRole.ORGANISER, UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD, UserRole.OPERATIONS_MANAGER, UserRole.ATTENDEE],
)
async def test_tc_us26_15_only_tech_support_opens_the_queue_and_reviews(
    client: AsyncClient, db: Session, line: EquipmentRequestLine, role: UserRole
) -> None:
    user = make_user(db, role)

    for response in (
        await client.get(QUEUE_URL, headers=auth(user), params={"status": "pending"}),
        await client.post(review_url(line.id), headers=auth(user), json={"decision": "approved"}),
    ):
        assert response.status_code == 403
        assert response.json() == {"code": "FORBIDDEN"}
    db.refresh(line)
    assert line.status == EquipmentLineStatus.PENDING


async def test_tc_us26_15_a_coordinator_not_assigned_to_the_event_is_not_found(
    client: AsyncClient, db: Session, event: Event, projector: EquipmentType, line: EquipmentRequestLine
) -> None:
    """Only the event's assigned coordinator manages its equipment (AC 1, D20); anyone else gets 404,
    as for venue bookings, so the event's lines aren't revealed."""
    other = make_user(db, UserRole.COORDINATOR)
    body = {"equipment_type_id": str(make_type(db).id), "quantity": 1}

    for response in (
        await client.post(lines_url(event.id), headers=auth(other), json=body),
        await client.get(lines_url(event.id), headers=auth(other)),
        await client.patch(line_url(line.id), headers=auth(other), json={"quantity": 5}),
        await client.delete(line_url(line.id), headers=auth(other)),
    ):
        assert response.status_code == 404
        assert response.json() == {"code": "NOT_FOUND"}
    assert line_count(db) == 1
    db.refresh(line)
    assert line.quantity == 2


async def test_tc_us26_15_an_unassigned_event_has_nobody_to_manage_it(
    client: AsyncClient, db: Session, coordinator: User, projector: EquipmentType
) -> None:
    unassigned = make_event(db, status=EventStatus.CONFIRMED)
    line = make_line(db, event=unassigned, equipment_type=projector, requested_by=coordinator)

    added = await client.post(
        lines_url(unassigned.id), headers=auth(coordinator), json={"equipment_type_id": str(make_type(db).id), "quantity": 1}
    )
    edited = await client.patch(line_url(line.id), headers=auth(coordinator), json={"quantity": 5})

    assert (added.status_code, edited.status_code) == (404, 404)
    assert line_count(db) == 1


async def test_tc_us26_15_an_inactive_coordinator_is_refused(
    client: AsyncClient, db: Session, projector: EquipmentType
) -> None:
    inactive = make_user(db, UserRole.COORDINATOR, active=False)
    event = make_event(db, coordinator_id=inactive.id)

    response = await client.post(
        lines_url(event.id), headers=auth(inactive), json={"equipment_type_id": str(projector.id), "quantity": 1}
    )

    assert response.status_code == 403
    assert line_count(db) == 0


@pytest.mark.parametrize("role", list(UserRole))
async def test_tc_us26_15_anyone_signed_in_reads_the_catalogue(
    client: AsyncClient, db: Session, projector: EquipmentType, role: UserRole
) -> None:
    response = await client.get(TYPES_URL, headers=auth(make_user(db, role)))

    assert response.status_code == 200


async def test_tc_us26_15_every_route_needs_an_identity(
    client: AsyncClient, event: Event, line: EquipmentRequestLine
) -> None:
    for method, url in (
        ("GET", TYPES_URL),
        ("GET", lines_url(event.id)),
        ("POST", lines_url(event.id)),
        ("PATCH", line_url(line.id)),
        ("DELETE", line_url(line.id)),
        ("GET", QUEUE_URL),
        ("POST", review_url(line.id)),
    ):
        response = await client.request(method, url, json={} if method in ("POST", "PATCH") else None)
        assert response.status_code == 401, f"{method} {url}"
        assert response.json()["code"] == "UNAUTHENTICATED"


# --- TC-US26-19 one live line per type per event (D41) ---


@pytest.mark.parametrize("status", [EquipmentLineStatus.PENDING, EquipmentLineStatus.APPROVED])
async def test_tc_us26_19_a_second_line_of_a_live_type_is_refused(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    projector: EquipmentType,
    status: EquipmentLineStatus,
) -> None:
    make_line(db, event=event, equipment_type=projector, requested_by=coordinator, status=status)

    response = await client.post(
        lines_url(event.id), headers=auth(coordinator), json={"equipment_type_id": str(projector.id), "quantity": 1}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_EQUIPMENT_TYPE"
    assert response.json()["fields"] == ["equipment_type_id"]
    assert line_count(db) == 1


async def test_tc_us26_19_a_rejected_type_can_be_asked_for_again(
    client: AsyncClient, db: Session, coordinator: User, event: Event, projector: EquipmentType
) -> None:
    make_line(db, event=event, equipment_type=projector, requested_by=coordinator, status=EquipmentLineStatus.REJECTED)

    response = await client.post(
        lines_url(event.id), headers=auth(coordinator), json={"equipment_type_id": str(projector.id), "quantity": 1}
    )

    assert response.status_code == 201
    assert line_count(db) == 2


async def test_tc_us26_19_another_event_or_type_is_not_a_duplicate(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    projector: EquipmentType,
    microphone: EquipmentType,
    line: EquipmentRequestLine,
) -> None:
    other_event = make_event(db, status=EventStatus.PLANNING, coordinator_id=coordinator.id)

    same_type_elsewhere = await client.post(
        lines_url(other_event.id), headers=auth(coordinator), json={"equipment_type_id": str(projector.id), "quantity": 1}
    )
    other_type_here = await client.post(
        lines_url(event.id), headers=auth(coordinator), json={"equipment_type_id": str(microphone.id), "quantity": 1}
    )

    assert (same_type_elsewhere.status_code, other_type_here.status_code) == (201, 201)


async def test_tc_us26_19_an_edit_to_a_live_type_is_refused(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    projector: EquipmentType,
    microphone: EquipmentType,
    line: EquipmentRequestLine,
) -> None:
    other = make_line(db, event=event, equipment_type=microphone, requested_by=coordinator)

    response = await client.patch(line_url(other.id), headers=auth(coordinator), json={"equipment_type_id": str(projector.id)})

    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_EQUIPMENT_TYPE"
    db.refresh(other)
    assert other.equipment_type_id == microphone.id


async def test_tc_us26_19_keeping_a_lines_own_type_is_not_a_duplicate(
    client: AsyncClient, db: Session, coordinator: User, projector: EquipmentType, line: EquipmentRequestLine
) -> None:
    response = await client.patch(
        line_url(line.id), headers=auth(coordinator), json={"equipment_type_id": str(projector.id), "quantity": 3}
    )

    assert response.status_code == 200
    db.refresh(line)
    assert line.quantity == 3


# --- TC-US26-20 a coordinator's events that take equipment (SCRUM-110) ---

MY_EVENTS_URL = "/api/v1/me/equipment-events"


async def test_tc_us26_20_a_coordinator_lists_their_events_upcoming_first_then_past(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    """Events not over yet come first, soonest first, then ended ones, most recent first (PR #78
    review), so last month's confirmed event isn't at the top. Ended ones stay listed: the API still
    takes lines for them (SCRUM-109's rule is status only)."""

    def mine(name: str, status: EventStatus, start: timedelta, hours: int = 2) -> Event:
        return make_event(
            db,
            name=name,
            status=status,
            start_at=NOW + start,
            end_at=NOW + start + timedelta(hours=hours),
            coordinator_id=coordinator.id,
        )

    later = mine("Career Fair", EventStatus.CONFIRMED, timedelta(days=20))
    sooner = mine("Data Science Summit", EventStatus.PLANNING, timedelta(days=5))
    # Under way: started an hour ago, ends in an hour, so not over yet.
    under_way = mine("Hackathon", EventStatus.CONFIRMED, timedelta(hours=-1))
    older = mine("Spring Showcase", EventStatus.CONFIRMED, timedelta(days=-30))
    recent = mine("Alumni Night", EventStatus.CONFIRMED, timedelta(days=-7))
    # Not listed: their events in any other status, someone else's, and unassigned ones.
    for status in [*NOT_ELIGIBLE, EventStatus.DRAFT]:
        make_event(db, status=status, coordinator_id=coordinator.id)
    make_event(db, status=EventStatus.CONFIRMED, coordinator_id=make_user(db, UserRole.COORDINATOR).id)
    make_event(db, status=EventStatus.CONFIRMED)

    response = await client.get(MY_EVENTS_URL, headers=auth(coordinator))

    assert response.status_code == 200
    events = response.json()["events"]
    assert [item["id"] for item in events] == [
        str(e.id) for e in (under_way, sooner, later, recent, older)
    ]
    assert (events[1]["name"], events[1]["status"]) == ("Data Science Summit", "planning")
    assert when(events[1]["start_at"]) == sooner.start_at
    assert (events[2]["name"], events[2]["status"]) == ("Career Fair", "confirmed")


async def test_tc_us26_20_a_coordinator_with_no_such_events_gets_an_empty_list(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)

    response = await client.get(MY_EVENTS_URL, headers=auth(coordinator))

    assert response.status_code == 200
    assert response.json() == {"events": []}


@pytest.mark.parametrize("role", [role for role in UserRole if role != UserRole.COORDINATOR])
async def test_tc_us26_20_only_coordinators_list_their_equipment_events(
    client: AsyncClient, db: Session, role: UserRole
) -> None:
    response = await client.get(MY_EVENTS_URL, headers=auth(make_user(db, role)))

    assert response.status_code == 403
    assert response.json() == {"code": "FORBIDDEN"}


async def test_tc_us26_20_the_list_needs_an_identity(client: AsyncClient) -> None:
    response = await client.get(MY_EVENTS_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
