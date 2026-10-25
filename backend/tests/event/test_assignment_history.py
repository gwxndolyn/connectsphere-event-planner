import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.event.models import AssignmentKind, CoordinatorAssignment, EventStatus
from app.user.models import User, UserRole
from tests.event.test_coordinator_assignment_api import assign
from tests.event.test_event_request_clarification_api import make_request, make_user
from tests.event.test_event_requests import auth

pytestmark = pytest.mark.anyio


def history_url(request_id: uuid.UUID) -> str:
    return f"/api/v1/event-requests/{request_id}/assignment-history"


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def lead(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR_LEAD)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


def test_tc_us10d_01_the_history_table_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)
    columns = {c["name"]: c for c in inspector.get_columns("coordinator_assignments")}
    assert set(columns) == {"id", "event_id", "assigned_by_user_id", "coordinator_id", "kind", "created_at"}
    assert not any(column["nullable"] for column in columns.values())
    referred = {fk["constrained_columns"][0]: fk["referred_table"] for fk in inspector.get_foreign_keys("coordinator_assignments")}
    assert referred == {"event_id": "events", "assigned_by_user_id": "users", "coordinator_id": "users"}


async def test_tc_us10d_02_assigning_stores_who_whom_which_event_and_when(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    event = make_request(db, organiser, EventStatus.SUBMITTED)

    response = await assign(client, lead, event.id, coordinator.id)

    assert response.status_code == 200
    [record] = db.scalars(select(CoordinatorAssignment)).all()
    assert record.event_id == event.id
    assert record.assigned_by_user_id == lead.id
    assert record.coordinator_id == coordinator.id
    assert record.kind == AssignmentKind.ASSIGNMENT
    assert record.created_at is not None


@pytest.mark.parametrize("target", ["lead", "organiser", "inactive"])
async def test_tc_us10d_03_a_refused_assignment_writes_no_record(
    client: AsyncClient, db: Session, organiser: User, lead: User, target: str
) -> None:
    event = make_request(db, organiser, EventStatus.SUBMITTED)
    picked = {"lead": lead, "organiser": organiser, "inactive": make_user(db, UserRole.COORDINATOR, active=False)}[target]

    response = await assign(client, lead, event.id, picked.id)

    assert response.status_code == 422
    assert db.scalars(select(CoordinatorAssignment)).all() == []


async def test_tc_us10d_04_an_already_assigned_request_gets_no_second_record(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    event = make_request(db, organiser, EventStatus.SUBMITTED)
    await assign(client, lead, event.id, coordinator.id)

    again = await assign(client, lead, event.id, make_user(db, UserRole.COORDINATOR).id)

    assert again.status_code == 409
    assert len(db.scalars(select(CoordinatorAssignment)).all()) == 1


async def test_tc_us10d_05_the_history_shows_kind_lead_coordinator_and_time(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    lead.full_name = "Lena Lead"
    coordinator.full_name = "Casey Tan"
    event = make_request(db, organiser, EventStatus.SUBMITTED)
    await assign(client, lead, event.id, coordinator.id)

    response = await client.get(history_url(event.id), headers=auth(lead))

    assert response.status_code == 200
    [entry] = response.json()["assignments"]
    assert entry["kind"] == "assignment"
    assert entry["assigned_by"] == {"id": str(lead.id), "name": "Lena Lead", "email": lead.email}
    assert entry["coordinator"] == {"id": str(coordinator.id), "name": "Casey Tan", "email": coordinator.email}
    assert entry["created_at"]


async def test_tc_us10d_06_records_are_listed_newest_first_with_reassignments_marked(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    event = make_request(db, organiser, EventStatus.UNDER_REVIEW)
    other = make_user(db, UserRole.COORDINATOR)
    first = CoordinatorAssignment(
        event_id=event.id, assigned_by_user_id=lead.id, coordinator_id=coordinator.id, kind=AssignmentKind.ASSIGNMENT
    )
    db.add(first)
    db.flush()
    db.refresh(first)
    db.add(
        CoordinatorAssignment(
            event_id=event.id,
            assigned_by_user_id=lead.id,
            coordinator_id=other.id,
            kind=AssignmentKind.REASSIGNMENT,
            created_at=first.created_at + timedelta(hours=1),
        )
    )
    db.flush()

    response = await client.get(history_url(event.id), headers=auth(lead))

    rows = response.json()["assignments"]
    assert [(row["kind"], row["coordinator"]["id"]) for row in rows] == [
        ("reassignment", str(other.id)),
        ("assignment", str(coordinator.id)),
    ]


async def test_tc_us10d_07_an_event_without_records_has_an_empty_history(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    event = make_request(db, organiser, EventStatus.SUBMITTED)

    response = await client.get(history_url(event.id), headers=auth(lead))

    assert response.status_code == 200
    assert response.json() == {"assignments": []}


async def test_tc_us10d_08_one_events_history_leaves_out_other_events_records(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    mine = make_request(db, organiser, EventStatus.SUBMITTED)
    theirs = make_request(db, organiser, EventStatus.SUBMITTED)
    await assign(client, lead, theirs.id, coordinator.id)

    response = await client.get(history_url(mine.id), headers=auth(lead))

    assert response.json() == {"assignments": []}


async def test_tc_us10d_09_only_the_lead_can_read_the_history(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User
) -> None:
    event = make_request(db, organiser, EventStatus.SUBMITTED)
    await assign(client, lead, event.id, coordinator.id)

    for user in (organiser, coordinator, make_user(db, UserRole.VENUE_STAFF), make_user(db, UserRole.ATTENDEE)):
        assert (await client.get(history_url(event.id), headers=auth(user))).status_code == 403
    assert (await client.get(history_url(event.id))).status_code == 401


async def test_tc_us10d_10_a_draft_or_unknown_event_is_not_found(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    draft = make_request(db, organiser, EventStatus.DRAFT)

    assert (await client.get(history_url(draft.id), headers=auth(lead))).status_code == 404
    assert (await client.get(history_url(uuid.uuid4()), headers=auth(lead))).status_code == 404


def test_tc_us10d_15_the_history_table_has_row_level_security(db: Session) -> None:
    assert db.execute(
        text("select relrowsecurity from pg_class where oid = 'coordinator_assignments'::regclass")
    ).scalar_one() is True
