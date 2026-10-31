"""US14 Tech support staff, PR 1 (SCRUM-133, story SCRUM-17): who's assigned to an event, and the log of
every assign and unassign (AC 6). The API comes in SCRUM-134; see docs/testing/US14-tech-support-staff.md."""

import uuid

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import TechStaffAssignment
from app.event.models import Event
from app.seed import EQUIPMENT_EVENT, SECOND_TECH_SUPPORT_EMAIL, SECOND_TECH_SUPPORT_NAME, seed, seed_id
from app.user.models import User, UserRole
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event, make_user

REVISION = "20261107_1200_us14_tech_staff"


def assign(db: Session, event: Event | None = None, staff: User | None = None, **overrides) -> TechStaffAssignment:
    coordinator = make_user(db, UserRole.COORDINATOR)
    fields = {
        "event_id": (event or make_event(db, coordinator_id=coordinator.id)).id,
        "staff_user_id": (staff or make_user(db, UserRole.TECH_SUPPORT)).id,
        "assigned_by_user_id": coordinator.id,
    }
    assignment = TechStaffAssignment(**(fields | overrides))
    db.add(assignment)
    db.flush()
    return assignment


def test_tc_us14_01_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("tech_staff_assignments")} == {
        "id",
        "event_id",
        "staff_user_id",
        "assigned_by_user_id",
        "assigned_at",
        "unassigned_by_user_id",
        "unassigned_at",
    }
    rls = db.scalar(text("SELECT relrowsecurity FROM pg_class WHERE oid = 'tech_staff_assignments'::regclass"))
    assert rls is True
    indexes = {index["name"]: index for index in inspector.get_indexes("tech_staff_assignments")}
    assert indexes["tech_staff_assignments_one_active"]["column_names"] == ["event_id", "staff_user_id"]
    assert indexes["ix_tech_staff_assignments_active_staff"]["column_names"] == ["staff_user_id"]


def test_tc_us14_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert REVISION in {revision.revision for revision in script.walk_revisions()}


def test_tc_us14_01_an_assignment_records_who_and_when(db: Session) -> None:
    assignment = assign(db)
    db.expire(assignment)

    stored = db.get(TechStaffAssignment, assignment.id)
    assert stored.assigned_at is not None
    assert (stored.unassigned_at, stored.unassigned_by_user_id) == (None, None)


@pytest.mark.parametrize("field", ["event_id", "staff_user_id", "assigned_by_user_id"])
def test_tc_us14_02_unknown_event_or_users_are_refused(db: Session, field: str) -> None:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            assign(db, **{field: uuid.uuid4()})

    assert raised.value.orig.diag.constraint_name == f"tech_staff_assignments_{field}_fkey"


@pytest.mark.parametrize("half", ["unassigned_at", "unassigned_by_user_id"], ids=["time only", "who only"])
def test_tc_us14_02_an_unassign_is_both_who_and_when(db: Session, half: str) -> None:
    value = NOW if half == "unassigned_at" else make_user(db, UserRole.COORDINATOR).id

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            assign(db, **{half: value})

    assert raised.value.orig.diag.constraint_name == "tech_staff_assignments_unassigned_consistent"


def test_tc_us14_02_one_active_assignment_per_person_per_event_then_again_after_unassign(db: Session) -> None:
    first = assign(db)
    event, staff = db.get(Event, first.event_id), db.get(User, first.staff_user_id)

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            assign(db, event=event, staff=staff)
    assert raised.value.orig.diag.constraint_name == "tech_staff_assignments_one_active"

    first.unassigned_at, first.unassigned_by_user_id = NOW, make_user(db, UserRole.COORDINATOR).id
    db.flush()
    again = assign(db, event=event, staff=staff)
    assert again.id != first.id
    # The log: both rows stay, the first with its unassign stamp (AC 6).
    assert db.scalar(select(func.count()).where(TechStaffAssignment.event_id == event.id)) == 2


def test_tc_us14_03_seed_adds_a_second_tech_support_user(db: Session) -> None:
    seed(db, now=NOW)
    second = db.get(User, seed_id("user", "tech-support-2"))

    assert (second.email, list(second.roles), second.is_active) == (
        SECOND_TECH_SUPPORT_EMAIL,
        [UserRole.TECH_SUPPORT],
        True,
    )
    assert second.full_name == SECOND_TECH_SUPPORT_NAME

    count = db.scalar(select(func.count()).select_from(User).where(User.roles.any(UserRole.TECH_SUPPORT)))
    seed(db, now=NOW)
    assert db.scalar(select(func.count()).select_from(User).where(User.roles.any(UserRole.TECH_SUPPORT))) == count


def test_tc_us14_03_reseed_clears_the_demo_events_assignments_only(db: Session) -> None:
    seed(db, now=NOW)
    demo = db.get(Event, seed_id("event", EQUIPMENT_EVENT.slug))
    terry = db.get(User, seed_id("user", "tech-support"))
    assign(db, event=demo, staff=terry)
    other = assign(db, staff=terry)

    seed(db, now=NOW)

    assert db.scalar(select(func.count()).where(TechStaffAssignment.event_id == demo.id)) == 0
    assert db.get(TechStaffAssignment, other.id) is not None
