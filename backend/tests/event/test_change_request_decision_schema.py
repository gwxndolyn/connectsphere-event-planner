"""US29b review an event change request, PR 1 (SCRUM-141, story SCRUM-98): a change request records its
decision (who, when, and a rejection's reason), the event's history says what each entry is, and a
significant change flags the event's affected arrangements for review (D101) without touching them. The
seed adds Change Request Demo. The endpoints come in PR 2 (SCRUM-142). See
docs/testing/US29b-change-request-review.md."""

import uuid
from collections.abc import Generator
from datetime import timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import (
    EquipmentLineStatus,
    EquipmentRequestLine,
    EquipmentReservation,
    EquipmentType,
)
from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from app.venue.models import VenueBooking, VenueBookingStatus
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

REVISION = "20261113_1200_us29b_decisions"
PREVIOUS_REVISION = "20261112_1200_us9_cancellations"
CHANGE = [{"field": "start_at", "old_value": "2026-10-02T09:00:00+08:00", "new_value": "2026-10-02T10:00:00+08:00"}]


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    return make_event(db, status=EventStatus.CONFIRMED, coordinator_id=coordinator.id)


def insert_request(db: Session, event: Event, requester: User, **values: object) -> uuid.UUID:
    """A change request written as the database holds it, so a test can set any decision columns."""
    request_id = uuid.uuid4()
    columns = {
        "id": request_id,
        "event_id": event.id,
        "requested_by_user_id": requester.id,
        "status": "pending_approval",
        "changes": '[{"field": "start_at", "old_value": "a", "new_value": "b"}]',
        **values,
    }
    names = ", ".join(columns)
    params = ", ".join(f"CAST(:{name} AS jsonb)" if name == "changes" else f":{name}" for name in columns)
    db.execute(text(f"insert into event_change_requests ({names}) values ({params})"), columns)
    return request_id


def insert_flag(db: Session, event_id: uuid.UUID, change_request_id: uuid.UUID, kind: str, **values: object) -> uuid.UUID:
    flag_id = uuid.uuid4()
    columns = {
        "id": flag_id,
        "event_id": event_id,
        "change_request_id": change_request_id,
        "kind": kind,
        "fields": ["start_at"],
        **values,
    }
    names = ", ".join(columns)
    params = ", ".join(f":{name}" for name in columns)
    db.execute(text(f"insert into event_review_flags ({names}) values ({params})"), columns)
    return flag_id


def refused(db: Session, write) -> str:
    """The name of the constraint that refuses `write`, which runs inside a savepoint."""
    with pytest.raises(IntegrityError) as raised, db.begin_nested():
        write()
    return raised.value.orig.diag.constraint_name


def make_line(db: Session, event: Event, coordinator: User, reviewer: User) -> EquipmentRequestLine:
    equipment_type = EquipmentType(name=f"Projector {uuid.uuid4().hex[:6]}", total_quantity=5)
    db.add(equipment_type)
    db.flush()
    line = EquipmentRequestLine(
        event_id=event.id,
        equipment_type_id=equipment_type.id,
        quantity=1,
        status=EquipmentLineStatus.APPROVED,
        requested_by_user_id=coordinator.id,
        reviewed_by_user_id=reviewer.id,
        reviewed_at=NOW,
    )
    db.add(line)
    db.flush()
    return line


# --- TC-US29B-01 a decision is whole: pending has none, decided has who and when ---


def test_tc_us29b_01_decision_columns_exist_and_a_decision_is_whole(
    db: Session, engine: Engine, event: Event, organiser: User, coordinator: User
) -> None:
    columns = {column["name"]: column for column in inspect(engine).get_columns("event_change_requests")}
    assert {"decided_at", "decided_by_user_id", "rejection_reason"} <= set(columns)
    assert all(columns[name]["nullable"] for name in ("decided_at", "decided_by_user_id", "rejection_reason"))
    checks = {check["name"] for check in inspect(engine).get_check_constraints("event_change_requests")}
    assert {
        "event_change_requests_decision_consistent",
        "event_change_requests_rejection_reason_only_when_rejected",
        "event_change_requests_rejection_reason_not_blank",
        "event_change_requests_decider_not_requester",
    } <= checks
    indexes = {index["name"]: index for index in inspect(engine).get_indexes("event_change_requests")}
    assert indexes["ix_event_change_requests_pending"]["column_names"] == ["event_id"]

    decided = {"decided_at": NOW, "decided_by_user_id": coordinator.id}
    assert refused(db, lambda: insert_request(db, event, organiser, **decided)) == "event_change_requests_decision_consistent"
    assert refused(db, lambda: insert_request(db, event, organiser, status="approved")) == "event_change_requests_decision_consistent"
    assert (
        refused(db, lambda: insert_request(db, event, organiser, status="approved", decided_at=NOW))
        == "event_change_requests_decision_consistent"
    )
    # A whole decision is accepted.
    insert_request(db, event, organiser, status="approved", **decided)


# --- TC-US29B-02 only a rejection has a reason, and it isn't blank ---


def test_tc_us29b_02_a_rejection_needs_a_reason_and_nothing_else_has_one(
    db: Session, event: Event, organiser: User, coordinator: User
) -> None:
    decided = {"decided_at": NOW, "decided_by_user_id": coordinator.id}
    assert (
        refused(db, lambda: insert_request(db, event, organiser, status="rejected", **decided))
        == "event_change_requests_rejection_reason_only_when_rejected"
    )
    assert (
        refused(db, lambda: insert_request(db, event, organiser, status="rejected", rejection_reason="   ", **decided))
        == "event_change_requests_rejection_reason_not_blank"
    )
    assert (
        refused(db, lambda: insert_request(db, event, organiser, status="approved", rejection_reason="Fine", **decided))
        == "event_change_requests_rejection_reason_only_when_rejected"
    )
    insert_request(db, event, organiser, status="rejected", rejection_reason="The venue is booked that week.", **decided)


# --- TC-US29B-03 no one decides their own request (D51) ---


def test_tc_us29b_03_the_requester_cannot_be_the_decider(db: Session, event: Event, coordinator: User) -> None:
    assert (
        refused(db, lambda: insert_request(db, event, coordinator, status="approved", decided_at=NOW, decided_by_user_id=coordinator.id))
        == "event_change_requests_decider_not_requester"
    )


# --- TC-US29B-04 a flag names one item of its kind, and an item has one open flag ---


def test_tc_us29b_04_a_flag_targets_one_item_of_its_kind_with_one_open_flag_per_item(
    db: Session, engine: Engine, event: Event, organiser: User, coordinator: User
) -> None:
    inspector = inspect(engine)
    checks = {check["name"] for check in inspector.get_check_constraints("event_review_flags")}
    assert {
        "event_review_flags_kind_known",
        "event_review_flags_target_matches_kind",
        "event_review_flags_fields_not_empty",
        "event_review_flags_clearance_consistent",
        "event_review_flags_note_only_when_cleared",
    } <= checks
    indexes = {index["name"]: index for index in inspector.get_indexes("event_review_flags")}
    for name in (
        "event_review_flags_one_open_per_booking",
        "event_review_flags_one_open_per_line",
        "event_review_flags_one_open_registrations",
    ):
        assert indexes[name]["unique"] is True
    assert indexes["ix_event_review_flags_event_id"]["column_names"] == ["event_id"]
    assert db.scalar(text("select relrowsecurity from pg_class where relname = 'event_review_flags'")) is True

    request = insert_request(db, event, organiser)
    booking = make_venue_booking(db, event=event, venue=make_venue(db), user=coordinator, status=VenueBookingStatus.APPROVED)
    line = make_line(db, event, coordinator, make_user(db, UserRole.TECH_SUPPORT))

    assert refused(db, lambda: insert_flag(db, event.id, request, "venue")) == "event_review_flags_kind_known"
    assert refused(db, lambda: insert_flag(db, event.id, request, "venue_booking")) == "event_review_flags_target_matches_kind"
    assert (
        refused(db, lambda: insert_flag(db, event.id, request, "venue_booking", venue_booking_id=booking.id, equipment_request_line_id=line.id))
        == "event_review_flags_target_matches_kind"
    )
    assert (
        refused(db, lambda: insert_flag(db, event.id, request, "registrations", venue_booking_id=booking.id))
        == "event_review_flags_target_matches_kind"
    )
    assert (
        refused(db, lambda: insert_flag(db, event.id, request, "venue_booking", venue_booking_id=booking.id, fields=[]))
        == "event_review_flags_fields_not_empty"
    )

    first = insert_flag(db, event.id, request, "venue_booking", venue_booking_id=booking.id)
    assert (
        refused(db, lambda: insert_flag(db, event.id, request, "venue_booking", venue_booking_id=booking.id))
        == "event_review_flags_one_open_per_booking"
    )
    insert_flag(db, event.id, request, "equipment_reservation", equipment_request_line_id=line.id)
    assert (
        refused(db, lambda: insert_flag(db, event.id, request, "equipment_reservation", equipment_request_line_id=line.id))
        == "event_review_flags_one_open_per_line"
    )
    insert_flag(db, event.id, request, "registrations")
    assert refused(db, lambda: insert_flag(db, event.id, request, "registrations")) == "event_review_flags_one_open_registrations"

    # Once the first is cleared, the booking can be flagged again by a later change.
    db.execute(
        text("update event_review_flags set cleared_at = :at, cleared_by_user_id = :by where id = :id"),
        {"at": NOW, "by": coordinator.id, "id": first},
    )
    insert_flag(db, event.id, request, "venue_booking", venue_booking_id=booking.id)


# --- TC-US29B-05 clearing is whole, and only a cleared flag has a note ---


def test_tc_us29b_05_a_clearance_is_whole_and_only_a_cleared_flag_has_a_note(
    db: Session, event: Event, organiser: User, coordinator: User
) -> None:
    request = insert_request(db, event, organiser)
    assert (
        refused(db, lambda: insert_flag(db, event.id, request, "registrations", cleared_at=NOW))
        == "event_review_flags_clearance_consistent"
    )
    assert (
        refused(db, lambda: insert_flag(db, event.id, request, "registrations", cleared_note="Checked"))
        == "event_review_flags_note_only_when_cleared"
    )
    assert (
        refused(db, lambda: insert_flag(db, event.id, request, "registrations", cleared_at=NOW, cleared_by_user_id=coordinator.id, cleared_note=" "))
        == "event_review_flags_note_only_when_cleared"
    )
    insert_flag(
        db, event.id, request, "registrations", cleared_at=NOW, cleared_by_user_id=coordinator.id, cleared_note="Attendees emailed."
    )


# --- TC-US29B-06 the history says what each entry is; the migration backfills and refuses lossy downgrades ---


def test_tc_us29b_06_audit_entries_carry_a_known_action(
    db: Session, engine: Engine, event: Event, coordinator: User
) -> None:
    columns = {column["name"]: column for column in inspect(engine).get_columns("event_audit_entries")}
    assert columns["action"]["nullable"] is False
    assert "saved" in str(columns["action"]["default"])

    def write(action: str) -> None:
        db.execute(
            text(
                "insert into event_audit_entries (event_id, user_id, field_name, previous_value, new_value, action) "
                "values (:event, :user, 'name', '\"Old\"', '\"New\"', :action)"
            ),
            {"event": event.id, "user": coordinator.id, "action": action},
        )

    assert refused(db, lambda: write("edited")) == "event_audit_entries_action_known"
    for action in ("saved", "requested", "applied", "decided", "status_changed", "confirmation_cleared", "safety_approval_cleared"):
        write(action)


def alembic_config(connection: Connection) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def migration_connection(engine: Engine) -> Generator[Connection, None, None]:
    """DDL is transactional in Postgres, so migrating down and up here is rolled back afterwards and the
    rest of the suite keeps the schema at head."""
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


def insert_old_rows(connection: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """An event, its coordinator, an organiser and a pending request, plus a plain save and a critical
    save's entry, as the schema before US29b holds them. Returns (event, coordinator, organiser, request)."""
    event_id, coordinator_id, organiser_id, request_id = (uuid.uuid4() for _ in range(4))
    for user_id, role in ((coordinator_id, "coordinator"), (organiser_id, "organiser")):
        connection.execute(
            text("insert into users (id, email, roles) values (:id, :email, CAST(:roles AS user_role[]))"),
            {"id": user_id, "email": f"{user_id.hex}@smu.edu.sg", "roles": "{" + role + "}"},
        )
    connection.execute(text("insert into events (id, status) values (:id, 'approved')"), {"id": event_id})
    connection.execute(
        text(
            "insert into event_change_requests (id, event_id, requested_by_user_id, changes) "
            "values (:id, :event, :user, CAST(:changes AS jsonb))"
        ),
        {"id": request_id, "event": event_id, "user": coordinator_id, "changes": '[{"field": "capacity", "old_value": 80, "new_value": 90}]'},
    )
    for field, request in (("name", None), ("capacity", request_id)):
        connection.execute(
            text(
                "insert into event_audit_entries (event_id, user_id, field_name, previous_value, new_value, change_request_id) "
                "values (:event, :user, :field, '1', '2', :request)"
            ),
            {"event": event_id, "user": coordinator_id, "field": field, "request": request},
        )
    return event_id, coordinator_id, organiser_id, request_id


def test_tc_us29b_06_the_upgrade_marks_existing_entries_and_the_downgrade_refuses_to_lose_decisions(
    migration_connection: Connection,
) -> None:
    config = alembic_config(migration_connection)
    command.downgrade(config, PREVIOUS_REVISION)
    event_id, _, organiser_id, request_id = insert_old_rows(migration_connection)

    command.upgrade(config, REVISION)
    actions = dict(
        migration_connection.execute(
            text("select field_name, action from event_audit_entries where event_id = :event"), {"event": event_id}
        ).all()
    )
    # A plain save stays a save; a critical save's entry is the request, not yet applied (D89).
    assert actions == {"name": "saved", "capacity": "requested"}

    # Nothing decided or flagged yet: the downgrade is clean, and the upgrade runs again.
    command.downgrade(config, PREVIOUS_REVISION)
    command.upgrade(config, REVISION)

    lossy = [
        (
            "update event_change_requests set status = 'rejected', decided_at = now(), "
            "decided_by_user_id = :organiser, rejection_reason = 'No' where id = :request"
        ),
        "insert into event_review_flags (event_id, change_request_id, kind, fields) values (:event, :request, 'registrations', '{start_at}')",
        (
            "insert into event_audit_entries (event_id, user_id, field_name, previous_value, new_value, action) "
            "values (:event, :organiser, 'capacity', '80', '90', 'applied')"
        ),
    ]
    for statement in lossy:
        savepoint = migration_connection.begin_nested()
        migration_connection.execute(
            text(statement), {"event": event_id, "request": request_id, "organiser": organiser_id}
        )
        with pytest.raises(RuntimeError, match="Refusing lossy downgrade"):
            command.downgrade(config, PREVIOUS_REVISION)
        savepoint.rollback()


# --- TC-US29B-07 the seed's Change Request Demo, and a reseed puts it back ---


def test_tc_us29b_07_seed_has_a_change_request_demo_and_a_reseed_resets_it(db: Session) -> None:
    from app.event.models import EventAuditEntry, EventChangeRequest
    from app.seed import (
        CHANGE_REQUEST_EVENT,
        EQUIPMENT_EVENT,
        MULTI_VENUE_EVENT,
        PLANNING_EVENT,
        seed,
        seed_id,
    )

    seed(db, now=NOW)
    demo = db.get(Event, seed_id("event", CHANGE_REQUEST_EVENT.slug))
    coordinator_id = seed_id("user", "event-coordinator")
    organiser_id = seed_id("user", "event-organiser")

    def check_seeded() -> None:
        db.expire_all()
        assert demo.status == EventStatus.CONFIRMED
        assert demo.coordinator_id == coordinator_id and demo.created_by_user_id == organiser_id
        assert demo.confirmed_at is not None and demo.confirmed_by_user_id == coordinator_id
        assert demo.safety_approved_at is not None
        # Off the attendees' board, like the other demos.
        assert demo.registration_enabled is False
        bookings = db.scalars(select(VenueBooking).where(VenueBooking.event_id == demo.id)).all()
        assert [(b.status, b.is_primary) for b in bookings] == [(VenueBookingStatus.APPROVED, True)]
        assert (bookings[0].starts_at, bookings[0].ends_at) == (demo.start_at, demo.end_at)
        lines = db.scalars(select(EquipmentRequestLine).where(EquipmentRequestLine.event_id == demo.id)).all()
        assert [line.status for line in lines] == [EquipmentLineStatus.APPROVED]
        assert db.scalar(select(func.count()).where(EquipmentReservation.request_line_id == lines[0].id)) == 1
        requests = db.scalars(select(EventChangeRequest).where(EventChangeRequest.event_id == demo.id)).all()
        assert len(requests) == 1
        request = requests[0]
        assert request.status.value == "pending_approval"
        assert request.requested_by_user_id == organiser_id and request.reason
        assert [change["field"] for change in request.changes] == ["start_at", "end_at"]
        assert db.scalar(select(func.count()).where(EventAuditEntry.event_id == demo.id)) == 0
        assert db.scalar(text("select count(*) from event_review_flags where event_id = :e"), {"e": demo.id}) == 0

    check_seeded()

    # What the app would do: approve a significant change, which moves the event back to Planning,
    # clears its safety approval and flags its booking, its reservation and its registrations (D101-D103).
    request = db.scalars(select(EventChangeRequest).where(EventChangeRequest.event_id == demo.id)).one()
    db.execute(
        text(
            "update event_change_requests set status = 'approved', decided_at = now(), decided_by_user_id = :c where id = :r"
        ),
        {"c": coordinator_id, "r": request.id},
    )
    demo.status = EventStatus.PLANNING
    demo.confirmed_at = demo.confirmed_by_user_id = None
    demo.safety_approved_at = demo.safety_approved_by_user_id = None
    demo.start_at, demo.end_at = demo.start_at + timedelta(hours=1), demo.end_at + timedelta(hours=1)
    db.flush()
    booking = db.scalars(select(VenueBooking).where(VenueBooking.event_id == demo.id)).one()
    line = db.scalars(select(EquipmentRequestLine).where(EquipmentRequestLine.event_id == demo.id)).one()
    insert_flag(db, demo.id, request.id, "venue_booking", venue_booking_id=booking.id)
    insert_flag(db, demo.id, request.id, "equipment_reservation", equipment_request_line_id=line.id)
    insert_flag(db, demo.id, request.id, "registrations")
    db.execute(
        text(
            "insert into event_audit_entries (event_id, user_id, field_name, previous_value, new_value, change_request_id, action) "
            "values (:e, :c, 'status', '\"confirmed\"', '\"planning\"', :r, 'status_changed')"
        ),
        {"e": demo.id, "c": coordinator_id, "r": request.id},
    )

    # Flags on rows the other demos' resets delete: an app-made Multi-Venue booking, an Equipment
    # Request Demo line and an Event Planning Demo change request.
    multi = db.get(Event, seed_id("event", MULTI_VENUE_EVENT.slug))
    multi_request = insert_request(db, multi, db.get(User, organiser_id))
    breakout = make_venue_booking(db, event=multi, venue=make_venue(db), user=db.get(User, coordinator_id))
    insert_flag(db, multi.id, multi_request, "venue_booking", venue_booking_id=breakout.id)
    equipment_event = db.get(Event, seed_id("event", EQUIPMENT_EVENT.slug))
    equipment_request = insert_request(db, equipment_event, db.get(User, organiser_id))
    equipment_line = make_line(db, equipment_event, db.get(User, coordinator_id), make_user(db, UserRole.TECH_SUPPORT))
    insert_flag(db, equipment_event.id, equipment_request, "equipment_reservation", equipment_request_line_id=equipment_line.id)
    planning = db.get(Event, seed_id("event", PLANNING_EVENT.slug))
    planning_request = insert_request(db, planning, db.get(User, coordinator_id))
    insert_flag(db, planning.id, planning_request, "registrations")
    db.flush()

    # The raw updates above bypassed the session; a real reseed starts with a fresh one.
    db.expire_all()
    seed(db, now=NOW)

    check_seeded()
    for event_id in (multi.id, equipment_event.id, planning.id):
        assert db.scalar(text("select count(*) from event_review_flags where event_id = :e"), {"e": event_id}) == 0
