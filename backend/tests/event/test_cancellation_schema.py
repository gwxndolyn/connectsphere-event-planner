"""US9 (SCRUM-12) PR 1: the event_cancellations table and its guards. See docs/testing/US9-cancel-event.md."""

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import CancellationStatus, Event, EventCancellation, EventStatus
from app.user.models import User, UserRole
from tests.factories import NOW, make_event, make_user


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

    refused(db, request(event, organiser, reason="Asking again"), "event_cancellations_one_pending")


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

    refused(db, approved(event, coordinator, reason="Again"), "event_cancellations_one_approved")


def test_tc_us9_04_reason_cant_be_blank(db: Session, event: Event, organiser: User) -> None:
    refused(db, request(event, organiser, reason="   "), "event_cancellations_reason_not_blank")


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": CancellationStatus.APPROVED},  # decided, but no one and no time
        {"decided_at": NOW},  # pending, but a decision time
        {"status": CancellationStatus.APPROVED, "decided_at": NOW},  # a time but no decider
    ],
)
def test_tc_us9_05_decision_fields_follow_the_status(
    db: Session, event: Event, organiser: User, overrides: dict[str, object]
) -> None:
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


def test_tc_us9_07_a_planned_event_still_needs_its_final_fields(db: Session, event: Event) -> None:
    event.start_at = None
    with pytest.raises(IntegrityError, match="events_final_fields_required"):
        db.flush()
