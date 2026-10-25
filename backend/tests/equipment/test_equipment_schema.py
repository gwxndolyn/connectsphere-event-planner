"""US26 equipment requests, PR 1 (SCRUM-108): the equipment catalogue, request lines, the `tech_support`
role and the seed. The API comes in SCRUM-109; see docs/testing/US26-equipment-requests.md."""

import uuid
from datetime import timedelta

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentType
from app.seed import EQUIPMENT_TYPES, TECH_SUPPORT_EMAIL, TECH_SUPPORT_NAME, seed, seed_id
from app.user.models import User, UserRole
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event

REVISION = "20261025_1200_us26_equipment"


def make_type(db: Session, name: str | None = None) -> EquipmentType:
    equipment_type = EquipmentType(name=name or f"Test type {uuid.uuid4().hex[:8]}")
    db.add(equipment_type)
    db.flush()
    return equipment_type


def make_coordinator(db: Session) -> User:
    user = User(email=f"{uuid.uuid4().hex[:12]}@smu.edu.sg", roles=[UserRole.COORDINATOR])
    db.add(user)
    db.flush()
    return user


def make_line(db: Session, **overrides) -> EquipmentRequestLine:
    fields = {
        "event_id": make_event(db).id,
        "equipment_type_id": make_type(db).id,
        "quantity": 2,
        "notes": "Front of the room",
        "requested_by_user_id": make_coordinator(db).id,
    }
    line = EquipmentRequestLine(**(fields | overrides))
    db.add(line)
    db.flush()
    return line


def test_tc_us26_01_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("equipment_types")} == {"id", "name", "created_at"}
    assert {column["name"] for column in inspector.get_columns("equipment_request_lines")} == {
        "id",
        "event_id",
        "equipment_type_id",
        "quantity",
        "notes",
        "status",
        "review_note",
        "requested_by_user_id",
        "reviewed_by_user_id",
        "reviewed_at",
        "created_at",
        "updated_at",
    }
    for table in ("equipment_types", "equipment_request_lines"):
        rls = db.execute(text(f"select relrowsecurity from pg_class where oid = '{table}'::regclass")).scalar_one()
        assert rls is True, table
    roles = set(db.scalars(text("select unnest(enum_range(null::user_role))::text")))
    assert "tech_support" in roles
    # The event page filters by event; Tech Support's queue reads pending lines oldest first (PR #63 review).
    indexes = {index["name"]: index for index in inspector.get_indexes("equipment_request_lines")}
    assert indexes["ix_equipment_request_lines_event_id"]["column_names"] == ["event_id"]
    assert indexes["ix_equipment_request_lines_pending"]["column_names"] == ["created_at"]


def test_tc_us26_01_a_user_can_hold_the_tech_support_role(db: Session) -> None:
    user = User(email=f"{uuid.uuid4().hex[:12]}@smu.edu.sg", roles=[UserRole.TECH_SUPPORT])
    db.add(user)
    db.flush()
    db.expire(user)

    assert list(db.get(User, user.id).roles) == [UserRole.TECH_SUPPORT]


def test_tc_us26_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert REVISION in {revision.revision for revision in script.walk_revisions()}


@pytest.mark.parametrize("quantity", [0, -1])
def test_tc_us26_02_quantity_must_be_positive(db: Session, quantity: int) -> None:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_line(db, quantity=quantity)

    assert raised.value.orig.diag.constraint_name == "equipment_request_lines_quantity_positive"


@pytest.mark.parametrize("field", ["equipment_type_id", "event_id"])
def test_tc_us26_03_type_and_event_must_exist(db: Session, field: str) -> None:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_line(db, **{field: uuid.uuid4()})

    assert raised.value.orig.diag.constraint_name.endswith("_fkey")


def test_tc_us26_03_type_names_are_unique_and_not_blank(db: Session) -> None:
    make_type(db, "Clicker")
    for name, constraint in (("Clicker", "equipment_types_name_key"), ("  ", "equipment_types_name_not_blank")):
        with pytest.raises(IntegrityError) as raised:
            with db.begin_nested():
                make_type(db, name)
        assert raised.value.orig.diag.constraint_name == constraint


def test_tc_us26_03_type_names_are_unique_ignoring_case_and_spaces(db: Session) -> None:
    # `Projector` and ` projector` would both appear in SCRUM-109's catalogue (PR #63 review).
    make_type(db, "Clicker")

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_type(db, " clicker ")

    assert raised.value.orig.diag.constraint_name == "equipment_types_name_lower_unique"


def test_tc_us26_04_a_new_line_is_pending(db: Session) -> None:
    line = make_line(db)
    db.expire(line)

    assert db.get(EquipmentRequestLine, line.id).status is EquipmentLineStatus.PENDING


def test_tc_us26_04_only_the_three_statuses_are_allowed(db: Session) -> None:
    line = make_line(db)

    with pytest.raises(DBAPIError):
        with db.begin_nested():
            db.execute(
                text("update equipment_request_lines set status = 'cancelled' where id = :id"), {"id": line.id}
            )

    assert {status.value for status in EquipmentLineStatus} == {"pending", "approved", "rejected"}


def make_reviewer(db: Session) -> User:
    user = User(email=f"{uuid.uuid4().hex[:12]}@smu.edu.sg", roles=[UserRole.TECH_SUPPORT])
    db.add(user)
    db.flush()
    return user


def test_tc_us26_04_a_reviewed_line_records_who_and_when(db: Session) -> None:
    reviewer = make_reviewer(db)

    for status in (EquipmentLineStatus.APPROVED, EquipmentLineStatus.REJECTED):
        line = make_line(
            db, status=status, reviewed_by_user_id=reviewer.id, reviewed_at=NOW + timedelta(hours=1), review_note="OK"
        )
        assert line.status is status


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"status": EquipmentLineStatus.APPROVED}, "equipment_request_lines_reviewed_consistent"),
        ({"status": EquipmentLineStatus.REJECTED, "reviewed_at": NOW}, "equipment_request_lines_reviewed_consistent"),
        ({"reviewed_at": NOW}, "equipment_request_lines_reviewed_consistent"),
        ({"review_note": "Not yet reviewed"}, "equipment_request_lines_note_only_when_reviewed"),
    ],
    ids=["approved without a reviewer", "rejected without a reviewer", "pending with a time", "pending with a note"],
)
def test_tc_us26_04_status_and_review_fields_must_agree(db: Session, fields: dict, constraint: str) -> None:
    # Like #64's withdrawn_consistent: the review columns can't contradict the status (PR #63 review).
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_line(db, **fields)

    assert raised.value.orig.diag.constraint_name == constraint


def test_tc_us26_04_a_pending_line_cannot_carry_a_reviewer(db: Session) -> None:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_line(db, reviewed_by_user_id=make_reviewer(db).id)

    assert raised.value.orig.diag.constraint_name == "equipment_request_lines_reviewed_consistent"


def test_tc_us26_18_one_live_line_per_type_per_event(db: Session) -> None:
    # D41 (DECISION-PENDING): equipment is tracked by type, so a second pending or approved line for the
    # same type is refused; the coordinator edits the quantity instead (AC 2). A rejected line doesn't
    # count, so the type can be requested again (AC 6: no splitting a request to get part of it).
    first = make_line(db)
    same = {"event_id": first.event_id, "equipment_type_id": first.equipment_type_id}

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_line(db, **same)
    assert raised.value.orig.diag.constraint_name == "equipment_request_lines_one_live_per_type"

    reviewer = make_reviewer(db)
    first.status = EquipmentLineStatus.REJECTED
    first.reviewed_by_user_id = reviewer.id
    first.reviewed_at = NOW
    db.flush()
    again = make_line(db, **same)
    assert again.status is EquipmentLineStatus.PENDING

    # Another event, or another type, is never a duplicate.
    make_line(db, equipment_type_id=first.equipment_type_id)
    make_line(db, event_id=first.event_id, equipment_type_id=make_type(db, "Clicker").id)


def test_tc_us26_05_seed_adds_the_catalogue_and_a_tech_support_user(db: Session) -> None:
    seed(db, now=NOW)
    seeded_ids = [seed_id("equipment-type", name) for name in EQUIPMENT_TYPES]
    types = list(db.scalars(select(EquipmentType).where(EquipmentType.id.in_(seeded_ids))))

    assert sorted(t.name for t in types) == sorted(EQUIPMENT_TYPES)
    staff = db.get(User, seed_id("user", "tech-support"))
    assert (staff.email, list(staff.roles), staff.is_active) == (TECH_SUPPORT_EMAIL, [UserRole.TECH_SUPPORT], True)
    # A name, so the coordinator sees who reviewed a line, not an email (as #68 did for the others).
    assert staff.full_name == TECH_SUPPORT_NAME

    # Idempotent: a second run updates the same rows and adds none.
    count_before = len(list(db.scalars(select(EquipmentType.id))))
    seed(db, now=NOW)
    assert len(list(db.scalars(select(EquipmentType.id)))) == count_before
