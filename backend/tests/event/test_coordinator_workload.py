import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import EventStatus
from app.user.models import User, UserRole
from tests.event.test_coordinator_assignment_api import assign
from tests.event.test_event_request_clarification_api import make_request, make_user
from tests.event.test_event_requests import auth
from tests.factories import make_event

pytestmark = pytest.mark.anyio

PICKER = "/api/v1/coordinators"
REQUEST_STAGE = (EventStatus.UNDER_REVIEW, EventStatus.AWAITING_CLARIFICATION, EventStatus.APPROVED, EventStatus.REJECTED)


def give(db: Session, organiser: User, coordinator: User, status: EventStatus) -> None:
    """An event of `status` that `coordinator` owns. Planning onwards needs the full event fields."""
    event = make_request(db, organiser, status) if status in REQUEST_STAGE else make_event(db, status=status)
    event.coordinator_id = coordinator.id
    db.flush()


async def counts(client: AsyncClient, lead: User) -> dict[str, int]:
    response = await client.get(PICKER, headers=auth(lead))
    assert response.status_code == 200
    return {row["id"]: row["planning_count"] for row in response.json()["coordinators"]}


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def lead(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR_LEAD)


async def test_tc_us10b_01_each_entry_has_a_name_and_a_count_and_zero_when_none(
    client: AsyncClient, db: Session, lead: User
) -> None:
    casey = make_user(db, UserRole.COORDINATOR)
    casey.full_name = "Casey Tan"
    db.flush()

    response = await client.get(PICKER, headers=auth(lead))

    [row] = response.json()["coordinators"]
    assert row == {"id": str(casey.id), "name": "Casey Tan", "email": casey.email, "planning_count": 0}


async def test_tc_us10b_02_counts_only_the_events_a_coordinator_is_working(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    busy = make_user(db, UserRole.COORDINATOR)
    for status in (
        EventStatus.UNDER_REVIEW,
        EventStatus.AWAITING_CLARIFICATION,
        EventStatus.APPROVED,
        EventStatus.PLANNING,
        # Finished or closed events are no longer being planned.
        EventStatus.REJECTED,
        EventStatus.CONFIRMED,
        EventStatus.CANCELLED,
        EventStatus.COMPLETED,
    ):
        give(db, organiser, busy, status)

    assert (await counts(client, lead))[str(busy.id)] == 4


async def test_tc_us10b_03_counts_are_per_coordinator(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    first = make_user(db, UserRole.COORDINATOR)
    second = make_user(db, UserRole.COORDINATOR)
    idle = make_user(db, UserRole.COORDINATOR)
    give(db, organiser, first, EventStatus.PLANNING)
    give(db, organiser, second, EventStatus.PLANNING)
    give(db, organiser, second, EventStatus.UNDER_REVIEW)

    result = await counts(client, lead)

    assert (result[str(first.id)], result[str(second.id)], result[str(idle.id)]) == (1, 2, 0)


async def test_tc_us10b_04_assigning_raises_the_count_by_one_the_next_time_the_picker_opens(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR)
    give(db, organiser, coordinator, EventStatus.PLANNING)
    queued = make_request(db, organiser)
    before = (await counts(client, lead))[str(coordinator.id)]

    assert (await assign(client, lead, queued.id, coordinator.id)).status_code == 200

    assert (await counts(client, lead))[str(coordinator.id)] == before + 1 == 2


async def test_tc_us10b_05_a_refused_assignment_leaves_every_count_alone(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR)
    queued = make_request(db, organiser)
    before = await counts(client, lead)

    assert (await assign(client, lead, queued.id, lead.id)).status_code == 422

    assert await counts(client, lead) == before


async def test_tc_us10b_06_inactive_coordinators_and_other_roles_are_not_listed_and_only_the_lead_may_look(
    client: AsyncClient, db: Session, organiser: User, lead: User
) -> None:
    inactive = make_user(db, UserRole.COORDINATOR, active=False)
    give(db, organiser, inactive, EventStatus.PLANNING)
    make_user(db, UserRole.VENUE_STAFF)
    coordinator = make_user(db, UserRole.COORDINATOR)

    result = await counts(client, lead)

    assert str(inactive.id) not in result and str(coordinator.id) in result
    assert (await client.get(PICKER, headers=auth(coordinator))).status_code == 403
    assert (await client.get(PICKER)).status_code == 401
