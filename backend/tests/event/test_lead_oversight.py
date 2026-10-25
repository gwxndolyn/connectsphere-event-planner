import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import AssignmentKind, CoordinatorAssignment, Event, EventStatus
from app.user.models import User, UserRole
from tests.event.test_coordinator_assignment_api import assign
from tests.event.test_event_request_clarification_api import make_request, make_user
from tests.event.test_event_requests import auth
from tests.factories import make_event

pytestmark = pytest.mark.anyio

ASSIGNED = "/api/v1/event-requests/assigned"
UNASSIGNED = "/api/v1/event-requests/unassigned"
REQUEST_STAGE = (EventStatus.UNDER_REVIEW, EventStatus.AWAITING_CLARIFICATION, EventStatus.APPROVED, EventStatus.REJECTED)


def owned(
    db: Session,
    organiser: User,
    lead: User,
    coordinator: User,
    status: EventStatus = EventStatus.UNDER_REVIEW,
    *,
    name: str | None = None,
    kind: AssignmentKind = AssignmentKind.ASSIGNMENT,
) -> Event:
    """An event `coordinator` owns, with the record saying `lead` assigned it."""
    event = make_request(db, organiser, status) if status in REQUEST_STAGE else make_event(db, status=status)
    if name:
        event.name = name
    event.coordinator_id = coordinator.id
    db.add(CoordinatorAssignment(event_id=event.id, assigned_by_user_id=lead.id, coordinator_id=coordinator.id, kind=kind))
    db.flush()
    return event


async def names(client: AsyncClient, user: User, **params: str) -> list[str]:
    response = await client.get(ASSIGNED, headers=auth(user), params=params)
    assert response.status_code == 200
    return [row["name"] for row in response.json()["event_requests"]]


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def lead(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR_LEAD)


@pytest.fixture
def other_lead(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR_LEAD)


@pytest.fixture
def casey(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.full_name = "Casey Tan"
    db.flush()
    return user


async def test_tc_us19_01_lists_the_active_events_the_lead_assigned_with_coordinator_status_and_date(
    client: AsyncClient, db: Session, organiser: User, lead: User, casey: User
) -> None:
    event = owned(db, organiser, lead, casey, name="Careers fair")
    event.preferred_dates = [date(2026, 12, 3), date(2026, 12, 10)]
    db.flush()

    response = await client.get(ASSIGNED, headers=auth(lead))

    [row] = response.json()["event_requests"]
    assert row["id"] == str(event.id)
    assert row["name"] == "Careers fair"
    assert row["status"] == "under_review"
    assert row["coordinator"] == {"id": str(casey.id), "name": "Casey Tan"}
    assert row["event_date"] == "2026-12-03"


async def test_tc_us19_02_a_confirmed_event_shows_its_start_date_in_singapore_time(
    client: AsyncClient, db: Session, organiser: User, lead: User, casey: User
) -> None:
    event = owned(db, organiser, lead, casey, EventStatus.CONFIRMED, name="Gala")
    event.start_at = datetime(2026, 12, 4, 17, 0, tzinfo=timezone.utc)  # 01:00 on the 5th in Singapore
    db.flush()

    [row] = (await client.get(ASSIGNED, headers=auth(lead))).json()["event_requests"]

    assert row["event_date"] == "2026-12-05"


async def test_tc_us19_03_only_active_events_are_listed(
    client: AsyncClient, db: Session, organiser: User, lead: User, casey: User
) -> None:
    for status in (
        EventStatus.UNDER_REVIEW,
        EventStatus.AWAITING_CLARIFICATION,
        EventStatus.APPROVED,
        EventStatus.PLANNING,
        EventStatus.CONFIRMED,
    ):
        owned(db, organiser, lead, casey, status, name=status.value)
    for status in (EventStatus.REJECTED, EventStatus.CANCELLED, EventStatus.COMPLETED):
        owned(db, organiser, lead, casey, status, name=status.value)

    assert sorted(await names(client, lead)) == sorted(
        ["under_review", "awaiting_clarification", "approved", "planning", "confirmed"]
    )


async def test_tc_us19_04_a_lead_sees_only_events_they_assigned_and_two_leads_see_their_own(
    client: AsyncClient, db: Session, organiser: User, lead: User, other_lead: User, casey: User
) -> None:
    owned(db, organiser, lead, casey, name="Mine")
    owned(db, organiser, other_lead, casey, name="Theirs")

    assert await names(client, lead) == ["Mine"]
    assert await names(client, other_lead) == ["Theirs"]


async def test_tc_us19_05_a_later_reassignment_moves_the_event_to_the_lead_who_did_it(
    client: AsyncClient, db: Session, organiser: User, lead: User, other_lead: User, casey: User
) -> None:
    event = owned(db, organiser, lead, casey, name="Handed over")
    db.add(
        CoordinatorAssignment(
            event_id=event.id,
            assigned_by_user_id=other_lead.id,
            coordinator_id=casey.id,
            kind=AssignmentKind.REASSIGNMENT,
            created_at=datetime(2999, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.flush()

    assert await names(client, lead) == []
    assert await names(client, other_lead) == ["Handed over"]


async def test_tc_us19_06_filters_by_coordinator_and_by_status(
    client: AsyncClient, db: Session, organiser: User, lead: User, casey: User
) -> None:
    dana = make_user(db, UserRole.COORDINATOR)
    owned(db, organiser, lead, casey, EventStatus.UNDER_REVIEW, name="A")
    owned(db, organiser, lead, casey, EventStatus.APPROVED, name="B")
    owned(db, organiser, lead, dana, EventStatus.APPROVED, name="C")

    assert sorted(await names(client, lead, coordinator_id=str(casey.id))) == ["A", "B"]
    assert sorted(await names(client, lead, status="approved")) == ["B", "C"]
    assert await names(client, lead, coordinator_id=str(dana.id), status="approved") == ["C"]
    assert await names(client, lead, coordinator_id=str(dana.id), status="under_review") == []
    assert await names(client, lead, coordinator_id=str(uuid.uuid4())) == []


async def test_tc_us19_07_a_status_that_is_not_active_is_refused(
    client: AsyncClient, lead: User
) -> None:
    response = await client.get(ASSIGNED, headers=auth(lead), params={"status": "rejected"})

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_STATUS_FILTER"


async def test_tc_us19_08_events_come_soonest_first_and_undated_last(
    client: AsyncClient, db: Session, organiser: User, lead: User, casey: User
) -> None:
    for name, dates in (("Late", [date(2026, 12, 20)]), ("Undated", None), ("Early", [date(2026, 12, 1)])):
        event = owned(db, organiser, lead, casey, name=name)
        event.preferred_dates = dates
    db.flush()

    assert await names(client, lead) == ["Early", "Late", "Undated"]


async def test_tc_us19_09_only_the_lead_may_open_the_assigned_list(
    client: AsyncClient, db: Session, organiser: User, casey: User
) -> None:
    for user in (organiser, casey, make_user(db, UserRole.VENUE_STAFF), make_user(db, UserRole.ATTENDEE)):
        assert (await client.get(ASSIGNED, headers=auth(user))).status_code == 403
    assert (await client.get(ASSIGNED)).status_code == 401


async def test_tc_us19_10_the_unassigned_queue_is_shared_and_an_assignment_by_one_lead_moves_it_to_their_tab(
    client: AsyncClient, db: Session, organiser: User, lead: User, other_lead: User, casey: User
) -> None:
    event = make_request(db, organiser, EventStatus.SUBMITTED)
    event.name = "Shared"
    db.flush()
    for reader in (lead, other_lead):
        queue = (await client.get(UNASSIGNED, headers=auth(reader))).json()["event_requests"]
        assert [row["name"] for row in queue] == ["Shared"]

    assert (await assign(client, lead, event.id, casey.id)).status_code == 200

    for reader in (lead, other_lead):
        assert (await client.get(UNASSIGNED, headers=auth(reader))).json()["event_requests"] == []
    assert await names(client, lead) == ["Shared"]
    assert await names(client, other_lead) == []


async def test_tc_us19_11_the_lead_has_no_approve_reject_or_confirm_routes(
    client: AsyncClient, db: Session, organiser: User, lead: User, casey: User
) -> None:
    event = owned(db, organiser, lead, casey)
    for action in ("approve", "reject", "confirm", "approval"):
        response = await client.post(f"/api/v1/event-requests/{event.id}/{action}", headers=auth(lead))
        assert response.status_code in (404, 405)
