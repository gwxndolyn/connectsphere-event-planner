import logging
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import EventStatus
from app.user.models import User, UserRole
from tests.conftest import FakeNotifier
from tests.event.test_event_requests import auth, complete_request, create_draft, make_user
from tests.factories import NOW

pytestmark = pytest.mark.anyio


async def submit(client: AsyncClient, organiser: User, **fields: object):
    draft = await create_draft(client, organiser, **complete_request(**fields))
    return await client.post(f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser))


@pytest.fixture
def organiser(db: Session) -> User:
    user = make_user(db, UserRole.ORGANISER)
    user.full_name = "Olivia Organiser"
    db.flush()
    return user


async def test_tc_us10a_27_every_active_lead_is_told_once_with_the_request_details(
    client: AsyncClient, db: Session, organiser: User, notifier: FakeNotifier
) -> None:
    first = make_user(db, UserRole.COORDINATOR_LEAD)
    second = make_user(db, UserRole.COORDINATOR_LEAD)
    dates = [(NOW.date() + timedelta(days=9)).isoformat(), (NOW.date() + timedelta(days=7)).isoformat()]

    response = await submit(client, organiser, name="Alumni night", preferred_dates=dates)

    assert response.status_code == 200
    body = response.json()
    assert {call["email"] for call in notifier.queued} == {first.email, second.email}
    assert len(notifier.queued) == 2
    for call in notifier.queued:  # AC 11: name, organiser and preferred dates
        assert call["event_name"] == "Alumni night"
        assert call["organiser_name"] == "Olivia Organiser"
        assert [day.isoformat() for day in call["preferred_dates"]] == sorted(dates)
        assert call["request_reference"] == body["request_reference"]


async def test_tc_us10a_28_only_active_leads_are_told(
    client: AsyncClient, db: Session, organiser: User, notifier: FakeNotifier
) -> None:
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    make_user(db, UserRole.COORDINATOR_LEAD, active=False)
    make_user(db, UserRole.COORDINATOR)
    make_user(db, UserRole.OPERATIONS_MANAGER)

    await submit(client, organiser)

    assert [call["email"] for call in notifier.queued] == [lead.email]


async def test_tc_us10a_29_a_failing_notifier_never_undoes_the_submit(
    client: AsyncClient, db: Session, organiser: User, notifier: FakeNotifier, caplog: pytest.LogCaptureFixture
) -> None:
    make_user(db, UserRole.COORDINATOR_LEAD)
    make_user(db, UserRole.COORDINATOR_LEAD)
    notifier.fail = True

    with caplog.at_level(logging.ERROR):
        response = await submit(client, organiser)

    assert response.status_code == 200
    assert response.json()["status"] == EventStatus.SUBMITTED.value
    assert response.json()["coordinator"] is None
    assert len(notifier.queued) == 2  # one Lead failing doesn't stop the next
    assert "could not notify Lead" in caplog.text
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    queue = await client.get("/api/v1/event-requests/unassigned", headers=auth(lead))
    assert [row["id"] for row in queue.json()["event_requests"]] == [response.json()["id"]]


async def test_tc_us10a_30_no_active_lead_logs_a_warning_and_still_queues_the_request(
    client: AsyncClient, db: Session, organiser: User, notifier: FakeNotifier, caplog: pytest.LogCaptureFixture
) -> None:
    make_user(db, UserRole.COORDINATOR_LEAD, active=False)

    with caplog.at_level(logging.WARNING):
        response = await submit(client, organiser)

    assert response.status_code == 200
    assert notifier.queued == []
    assert "none is active" in caplog.text


async def test_tc_us10a_31_a_refused_submit_notifies_no_one(
    client: AsyncClient, db: Session, organiser: User, notifier: FakeNotifier
) -> None:
    make_user(db, UserRole.COORDINATOR_LEAD)
    draft = await create_draft(client, organiser, name="Incomplete")

    response = await client.post(f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser))

    assert response.status_code == 422
    assert notifier.queued == []
    again = await submit(client, organiser)  # a later good submit does notify
    assert again.status_code == 200 and len(notifier.queued) == 1
