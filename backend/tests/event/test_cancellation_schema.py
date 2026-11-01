"""US9 (SCRUM-12) PR 1: the event_cancellations table and its guards. See docs/testing/US9-cancel-event.md."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import CancellationStatus, Event, EventCancellation, EventStatus
from app.user.models import User, UserRole
from tests.conftest import BACKEND_DIR
from tests.event.test_event_request_clarification_api import auth
from tests.factories import NOW, make_event, make_user

REVISION = "20261112_1200_us9_cancellations"


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    return make_event(db, status=EventStatus.PLANNING, coordinator_id=coordinator.id)


def request(event: Event, organiser: User, **overrides: object) -> EventCancellation:
    values: dict[str, object] = {
        "event_id": event.id,
        "requested_by_user_id": organiser.id,
        "reason": "The speaker can't travel",
        "requested_at": NOW,
    }
    values.update(overrides)
    return EventCancellation(**values)


def approved(event: Event, coordinator: User, **overrides: object) -> EventCancellation:
    values: dict[str, object] = {
        "requested_by_user_id": coordinator.id,
        "status": CancellationStatus.APPROVED,
        "decided_by_user_id": coordinator.id,
        "decided_at": NOW,
    }
    values.update(overrides)
    return request(event, coordinator, **values)


def refused(db: Session, row: EventCancellation, constraint: str) -> None:
    db.add(row)
    with pytest.raises(IntegrityError, match=constraint):
        db.flush()
    db.rollback()


def test_tc_us9_01_schema_is_installed_with_rls(db: Session) -> None:
    statuses = db.scalars(
        text(
            "select enumlabel from pg_enum join pg_type on pg_type.oid = pg_enum.enumtypid "
            "where pg_type.typname = 'cancellation_status' order by enumsortorder"
        )
    ).all()
    assert statuses == ["pending", "approved", "rejected"]
    assert db.scalar(text("select relrowsecurity from pg_class where oid = 'event_cancellations'::regclass")) is True


def test_tc_us9_01_a_request_defaults_to_pending(db: Session, event: Event, organiser: User) -> None:
    row = request(event, organiser)
    db.add(row)
    db.flush()
    db.refresh(row)

    assert (row.status, row.decided_at, row.decided_by_user_id, row.rejection_reason) == (
        CancellationStatus.PENDING,
        None,
        None,
        None,
    )


def test_tc_us9_02_one_pending_request_per_event(db: Session, event: Event, organiser: User) -> None:
    db.add(request(event, organiser))
    db.flush()

    refused(db, request(event, organiser, reason="Asking again"), "event_cancellations_one_open")


def test_tc_us9_02_a_decided_request_doesnt_block_a_new_one(
    db: Session, event: Event, organiser: User, coordinator: User
) -> None:
    db.add(
        request(
            event,
            organiser,
            status=CancellationStatus.REJECTED,
            decided_by_user_id=coordinator.id,
            decided_at=NOW,
            rejection_reason="Registrations are strong",
        )
    )
    db.add(request(event, organiser, reason="Asking again", requested_at=NOW + timedelta(hours=1)))
    db.flush()


def test_tc_us9_03_one_approved_cancellation_per_event(db: Session, event: Event, coordinator: User) -> None:
    db.add(approved(event, coordinator))
    db.flush()

    refused(db, approved(event, coordinator, reason="Again"), "event_cancellations_one_open")


def test_tc_us9_03_no_request_after_a_cancel(db: Session, event: Event, organiser: User, coordinator: User) -> None:
    db.add(approved(event, coordinator))
    db.flush()

    refused(db, request(event, organiser), "event_cancellations_one_open")


def test_tc_us9_03_a_cancel_must_decide_the_pending_request(
    db: Session, event: Event, organiser: User, coordinator: User
) -> None:
    db.add(request(event, organiser))
    db.flush()

    refused(db, approved(event, coordinator), "event_cancellations_one_open")


def test_tc_us9_04_reason_cant_be_blank(db: Session, event: Event, organiser: User) -> None:
    refused(db, request(event, organiser, reason="   "), "event_cancellations_reason_not_blank")


@pytest.mark.parametrize(
    ("overrides", "with_decider"),
    [
        ({"status": CancellationStatus.APPROVED}, False),  # decided, but no one and no time
        ({"decided_at": NOW}, False),  # pending, but a decision time
        ({"status": CancellationStatus.APPROVED, "decided_at": NOW}, False),  # a time but no decider
        ({"status": CancellationStatus.APPROVED, "decided_at": NOW - timedelta(minutes=1)}, True),  # before the ask
    ],
)
def test_tc_us9_05_decision_fields_follow_the_status(
    db: Session,
    event: Event,
    organiser: User,
    coordinator: User,
    overrides: dict[str, object],
    with_decider: bool,
) -> None:
    if with_decider:
        overrides = {**overrides, "decided_by_user_id": coordinator.id}
    refused(db, request(event, organiser, **overrides), "event_cancellations_decided_consistent")


@pytest.mark.parametrize(
    ("status", "rejection_reason"),
    [
        (CancellationStatus.REJECTED, None),
        (CancellationStatus.REJECTED, "  "),
        (CancellationStatus.APPROVED, "Not a rejection"),
    ],
)
def test_tc_us9_06_a_rejection_reason_only_and_always_when_rejected(
    db: Session,
    event: Event,
    organiser: User,
    coordinator: User,
    status: CancellationStatus,
    rejection_reason: str | None,
) -> None:
    row = request(
        event,
        organiser,
        status=status,
        decided_by_user_id=coordinator.id,
        decided_at=NOW,
        rejection_reason=rejection_reason,
    )
    refused(db, row, "event_cancellations_rejection_reason_only_when_rejected")


def test_tc_us9_07_an_approved_event_without_a_date_can_be_cancelled(db: Session) -> None:
    event = make_event(db, status=EventStatus.APPROVED)
    event.capacity = None
    db.flush()
    assert event.start_at is None

    event.status = EventStatus.CANCELLED
    db.flush()


def test_tc_us9_07_a_cancelled_event_still_needs_its_name(db: Session) -> None:
    event = make_event(db, status=EventStatus.APPROVED)
    event.name = None
    db.flush()

    event.status = EventStatus.CANCELLED
    with pytest.raises(IntegrityError, match="events_final_fields_required"):
        db.flush()


def test_tc_us9_07_a_planned_event_still_needs_its_final_fields(db: Session, event: Event) -> None:
    event.start_at = None
    with pytest.raises(IntegrityError, match="events_final_fields_required"):
        db.flush()


def test_tc_us9_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert REVISION in {revision.revision for revision in script.walk_revisions()}


@pytest.fixture
def dateless_cancelled(db: Session, organiser: User, coordinator: User) -> Event:
    """Cancelled while Approved, before it had a date or capacity (D93)."""
    event = make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)
    event.created_by_user_id = organiser.id
    event.capacity = None
    event.status = EventStatus.CANCELLED
    db.flush()
    return event


@pytest.mark.anyio
async def test_tc_us9_08_coordinators_events_leave_out_one_cancelled_before_it_was_planned(
    client: AsyncClient, db: Session, coordinator: User, event: Event, dateless_cancelled: Event
) -> None:
    listed = await client.get("/api/v1/me/coordinated-events", headers=auth(coordinator))
    opened = await client.get(f"/api/v1/events/{dateless_cancelled.id}", headers=auth(coordinator))

    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["events"]] == [str(event.id)]
    assert opened.status_code == 404


@pytest.mark.anyio
async def test_tc_us9_08_managed_events_leave_out_one_cancelled_before_it_was_planned(
    client: AsyncClient, db: Session, organiser: User, dateless_cancelled: Event
) -> None:
    listed = await client.get("/api/v1/me/managed-events", headers=auth(organiser))
    opened = await client.get(f"/api/v1/events/{dateless_cancelled.id}/registrations", headers=auth(organiser))

    assert listed.status_code == 200
    assert str(dateless_cancelled.id) not in listed.text
    assert opened.status_code == 404
