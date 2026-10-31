"""US27 equipment reservations, PR 1 (SCRUM-130, story SCRUM-95): each reservation fulfils one approved
request line, for that line's event and type, and records who reserved it. Reserving and releasing come
in SCRUM-131; see docs/testing/US27-equipment-reservations.md."""

import uuid
from datetime import timedelta

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentReservation, EquipmentType
from app.event.models import Event
from app.seed import EQUIPMENT_EVENT, seed, seed_id
from app.user.models import User, UserRole
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event, make_user

REVISION = "20261104_1200_us27_reservations"


def make_type(db: Session) -> EquipmentType:
    equipment_type = EquipmentType(name=f"Test type {uuid.uuid4().hex[:8]}", total_quantity=10)
    db.add(equipment_type)
    db.flush()
    return equipment_type


def make_approved_line(db: Session, event: Event | None = None) -> EquipmentRequestLine:
    coordinator = make_user(db, UserRole.COORDINATOR)
    line = EquipmentRequestLine(
        event_id=(event or make_event(db, coordinator_id=coordinator.id)).id,
        equipment_type_id=make_type(db).id,
        quantity=2,
        requested_by_user_id=coordinator.id,
        status=EquipmentLineStatus.APPROVED,
        reviewed_by_user_id=make_user(db, UserRole.TECH_SUPPORT).id,
        reviewed_at=NOW - timedelta(hours=1),
    )
    db.add(line)
    db.flush()
    return line


def reserve(db: Session, line: EquipmentRequestLine, by: User | None = None, **overrides) -> EquipmentReservation:
    fields = {
        "request_line_id": line.id,
        "event_id": line.event_id,
        "equipment_type_id": line.equipment_type_id,
        "quantity": line.quantity,
        "reserved_by_user_id": (by or make_user(db, UserRole.TECH_SUPPORT)).id,
    }
    reservation = EquipmentReservation(**(fields | overrides))
    db.add(reservation)
    db.flush()
    return reservation


def test_tc_us27_01_schema_is_installed(engine) -> None:
    columns = {column["name"]: column for column in inspect(engine).get_columns("equipment_reservations")}

    assert columns["request_line_id"]["nullable"] is False
    assert columns["reserved_by_user_id"]["nullable"] is False
    unique = {tuple(c["column_names"]) for c in inspect(engine).get_unique_constraints("equipment_reservations")}
    assert ("request_line_id",) in unique


def test_tc_us27_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert REVISION in {revision.revision for revision in script.walk_revisions()}


def test_tc_us27_01_a_reservation_fulfils_its_line(db: Session) -> None:
    line = make_approved_line(db)
    tech = make_user(db, UserRole.TECH_SUPPORT)

    reservation = reserve(db, line, by=tech)

    assert (reservation.request_line_id, reservation.reserved_by_user_id) == (line.id, tech.id)


@pytest.mark.parametrize("field", ["event_id", "equipment_type_id"])
def test_tc_us27_02_a_reservation_cannot_disagree_with_its_line(db: Session, field: str) -> None:
    line = make_approved_line(db)
    other = {"event_id": make_event(db).id, "equipment_type_id": make_type(db).id}[field]

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            reserve(db, line, **{field: other})

    assert raised.value.orig.diag.constraint_name == "equipment_reservations_line_fkey"


def test_tc_us27_02_one_reservation_per_line(db: Session) -> None:
    line = make_approved_line(db)
    reserve(db, line)

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            reserve(db, line)

    assert raised.value.orig.diag.constraint_name == "equipment_reservations_request_line_id_key"


def test_tc_us27_03_an_unknown_line_is_refused(db: Session) -> None:
    line = make_approved_line(db)

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            reserve(db, line, request_line_id=uuid.uuid4())

    assert raised.value.orig.diag.constraint_name == "equipment_reservations_line_fkey"


def test_tc_us27_03_an_unknown_user_is_refused(db: Session) -> None:
    line = make_approved_line(db)

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            reserve(db, line, reserved_by_user_id=uuid.uuid4())

    assert raised.value.orig.diag.constraint_name == "equipment_reservations_reserved_by_user_id_fkey"


def test_tc_us27_04_reseed_removes_the_demo_events_reservations_with_its_lines(db: Session) -> None:
    seed(db, now=NOW)
    demo = db.get(Event, seed_id("event", EQUIPMENT_EVENT.slug))
    demo_line = make_approved_line(db, event=demo)
    reserve(db, demo_line)
    other_line = make_approved_line(db)
    other = reserve(db, other_line)

    seed(db, now=NOW)

    assert db.scalar(select(func.count()).where(EquipmentReservation.event_id == demo.id)) == 0
    assert db.scalar(select(func.count()).where(EquipmentRequestLine.event_id == demo.id)) == 0
    assert db.get(EquipmentReservation, other.id) is not None
    assert db.get(EquipmentRequestLine, other_line.id) is not None
