"""US29a (SCRUM-97): an organiser requests a change to their own submitted event. See docs/testing/US29a-change-request.md."""

import uuid
from datetime import datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import ChangeRequestStatus, DeliveryMode, Event, EventChangeRequest, EventStatus
from app.user.models import User, UserRole
from tests.conftest import FakeNotifier
from tests.event.test_event_request_clarification_api import auth
from tests.factories import NOW, make_user

pytestmark = pytest.mark.anyio

IN_A_WEEK = NOW.date() + timedelta(days=7)
BODY = {"changes": {"expected_attendees": 50}, "reason": "Two more teams are joining."}


@pytest.fixture
def organiser(db: Session) -> User:
    user = make_user(db, UserRole.ORGANISER)
    user.full_name = "Olivia Organiser"
    db.flush()
    return user


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


def submitted_event(
    db: Session, organiser: User, status: EventStatus = EventStatus.SUBMITTED, coordinator: User | None = None
) -> Event:
    event = Event(
        name="Community design workshop",
        status=EventStatus.SUBMITTED,
        registration_enabled=False,
        event_category="Workshop",
        purpose="Plan a community design session",
        preferred_dates=[IN_A_WEEK],
        preferred_start_time=time(9, 0),
        preferred_end_time=time(11, 0),
        expected_attendees=24,
        created_by_user_id=organiser.id,
        submitted_by_user_id=organiser.id,
        submitted_at=NOW - timedelta(days=1),
        request_reference=f"ER-2026-{uuid.uuid4().int % 900000 + 100000}",
        coordinator_id=coordinator.id if coordinator else None,
    )
    db.add(event)
    db.flush()
    if status in (EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.CANCELLED, EventStatus.COMPLETED):
        event.start_at = NOW + timedelta(days=10)
        event.end_at = event.start_at + timedelta(hours=2)
        event.capacity = 40
        event.delivery_mode = DeliveryMode.IN_PERSON
    event.status = status
    db.flush()
    return event


async def request_change(client: AsyncClient, user: User, event: Event | uuid.UUID, body: dict = BODY):
    event_id = event.id if isinstance(event, Event) else event
    return await client.post(f"/api/v1/event-requests/{event_id}/change-requests", headers=auth(user), json=body)


def stored(db: Session, event: Event) -> list[EventChangeRequest]:
    return db.scalars(select(EventChangeRequest).where(EventChangeRequest.event_id == event.id)).all()


# --- AC 1: their own event, Submitted or later, not Rejected, Cancelled or Completed ---


@pytest.mark.parametrize(
    "status",
    [
        EventStatus.SUBMITTED,
        EventStatus.UNDER_REVIEW,
        EventStatus.AWAITING_CLARIFICATION,
        EventStatus.APPROVED,
        EventStatus.PLANNING,
        EventStatus.CONFIRMED,
    ],
)
async def test_tc_us29a_01_an_organiser_requests_a_change_from_submitted_on(
    client: AsyncClient, db: Session, organiser: User, status: EventStatus
) -> None:
    event = submitted_event(db, organiser, status)

    response = await request_change(client, organiser, event)

    assert response.status_code == 201
    assert response.json()["status"] == "pending_approval"


@pytest.mark.parametrize("status", [EventStatus.REJECTED, EventStatus.CANCELLED, EventStatus.COMPLETED])
async def test_tc_us29a_02_rejected_cancelled_and_completed_events_refuse(
    client: AsyncClient, db: Session, organiser: User, status: EventStatus
) -> None:
    event = submitted_event(db, organiser, status)

    response = await request_change(client, organiser, event)

    assert (response.status_code, response.json()) == (409, {"code": "CHANGE_NOT_ALLOWED", "status": status.value})
    assert stored(db, event) == []


async def test_tc_us29a_03_a_draft_another_organisers_event_and_an_unknown_id_are_not_found(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    draft = submitted_event(db, organiser, EventStatus.DRAFT)
    others = submitted_event(db, make_user(db, UserRole.ORGANISER))

    for event in (draft, others, uuid.uuid4()):
        response = await request_change(client, organiser, event)
        assert (response.status_code, response.json()) == (404, {"code": "NOT_FOUND"})


async def test_tc_us29a_04_the_request_stage_takes_preferred_dates_and_times(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    event = submitted_event(db, organiser)
    later = (IN_A_WEEK + timedelta(days=3)).isoformat()

    response = await request_change(
        client,
        organiser,
        event,
        {
            "changes": {
                "preferred_dates": [later],
                "preferred_start_time": "10:00",
                "preferred_end_time": "12:30",
                "equipment_needs": "Two microphones",
                "room_layout_preference": "Cabaret",
            },
            "reason": "The hall is free later that week.",
        },
    )

    assert response.status_code == 201
    assert [change["field"] for change in response.json()["changes"]] == [
        "preferred_dates",
        "preferred_start_time",
        "preferred_end_time",
        "room_layout_preference",
        "equipment_needs",
    ]


async def test_tc_us29a_05_a_planned_event_takes_its_start_and_end_not_preferences(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    event = submitted_event(db, organiser, EventStatus.PLANNING)
    new_end = (event.end_at + timedelta(hours=1)).isoformat()

    moved = await request_change(client, organiser, event, {"changes": {"end_at": new_end}, "reason": "Longer Q&A."})
    preferred = await request_change(
        client, organiser, event, {"changes": {"preferred_start_time": "10:00"}, "reason": "Later start."}
    )

    assert moved.status_code == 201
    [change] = moved.json()["changes"]
    # Compared as instants: the database gives the old value in its session's zone (UTC in CI, SGT locally).
    assert change["field"] == "end_at"
    assert datetime.fromisoformat(change["old_value"]) == event.end_at
    assert datetime.fromisoformat(change["new_value"]) == datetime.fromisoformat(new_end)
    assert preferred.status_code == 422
    assert preferred.json()["errors"] == {"preferred_start_time": "This can't be changed at this stage."}


# --- AC 2: each field's current and proposed value ---


async def test_tc_us29a_06_the_request_lists_each_field_with_its_current_and_proposed_value(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    event = submitted_event(db, organiser)

    response = await request_change(
        client,
        organiser,
        event,
        {"changes": {"expected_attendees": 50, "purpose": "Plan a community design session"}, "reason": "More teams."},
    )

    # The unchanged purpose isn't listed.
    assert response.json()["changes"] == [{"field": "expected_attendees", "old_value": 24, "new_value": 50}]


async def test_tc_us29a_07_proposing_only_current_values_is_refused(client: AsyncClient, db: Session, organiser: User) -> None:
    event = submitted_event(db, organiser)

    response = await request_change(client, organiser, event, {"changes": {"expected_attendees": 24}, "reason": "Same."})

    assert response.status_code == 422
    assert response.json()["code"] == "NO_CHANGES"
    assert stored(db, event) == []


# --- AC 3: a reason is required ---


@pytest.mark.parametrize(
    ("body", "fields"),
    [
        ({"changes": {"expected_attendees": 50}}, ["reason"]),
        ({"changes": {"expected_attendees": 50}, "reason": "   "}, ["reason"]),
        ({"changes": {}, "reason": "More teams."}, ["changes"]),
        ({}, ["changes", "reason"]),
    ],
)
async def test_tc_us29a_08_a_reason_and_at_least_one_change_are_required(
    client: AsyncClient, db: Session, organiser: User, body: dict, fields: list[str]
) -> None:
    event = submitted_event(db, organiser)

    response = await request_change(client, organiser, event, body)

    assert (response.status_code, response.json()) == (422, {"code": "MISSING_REQUIRED_FIELD", "fields": fields})
    assert stored(db, event) == []


async def test_tc_us29a_09_a_reason_over_1000_characters_is_refused(client: AsyncClient, db: Session, organiser: User) -> None:
    event = submitted_event(db, organiser)

    response = await request_change(client, organiser, event, {"changes": {"expected_attendees": 50}, "reason": "x" * 1001})

    assert response.json()["fields"] == ["reason"]


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"expected_attendees": 0}, "expected_attendees"),
        ({"expected_attendees": "lots"}, "expected_attendees"),
        ({"name": ""}, "name"),
        ({"preferred_dates": ["2026-09-01"]}, "preferred_dates"),
        ({"preferred_dates": ["not a date"]}, "preferred_dates"),
        ({"preferred_end_time": "08:00"}, "preferred_end_time"),
        ({"capacity": 100}, "capacity"),
        ({"status": "approved"}, "status"),
    ],
)
async def test_tc_us29a_10_an_invalid_proposed_value_is_named(
    client: AsyncClient, db: Session, organiser: User, changes: dict, field: str
) -> None:
    event = submitted_event(db, organiser)

    response = await request_change(client, organiser, event, {"changes": changes, "reason": "Because."})

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_CHANGE_REQUEST"
    assert response.json()["fields"] == [field]
    assert stored(db, event) == []


# --- AC 4: a Pending change request; the event keeps its values ---


async def test_tc_us29a_11_the_request_is_pending_and_the_event_is_unchanged(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    event = submitted_event(db, organiser)

    response = await request_change(client, organiser, event)

    body = response.json()
    assert (body["status"], body["reason"], body["event_id"]) == ("pending_approval", "Two more teams are joining.", str(event.id))
    db.refresh(event)
    assert (event.expected_attendees, event.status) == (24, EventStatus.SUBMITTED)
    [request] = stored(db, event)
    assert (request.status, request.requested_by_user_id, request.reason, request.created_at) == (
        ChangeRequestStatus.PENDING_APPROVAL,
        organiser.id,
        "Two more teams are joining.",
        NOW,
    )


def test_tc_us29a_12_the_schema_refuses_a_blank_reason(db: Session, organiser: User) -> None:
    event = submitted_event(db, organiser)
    db.add(
        EventChangeRequest(
            event_id=event.id,
            requested_by_user_id=organiser.id,
            changes=[{"field": "expected_attendees", "old_value": 24, "new_value": 50}],
            reason="  ",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


# --- AC 5: the assigned coordinator is notified ---


async def test_tc_us29a_13_the_assigned_coordinator_is_notified(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier
) -> None:
    event = submitted_event(db, organiser, EventStatus.UNDER_REVIEW, coordinator)

    await request_change(client, organiser, event)

    assert notifier.change_requests == [
        {
            "email": coordinator.email,
            "event_id": event.id,
            "event_name": "Community design workshop",
            "organiser_name": "Olivia Organiser",
            "fields": ["expected_attendees"],
            "reason": "Two more teams are joining.",
            "to_lead": False,
        }
    ]


async def test_tc_us29a_14_an_unassigned_event_notifies_every_active_lead(
    client: AsyncClient, db: Session, organiser: User, notifier: FakeNotifier
) -> None:
    """D91: a Submitted event has no coordinator yet (D27)."""
    db.execute(text("UPDATE users SET is_active = false WHERE 'coordinator_lead' = ANY(roles)"))
    leads = [make_user(db, UserRole.COORDINATOR_LEAD), make_user(db, UserRole.COORDINATOR_LEAD)]
    make_user(db, UserRole.COORDINATOR_LEAD, active=False)
    event = submitted_event(db, organiser)

    await request_change(client, organiser, event)

    assert sorted(call["email"] for call in notifier.change_requests) == sorted(lead.email for lead in leads)
    assert all(call["to_lead"] for call in notifier.change_requests)


async def test_tc_us29a_15_a_failed_notice_still_keeps_the_request(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, notifier: FakeNotifier
) -> None:
    event = submitted_event(db, organiser, EventStatus.UNDER_REVIEW, coordinator)
    notifier.fail = True

    response = await request_change(client, organiser, event)

    assert response.status_code == 201
    assert len(stored(db, event)) == 1


# --- AC 6: the organiser sees the status of their requests ---


async def test_tc_us29a_16_the_organiser_lists_their_change_requests_newest_first(
    client: AsyncClient, db: Session, organiser: User
) -> None:
    from app.core.clock import get_now
    from app.main import app

    first, second = submitted_event(db, organiser), submitted_event(db, organiser)
    await request_change(client, organiser, first)
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=5)
    await request_change(client, organiser, second, {"changes": {"purpose": "A new purpose"}, "reason": "Refocused."})
    await request_change(client, make_user(db, UserRole.ORGANISER), submitted_event(db, make_user(db, UserRole.ORGANISER)))

    everything = (await client.get("/api/v1/me/change-requests", headers=auth(organiser))).json()["change_requests"]
    one_event = (
        await client.get(f"/api/v1/me/change-requests?event_id={first.id}", headers=auth(organiser))
    ).json()["change_requests"]

    assert [(r["event_id"], r["status"]) for r in everything] == [
        (str(second.id), "pending_approval"),
        (str(first.id), "pending_approval"),
    ]
    assert everything[1]["request_reference"] == first.request_reference
    assert [r["event_id"] for r in one_event] == [str(first.id)]


async def test_tc_us29a_17_a_coordinators_us12_edits_are_not_in_the_organisers_list(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = submitted_event(db, organiser, EventStatus.PLANNING, coordinator)
    db.add(
        EventChangeRequest(
            event_id=event.id,
            requested_by_user_id=coordinator.id,
            changes=[{"field": "capacity", "old_value": 40, "new_value": 60}],
        )
    )
    db.flush()

    response = await client.get("/api/v1/me/change-requests", headers=auth(organiser))

    assert response.json()["change_requests"] == []


def test_tc_us29a_18_one_migration_head(db: Session) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from tests.conftest import BACKEND_DIR

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1
    assert "20261110_1200_us29a_change_reqs" in {revision.revision for revision in script.walk_revisions()}
    assert db.scalar(select(func.count()).select_from(EventChangeRequest)) == 0
