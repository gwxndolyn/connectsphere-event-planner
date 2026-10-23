import logging
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from tests.conftest import FakeNotifier
from tests.event.test_coordinator_assignment_api import assign
from tests.event.test_event_request_clarification_api import make_request, make_user
from tests.factories import NOW

pytestmark = pytest.mark.anyio

DATES = [(NOW + timedelta(days=7)).date(), (NOW + timedelta(days=9)).date()]


def queued_request(db: Session, organiser: User, status: EventStatus = EventStatus.SUBMITTED) -> Event:
    event = make_request(db, organiser, status)
    event.name = "Alumni night"
    event.request_reference = f"ER-2026-{uuid.uuid4().int % 900000 + 100000}"
    event.preferred_dates = DATES
    db.flush()
    return event


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def lead(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR_LEAD)


@pytest.fixture
def coordinator(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.full_name = "Casey Tan"
    db.flush()
    return user


async def test_tc_us10c_01_the_coordinator_is_told_with_event_coordinator_and_date(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User, notifier: FakeNotifier
) -> None:
    event = queued_request(db, organiser)

    response = await assign(client, lead, event.id, coordinator.id)

    assert response.status_code == 200
    [notice] = [n for n in notifier.assignments if n["recipient"] == "coordinator"]
    assert notice == {
        "email": coordinator.email,
        "recipient": "coordinator",
        "request_reference": event.request_reference,
        "event_name": "Alumni night",
        "coordinator_name": "Casey Tan",
        "event_dates": DATES,
    }


async def test_tc_us10c_02_the_organiser_is_told_the_same_three_details(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User, notifier: FakeNotifier
) -> None:
    event = queued_request(db, organiser)

    await assign(client, lead, event.id, coordinator.id)

    assert len(notifier.assignments) == 2  # AC 1 and 2: one each, no copy to the Lead
    to_coordinator, to_organiser = sorted(notifier.assignments, key=lambda n: n["recipient"] != "coordinator")
    assert to_organiser["email"] == organiser.email and to_organiser["recipient"] == "organiser"
    for key in ("event_name", "coordinator_name", "event_dates", "request_reference"):
        assert to_organiser[key] == to_coordinator[key]
    assert lead.email not in {n["email"] for n in notifier.assignments}


async def test_tc_us10c_03_a_coordinator_with_no_full_name_is_named_by_email(
    client: AsyncClient, db: Session, organiser: User, lead: User, notifier: FakeNotifier
) -> None:
    unnamed = make_user(db, UserRole.COORDINATOR)
    event = queued_request(db, organiser)

    await assign(client, lead, event.id, unnamed.id)

    assert {n["coordinator_name"] for n in notifier.assignments} == {unnamed.email}


async def test_tc_us10c_04_an_assignment_that_does_not_complete_sends_nothing(
    client: AsyncClient, db: Session, organiser: User, lead: User, coordinator: User, notifier: FakeNotifier
) -> None:
    inactive = make_user(db, UserRole.COORDINATOR, active=False)
    event = queued_request(db, organiser)
    draft = queued_request(db, organiser, EventStatus.DRAFT)
    assigned = queued_request(db, organiser)
    assigned.coordinator_id = coordinator.id
    db.flush()

    assert (await assign(client, lead, event.id, inactive.id)).status_code == 422
    assert (await assign(client, lead, event.id, lead.id)).status_code == 422
    assert (await assign(client, lead, event.id, uuid.uuid4())).status_code == 422
    assert (await assign(client, lead, assigned.id, coordinator.id)).status_code == 409
    assert (await assign(client, lead, draft.id, coordinator.id)).status_code == 404
    assert (await assign(client, organiser, event.id, coordinator.id)).status_code == 403
    assert (await assign(client, None, event.id, coordinator.id)).status_code == 401

    assert notifier.assignments == []


async def test_tc_us10c_05_a_failing_notifier_never_undoes_the_assignment(
    client: AsyncClient,
    db: Session,
    organiser: User,
    lead: User,
    coordinator: User,
    notifier: FakeNotifier,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = queued_request(db, organiser)
    notifier.fail = True

    with caplog.at_level(logging.ERROR):
        response = await assign(client, lead, event.id, coordinator.id)

    assert response.status_code == 200
    assert response.json()["status"] == "under_review"
    db.refresh(event)
    assert event.coordinator_id == coordinator.id
    assert len(notifier.assignments) == 2  # the organiser's notice was still tried
    assert "could not send the coordinator assignment notice" in caplog.text


async def test_tc_us10c_06_no_organiser_email_logs_a_warning_and_still_tells_the_coordinator(
    client: AsyncClient,
    db: Session,
    organiser: User,
    lead: User,
    coordinator: User,
    notifier: FakeNotifier,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = queued_request(db, organiser)
    event.created_by_user_id = None
    db.flush()

    with caplog.at_level(logging.WARNING):
        response = await assign(client, lead, event.id, coordinator.id)

    assert response.status_code == 200
    assert [n["recipient"] for n in notifier.assignments] == ["coordinator"]
    assert "could not notify the organiser" in caplog.text


async def test_tc_us10c_07_missing_request_details_log_a_warning_and_send_nothing(
    client: AsyncClient,
    db: Session,
    organiser: User,
    lead: User,
    coordinator: User,
    notifier: FakeNotifier,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = queued_request(db, organiser)
    event.request_reference = None
    db.flush()

    with caplog.at_level(logging.WARNING):
        response = await assign(client, lead, event.id, coordinator.id)

    assert response.status_code == 200
    assert notifier.assignments == []
    assert "missing request details" in caplog.text
