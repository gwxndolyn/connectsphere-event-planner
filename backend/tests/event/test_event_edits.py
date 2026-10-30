"""US12 (SCRUM-15): the assigned coordinator edits an event in planning. See docs/testing/US12-edit-event.md."""

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import (
    ChangeRequestStatus,
    Event,
    EventAuditEntry,
    EventChangeRequest,
    EventStatus,
)
from app.seed import PLANNING_EVENT, seed, seed_id
from app.user.models import User, UserRole
from tests.event.test_event_request_clarification_api import auth
from tests.factories import NOW, make_event, make_user

pytestmark = pytest.mark.anyio


@pytest.fixture
def coordinator(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.full_name = "Casey Tan"
    db.flush()
    return user


def planning_event(db: Session, coordinator: User | None, status: EventStatus = EventStatus.PLANNING) -> Event:
    event = make_event(
        db,
        name="Design Thinking Lab",
        status=status,
        registration_enabled=False,
        start_at=NOW + timedelta(days=14),
        capacity=80,
        coordinator_id=coordinator.id if coordinator else None,
    )
    event.event_category = "Workshop"
    event.purpose = "Hands-on design practice"
    event.expected_attendees = 60
    event.room_layout_preference = "Classroom"
    db.flush()
    return event


def url(event: Event | uuid.UUID, suffix: str = "") -> str:
    event_id = event.id if isinstance(event, Event) else event
    return f"/api/v1/events/{event_id}{suffix}"


def audit_count(db: Session, event: Event) -> int:
    return db.scalar(select(func.count()).select_from(EventAuditEntry).where(EventAuditEntry.event_id == event.id))


def change_request_count(db: Session, event: Event) -> int:
    return db.scalar(select(func.count()).select_from(EventChangeRequest).where(EventChangeRequest.event_id == event.id))


# --- AC 1: Edit is enabled only in planning ---


async def test_tc_us12_01_a_planning_event_is_editable_for_its_coordinator(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)

    response = await client.get(url(event), headers=auth(coordinator))

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["editable"], body["name"]) == ("planning", True, "Design Thinking Lab")
    assert body["pending_change_requests"] == []


@pytest.mark.parametrize("status", [EventStatus.CONFIRMED, EventStatus.CANCELLED, EventStatus.COMPLETED])
async def test_tc_us12_02_other_statuses_are_not_editable_and_refuse_a_save(
    client: AsyncClient, db: Session, coordinator: User, status: EventStatus
) -> None:
    event = planning_event(db, coordinator, status)

    details = await client.get(url(event), headers=auth(coordinator))
    saved = await client.patch(url(event), headers=auth(coordinator), json={"purpose": "Changed"})

    assert details.json()["editable"] is False
    assert (saved.status_code, saved.json()) == (409, {"code": "EVENT_NOT_EDITABLE", "status": status.value})
    db.refresh(event)
    assert event.purpose == "Hands-on design practice"
    assert audit_count(db, event) == 0


async def test_tc_us12_03_the_coordinator_lists_their_events_with_whether_each_is_editable(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    planning = planning_event(db, coordinator)
    confirmed = planning_event(db, coordinator, EventStatus.CONFIRMED)
    confirmed.start_at = NOW + timedelta(days=20)
    confirmed.end_at = confirmed.start_at + timedelta(hours=2)
    planning_event(db, make_user(db, UserRole.COORDINATOR))  # someone else's
    db.flush()

    response = await client.get("/api/v1/me/coordinated-events", headers=auth(coordinator))

    assert response.status_code == 200
    assert [(row["id"], row["editable"]) for row in response.json()["events"]] == [
        (str(planning.id), True),
        (str(confirmed.id), False),
    ]


async def test_tc_us12_04_only_the_assigned_coordinator_reaches_the_event(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)
    other = make_user(db, UserRole.COORDINATOR)
    unassigned = planning_event(db, None)

    for path in (url(event), url(event, "/history")):
        response = await client.get(path, headers=auth(other))
        assert (response.status_code, response.json()) == (404, {"code": "NOT_FOUND"})
    saved = await client.patch(url(event), headers=auth(other), json={"purpose": "Changed"})
    assert saved.status_code == 404
    assert (await client.get(url(unassigned), headers=auth(coordinator))).status_code == 404
    assert (await client.get(url(uuid.uuid4()), headers=auth(coordinator))).status_code == 404


async def test_tc_us12_05_an_event_still_at_the_request_stage_is_not_found(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    """Approved requests are the request routes' (D11); this screen starts at planning."""
    event = planning_event(db, coordinator)
    event.status = EventStatus.APPROVED
    db.flush()

    assert (await client.get(url(event), headers=auth(coordinator))).status_code == 404


# --- AC 2: non-critical fields save at once ---


async def test_tc_us12_06_non_critical_fields_save_immediately(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)

    response = await client.patch(
        url(event),
        headers=auth(coordinator),
        json={"purpose": "Hands-on design practice, with prototypes", "equipment_needs": "Sticky notes"},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["outcome"], body["change_request"]) == ("saved", None)
    assert body["message"] == "Your changes are saved."
    assert body["event"]["purpose"] == "Hands-on design practice, with prototypes"
    assert body["event"]["equipment_needs"] == "Sticky notes"
    assert body["event"]["status"] == "planning"
    db.refresh(event)
    assert (event.purpose, event.equipment_needs, event.status) == (
        "Hands-on design practice, with prototypes",
        "Sticky notes",
        EventStatus.PLANNING,
    )
    assert change_request_count(db, event) == 0
    # The new values are what the next read returns (AC 2: "appear on the event record immediately").
    assert (await client.get(url(event), headers=auth(coordinator))).json()["purpose"] == event.purpose


async def test_tc_us12_07_an_optional_field_can_be_cleared(client: AsyncClient, db: Session, coordinator: User) -> None:
    event = planning_event(db, coordinator)

    response = await client.patch(url(event), headers=auth(coordinator), json={"room_layout_preference": "  "})

    assert response.status_code == 200
    db.refresh(event)
    assert event.room_layout_preference is None


async def test_tc_us12_08_sending_the_current_values_saves_nothing_and_logs_nothing(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)

    response = await client.patch(
        url(event), headers=auth(coordinator), json={"purpose": "Hands-on design practice", "capacity": 80}
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "saved"
    assert response.json()["message"] == "Nothing changed, so nothing was saved."
    assert (audit_count(db, event), change_request_count(db, event)) == (0, 0)


# --- AC 3: a critical field goes for approval ---


async def test_tc_us12_09_a_critical_change_creates_a_pending_change_request(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)
    old_start, old_end = event.start_at, event.end_at
    new_start = (old_start + timedelta(days=1)).isoformat()
    new_end = (old_end + timedelta(days=1)).isoformat()

    response = await client.patch(
        url(event), headers=auth(coordinator), json={"start_at": new_start, "end_at": new_end, "capacity": 100}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["outcome"] == "pending_approval"
    assert body["message"] == (
        "Your change to start time, end time, capacity is awaiting approval. "
        "The event keeps its current details until then."
    )
    request = body["change_request"]
    assert request["status"] == "pending_approval"
    assert request["requested_by"] == {"id": str(coordinator.id), "name": "Casey Tan"}
    assert request["changes"] == [
        {"field": "start_at", "old_value": old_start.isoformat(), "new_value": new_start},
        {"field": "end_at", "old_value": old_end.isoformat(), "new_value": new_end},
        {"field": "capacity", "old_value": 80, "new_value": 100},
    ]
    # The event keeps its previous values, and its details show the pending request.
    db.refresh(event)
    assert (event.start_at, event.end_at, event.capacity, event.status) == (old_start, old_end, 80, EventStatus.PLANNING)
    assert body["event"]["capacity"] == 80
    assert [r["id"] for r in body["event"]["pending_change_requests"]] == [request["id"]]
    stored = db.get(EventChangeRequest, uuid.UUID(request["id"]))
    assert (stored.status, stored.requested_by_user_id) == (ChangeRequestStatus.PENDING_APPROVAL, coordinator.id)


async def test_tc_us12_10_a_mixed_save_sends_every_changed_field_for_approval(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    """D57: one critical field holds the whole edit, so the event keeps every previous value (AC 3)."""
    event = planning_event(db, coordinator)

    response = await client.patch(
        url(event), headers=auth(coordinator), json={"purpose": "New purpose", "expected_attendees": 70}
    )

    assert response.status_code == 202
    assert response.json()["change_request"]["changes"] == [
        {"field": "purpose", "old_value": "Hands-on design practice", "new_value": "New purpose"},
        {"field": "expected_attendees", "old_value": 60, "new_value": 70},
    ]
    assert response.json()["message"].startswith("Your change to expected attendance is awaiting approval.")
    db.refresh(event)
    assert (event.purpose, event.expected_attendees) == ("Hands-on design practice", 60)


@pytest.mark.parametrize(
    ("field", "value"),
    [("start_at", None), ("end_at", None), ("capacity", 120), ("expected_attendees", 75), ("delivery_mode", "online")],
)
async def test_tc_us12_11_each_critical_field_goes_for_approval(
    client: AsyncClient, db: Session, coordinator: User, field: str, value: object
) -> None:
    event = planning_event(db, coordinator)
    if field == "start_at":
        value = (event.start_at - timedelta(hours=1)).isoformat()
    if field == "end_at":
        value = (event.end_at + timedelta(hours=1)).isoformat()

    response = await client.patch(url(event), headers=auth(coordinator), json={field: value})

    assert response.status_code == 202
    assert [change["field"] for change in response.json()["change_request"]["changes"]] == [field]


# --- AC 4: validation writes nothing and names the field ---


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ({"name": "   "}, "name", "Event name is required."),
        ({"purpose": None}, "purpose", "Purpose is required."),
        ({"capacity": 0}, "capacity", "Capacity must be a whole number of at least 1."),
        ({"expected_attendees": -5}, "expected_attendees", "Expected attendance must be a whole number of at least 1."),
        ({"expected_attendees": 1.5}, "expected_attendees", "Expected attendance must be a whole number of at least 1."),
        ({"expected_attendees": "lots"}, "expected_attendees", "Expected attendance must be a whole number of at least 1."),
        ({"expected_attendees": True}, "expected_attendees", "Expected attendance must be a whole number of at least 1."),
        ({"delivery_mode": "hybrid"}, "delivery_mode", "Delivery mode must be in person or online."),
        ({"start_at": "2026-10-20T10:00:00"}, "start_at", "Start time must be a date and time with its timezone offset."),
        ({"event_category": "x" * 101}, "event_category", "Category must be at most 100 characters."),
    ],
)
async def test_tc_us12_12_an_invalid_value_is_refused_and_named(
    client: AsyncClient, db: Session, coordinator: User, body: dict, field: str, message: str
) -> None:
    event = planning_event(db, coordinator)

    response = await client.patch(url(event), headers=auth(coordinator), json={"equipment_needs": "Laptops", **body})

    assert response.status_code == 422
    assert response.json() == {"code": "INVALID_EVENT_EDIT", "fields": [field], "errors": {field: message}}
    db.refresh(event)
    # Nothing written: not the valid field sent alongside, not the audit log, not a change request.
    assert event.equipment_needs is None
    assert (audit_count(db, event), change_request_count(db, event)) == (0, 0)


async def test_tc_us12_13_an_end_before_the_start_is_refused_on_the_end(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)

    end_first = await client.patch(
        url(event), headers=auth(coordinator), json={"end_at": (event.start_at - timedelta(hours=1)).isoformat()}
    )
    start_late = await client.patch(
        url(event), headers=auth(coordinator), json={"start_at": (event.end_at + timedelta(hours=1)).isoformat()}
    )

    assert end_first.json() == {
        "code": "INVALID_EVENT_EDIT",
        "fields": ["end_at"],
        "errors": {"end_at": "End time must be after the start time."},
    }
    assert start_late.json()["fields"] == ["start_at"]
    assert (audit_count(db, event), change_request_count(db, event)) == (0, 0)


async def test_tc_us12_14_every_invalid_field_is_named_at_once(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)

    response = await client.patch(
        url(event), headers=auth(coordinator), json={"join_link": "x", "capacity": -1, "name": ""}
    )

    assert response.json()["fields"] == ["name", "capacity"]


async def test_tc_us12_15_unknown_fields_and_status_are_refused(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)

    for body in ({"status": "confirmed"}, {"venue_name": "Somewhere else"}):
        response = await client.patch(url(event), headers=auth(coordinator), json=body)
        assert response.status_code == 422
    db.refresh(event)
    assert (event.status, event.venue_name) == (EventStatus.PLANNING, "SMU SCIS Building")


# --- AC 5: every successful save is in History, newest first ---


async def test_tc_us12_16_a_save_writes_one_audit_entry_per_changed_field(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    event = planning_event(db, coordinator)

    await client.patch(
        url(event),
        headers=auth(coordinator),
        json={"purpose": "Hands-on design practice", "room_layout_preference": "Cabaret", "equipment_needs": "Pens"},
    )

    entries = db.scalars(select(EventAuditEntry).where(EventAuditEntry.event_id == event.id).order_by(EventAuditEntry.seq)).all()
    # The unchanged purpose isn't logged.
    assert [(e.user_id, e.field_name, e.previous_value, e.new_value, e.created_at) for e in entries] == [
        (coordinator.id, "room_layout_preference", "Classroom", "Cabaret", NOW),
        (coordinator.id, "equipment_needs", None, "Pens", NOW),
    ]
    assert all(e.change_request_id is None for e in entries)


async def test_tc_us12_17_a_critical_save_is_logged_against_its_change_request(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    """D58: a save that creates a change request succeeded too, so its fields are logged, tied to it."""
    event = planning_event(db, coordinator)

    response = await client.patch(url(event), headers=auth(coordinator), json={"capacity": 90})

    entry = db.scalars(select(EventAuditEntry).where(EventAuditEntry.event_id == event.id)).one()
    assert (entry.field_name, entry.previous_value, entry.new_value) == ("capacity", 80, 90)
    assert str(entry.change_request_id) == response.json()["change_request"]["id"]


async def test_tc_us12_18_history_lists_entries_newest_first(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    from app.core.clock import get_now
    from app.main import app

    event = planning_event(db, coordinator)
    await client.patch(url(event), headers=auth(coordinator), json={"purpose": "First", "equipment_needs": "Pens"})
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=5)
    await client.patch(url(event), headers=auth(coordinator), json={"capacity": 90})

    response = await client.get(url(event, "/history"), headers=auth(coordinator))

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert [(e["field"], e["previous_value"], e["new_value"]) for e in entries] == [
        ("capacity", 80, 90),
        ("equipment_needs", None, "Pens"),
        ("purpose", "Hands-on design practice", "First"),
    ]
    assert entries[0]["change_request_status"] == "pending_approval"
    assert entries[1]["change_request_id"] is None
    assert entries[0]["user"] == {"id": str(coordinator.id), "name": "Casey Tan"}
    assert entries[0]["created_at"] > entries[1]["created_at"]


async def test_tc_us12_19_history_is_append_only_in_the_schema(db: Session, coordinator: User) -> None:
    event = planning_event(db, coordinator)
    db.add(EventChangeRequest(event_id=event.id, requested_by_user_id=coordinator.id, changes=[]))
    with pytest.raises(IntegrityError):
        db.flush()


def test_tc_us12_20_seed_has_a_planning_event_for_the_coordinator(db: Session) -> None:
    seed(db, now=NOW)

    event = db.get(Event, seed_id("event", PLANNING_EVENT.slug))
    assert (event.name, event.status, event.registration_enabled) == ("Event Planning Demo", EventStatus.PLANNING, False)
    assert event.coordinator_id == seed_id("user", "event-coordinator")
    assert event.expected_attendees == 60


def test_tc_us12_20_reseeding_resets_the_planning_event(db: Session) -> None:
    seed(db, now=NOW)
    event = db.get(Event, seed_id("event", PLANNING_EVENT.slug))
    coordinator = db.get(User, seed_id("user", "event-coordinator"))
    event.purpose = "Edited in the app"
    request = EventChangeRequest(
        event_id=event.id, requested_by_user_id=coordinator.id, changes=[{"field": "capacity", "old_value": 80, "new_value": 90}]
    )
    db.add(request)
    db.flush()
    db.add(EventAuditEntry(event_id=event.id, user_id=coordinator.id, field_name="capacity", previous_value=80, new_value=90, change_request_id=request.id))
    db.flush()

    seed(db, now=NOW)

    db.refresh(event)
    assert event.purpose == "Seeded for editing an event in planning (US12)"
    assert (audit_count(db, event), change_request_count(db, event)) == (0, 0)


def test_tc_us12_19_schema_has_rls_on_both_tables(db: Session) -> None:
    from sqlalchemy import text

    for table in ("event_change_requests", "event_audit_entries"):
        assert db.scalar(text(f"select relrowsecurity from pg_class where oid = '{table}'::regclass")) is True
