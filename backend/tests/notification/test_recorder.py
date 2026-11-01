"""US31 (SCRUM-107): every notice the system raises is also kept for the person it was sent to."""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.equipment.models import EquipmentLineStatus
from app.event.models import Event, EventStatus
from app.main import app
from app.notification.models import Notification
from app.notification.recorder import RecordingNotifier
from app.notification.service import LoggingNotifier, Notifier, get_notifier
from app.user.models import User, UserRole
from tests.conftest import FakeNotifier
from tests.equipment.test_equipment_api import make_line
from tests.equipment.test_equipment_schema import make_type
from tests.event.test_coordinator_assignment_api import assign
from tests.event.test_event_request_clarification_api import make_request
from tests.event.test_event_requests import auth
from tests.factories import NOW, make_attendee, make_registration, make_user, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

STARTS = datetime(2026, 11, 13, 6, 0, tzinfo=timezone.utc)
ENDS = STARTS + timedelta(hours=2)
REFERENCE = "ER-2026-000101"


def recorder(db: Session) -> tuple[RecordingNotifier, FakeNotifier]:
    """The recording notifier on the test's own session (its transaction is rolled back after the test)."""
    inner = FakeNotifier()
    return RecordingNotifier(inner, lambda: db, close_sessions=False), inner


def kept(db: Session, user: User) -> list[Notification]:
    return list(
        db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at, Notification.id))
    )


@pytest.fixture
def person(db: Session) -> User:
    user = make_user(db, UserRole.ORGANISER)
    user.email = "Olivia.Organiser@smu.edu.sg"
    db.flush()
    return user


@pytest.fixture
def event(db: Session, person: User) -> Event:
    event = make_request(db, person, EventStatus.APPROVED)
    event.name = "Alumni night"
    event.request_reference = REFERENCE
    db.flush()
    return event


# One call to each Notifier method, with a fragment its sentence must hold and how the event is found.
CALLS = [
    ("waitlist_offer", lambda c: dict(event_name="Alumni night", expires_at=STARTS, registration_id=c.registration.id), "Accept it before", "registration"),
    ("clarification_requested", lambda c: dict(request_reference=REFERENCE, event_name="Alumni night", round=2, sections=["attendance", "layout"], comment="How many?"), "clarification on attendance, layout (round 2): How many?", "reference"),
    ("venue_booking_requested", lambda c: dict(booking_id=c.booking.id, event_name="Alumni night", venue_name="SCIS Room", starts_at=STARTS, ends_at=ENDS), "A booking was requested for SCIS Room", "booking"),
    ("venue_booking_decided", lambda c: dict(booking_id=c.booking.id, decision="rejected", event_name="Alumni night", venue_name="SCIS Room", starts_at=STARTS, ends_at=ENDS, reason="Closed", alternative_suggestion="Room B"), "was rejected. Reason: Closed Suggested instead: Room B", "booking"),
    ("venue_booking_withdrawn", lambda c: dict(booking_id=c.booking.id, event_name="Alumni night", venue_name="SCIS Room", starts_at=STARTS, ends_at=ENDS), "was withdrawn", "booking"),
    ("request_queued", lambda c: dict(request_reference=REFERENCE, event_name="Alumni night", organiser_name="Olivia", preferred_dates=[date(2026, 11, 13)]), "Olivia submitted request ER-2026-000101 for 13 Nov 2026", "reference"),
    ("assignment_made", lambda c: dict(recipient="coordinator", request_reference=REFERENCE, event_name="Alumni night", coordinator_name="Casey Tan", event_dates=[date(2026, 11, 13)]), "You were assigned to coordinate request ER-2026-000101", "reference"),
    ("event_reassigned", lambda c: dict(recipient="new_coordinator", request_reference=REFERENCE, event_name="Alumni night", previous_coordinator_name="Pat", new_coordinator_name="Casey Tan", event_dates=[], reason="Leave"), "reassigned to you from Pat. Reason: Leave", "reference"),
    ("transfer_requested", lambda c: dict(request_reference=REFERENCE, event_name="Alumni night", coordinator_name="Casey Tan", reason="Clash"), "Casey Tan asked to transfer request ER-2026-000101. Reason: Clash", "reference"),
    ("equipment_line_reviewed", lambda c: dict(line_id=c.line.id, event_name="Alumni night", equipment_type="Projector", quantity=2, decision="approved", note="Bring a cable"), "2 × Projector was approved. Note: Bring a cable", "line"),
    ("request_decided", lambda c: dict(request_reference=REFERENCE, event_name="Alumni night", decision="rejected", reason="Too late"), "ER-2026-000101 was rejected. Reason: Too late", "reference"),
    ("tech_staff_assigned", lambda c: dict(event_id=c.event.id, event_name="Alumni night", starts_at=STARTS, ends_at=ENDS, venue_name="SCIS Room", location="Level 2", equipment=["Projector"], equipment_needs=None), "You were assigned to support the event", "id"),
    ("event_confirmed", lambda c: dict(request_reference=REFERENCE, event_name="Alumni night", starts_at=STARTS, ends_at=ENDS, venues=["SCIS Room"]), "The event is confirmed for Fri 13 Nov 2026, 06:00 UTC", "reference"),
    ("safety_review_decided", lambda c: dict(request_reference=REFERENCE, event_name="Alumni night", outcome="rejected", comments="Add an exit", issues=["Emergency access"]), "rejected the safety arrangement. Flagged: Emergency access. Comments: Add an exit", "reference"),
    ("safety_changes_requested", lambda c: dict(request_reference=REFERENCE, event_name="Alumni night", comments="Widen the aisles", areas=["Venue", "Layout"], issues=[]), "asked for changes to Venue, Layout. Comments: Widen the aisles", "reference"),
    ("cancellation_requested", lambda c: dict(event_id=c.event.id, event_name="Alumni night", organiser_name="Olivia", reason="Speaker unwell"), "Olivia asked to cancel the event. Reason: Speaker unwell", "id"),
    ("cancellation_rejected", lambda c: dict(event_id=c.event.id, event_name="Alumni night", reason="Speaker unwell", rejection_reason="Find a stand-in"), "was rejected, so it goes ahead. Reason: Find a stand-in", "id"),
    ("event_cancelled", lambda c: dict(event_id=c.event.id, event_name="Alumni night", reason="Venue closed", recipient="organiser"), "The event was cancelled. Reason: Venue closed", "id"),
    ("change_requested", lambda c: dict(event_id=c.event.id, event_name="Alumni night", organiser_name="Olivia", fields=["capacity"], reason="Bigger room", to_lead=False), "Olivia asked to change capacity. Reason: Bigger room", "id"),
]


class Ctx:
    def __init__(self, event: Event, booking, line, registration) -> None:
        self.event, self.booking, self.line, self.registration = event, booking, line, registration


@pytest.fixture
def ctx(db: Session, person: User, event: Event) -> Ctx:
    staff = make_user(db, UserRole.VENUE_STAFF)
    booking = make_venue_booking(db, event=event, venue=make_venue(db), user=person)
    line = make_line(db, event=event, equipment_type=make_type(db, "Projector"), requested_by=person, status=EquipmentLineStatus.PENDING)
    registration = make_registration(db, event, make_attendee(db))
    assert staff is not None
    return Ctx(event, booking, line, registration)


def test_tc_us31_01_every_notifier_method_is_in_this_table() -> None:
    methods = {name for name in Notifier.__dict__ if not name.startswith("_")}
    assert {name for name, *_ in CALLS} == methods


@pytest.mark.parametrize("name, build, fragment, how", CALLS, ids=[call[0] for call in CALLS])
def test_tc_us31_02_each_notice_is_kept_for_its_recipient_with_the_event_it_is_about(
    db: Session, person: User, event: Event, ctx: Ctx, name: str, build, fragment: str, how: str
) -> None:
    notifier, inner = recorder(db)

    getattr(notifier, name)(email="olivia.organiser@smu.edu.sg", **build(ctx))

    [row] = kept(db, person)
    assert (row.kind, row.event_id, row.event_name, row.read_at) == (name, event.id, "Alumni night", None)
    assert fragment in row.message
    # Still logged through the wrapped notifier, with the same call.
    assert sum(len(calls) for calls in vars(inner).values() if isinstance(calls, list)) == 1


def test_tc_us31_03_the_same_address_in_another_case_is_the_same_person(db: Session, person: User, event: Event) -> None:
    notifier, _ = recorder(db)

    notifier.request_decided(email="OLIVIA.ORGANISER@SMU.EDU.SG", request_reference=REFERENCE, event_name="Alumni night", decision="approved", reason=None)

    assert [row.kind for row in kept(db, person)] == ["request_decided"]


def test_tc_us31_04_an_address_no_user_holds_is_logged_and_skipped(
    db: Session, event: Event, caplog: pytest.LogCaptureFixture
) -> None:
    notifier, inner = recorder(db)

    with caplog.at_level(logging.WARNING):
        notifier.request_decided(email="nobody@example.com", request_reference=REFERENCE, event_name="Alumni night", decision="approved", reason=None)

    assert db.scalars(select(Notification)).all() == []
    assert len(inner.request_decisions) == 1
    assert "no user holds nobody@example.com" in caplog.text


def test_tc_us31_05_a_notice_for_an_event_that_cant_be_found_is_kept_without_one(db: Session, person: User) -> None:
    notifier, _ = recorder(db)

    notifier.request_decided(email=person.email, request_reference="ER-0000-000000", event_name="Gone", decision="approved", reason=None)

    [row] = kept(db, person)
    assert (row.event_id, row.event_name) == (None, "Gone")


def test_tc_us31_06_a_failure_to_record_is_logged_and_never_raised(
    db: Session, person: User, caplog: pytest.LogCaptureFixture
) -> None:
    inner = FakeNotifier()

    def broken() -> Session:
        raise RuntimeError("database unavailable")

    notifier = RecordingNotifier(inner, broken)
    with caplog.at_level(logging.ERROR):
        notifier.request_decided(email=person.email, request_reference=REFERENCE, event_name="Alumni night", decision="approved", reason=None)

    assert len(inner.request_decisions) == 1
    assert "could not open a session to record the request_decided notice" in caplog.text


def test_tc_us31_07_a_row_the_database_refuses_is_logged_and_the_session_stays_usable(
    db: Session, person: User, event: Event, caplog: pytest.LogCaptureFixture
) -> None:
    db.commit()  # the refused insert is rolled back, so what the test built must already be committed
    notifier, _ = recorder(db)

    with caplog.at_level(logging.ERROR):
        # A blank sentence breaks notifications_kind_and_message_not_blank.
        notifier._record("request_decided", email=person.email, event_name="Alumni night", message="  ")
    notifier.request_decided(email=person.email, request_reference=REFERENCE, event_name="Alumni night", decision="approved", reason=None)

    assert "could not record the request_decided notice" in caplog.text
    assert [row.kind for row in kept(db, person)] == ["request_decided"]


def test_tc_us31_08_the_app_uses_the_recording_notifier_over_the_logging_one() -> None:
    notifier = get_notifier()

    assert isinstance(notifier, RecordingNotifier)
    assert isinstance(notifier._delegate, LoggingNotifier)


async def test_tc_us31_09_an_assignment_reaches_the_coordinators_and_organisers_notifications(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    coordinator = make_user(db, UserRole.COORDINATOR)
    coordinator.full_name = "Casey Tan"
    event = make_request(db, organiser, EventStatus.SUBMITTED)
    event.name = "Alumni night"
    event.request_reference = f"ER-2026-{uuid.uuid4().int % 900000 + 100000}"
    db.flush()
    notifier, _ = recorder(db)
    app.dependency_overrides[get_notifier] = lambda: notifier

    assert (await assign(client, lead, event.id, coordinator.id)).status_code == 200

    for user, fragment in ((coordinator, "You were assigned"), (organiser, "Casey Tan was assigned")):
        response = await client.get("/api/v1/me/notifications", headers=auth(user))
        [row] = response.json()["notifications"]
        assert (row["kind"], row["event_id"], row["event_name"], row["read"]) == ("assignment_made", str(event.id), "Alumni night", False)
        assert fragment in row["message"]
    assert (await client.get("/api/v1/me/notifications", headers=auth(lead))).json()["notifications"] == []


def test_tc_us31_10_recording_never_waits_on_a_lock_the_caller_holds(engine) -> None:
    """A waitlist offer goes out inside the withdrawal's transaction, which holds the event's row lock. Recording
    from its own session must not wait for it, or the request waits on itself (found by the attendee E2E)."""
    import time

    from sqlalchemy import delete, text

    email = f"{uuid.uuid4().hex}@smu.edu.sg"
    reference = f"ER-2026-{uuid.uuid4().int % 900000 + 100000}"
    with Session(engine) as setup:
        user = User(email=email, roles=[UserRole.ORGANISER])
        setup.add(user)
        setup.flush()
        event = Event(name="Locked event", status=EventStatus.APPROVED, registration_enabled=False, created_by_user_id=user.id, request_reference=reference)
        setup.add(event)
        setup.commit()
        event_id, user_id = event.id, user.id
    holder = engine.connect()
    transaction = holder.begin()
    try:
        holder.execute(text("select id from events where id = :id for update"), {"id": event_id})

        started = time.monotonic()
        RecordingNotifier(FakeNotifier(), lambda: Session(engine)).request_decided(
            email=email, request_reference=reference, event_name="Locked event", decision="approved", reason=None
        )
        elapsed = time.monotonic() - started

        with Session(engine) as check:
            [row] = check.scalars(select(Notification).where(Notification.user_id == user_id)).all()
        assert (row.event_id, row.kind) == (event_id, "request_decided")
        assert elapsed < 2
    finally:
        transaction.rollback()
        holder.close()
        with Session(engine) as cleanup:
            cleanup.execute(delete(Notification).where(Notification.user_id == user_id))
            cleanup.execute(delete(Event).where(Event.id == event_id))
            cleanup.execute(delete(User).where(User.id == user_id))
            cleanup.commit()
