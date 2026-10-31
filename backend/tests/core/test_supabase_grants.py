"""SCRUM-118: Supabase's anon and authenticated roles get nothing from the app's database objects, even
with the Data API on. `alembic_version` has row level security, and `next_venue_booking_reference()` and
the three sequences are closed to those roles where they exist (Supabase); local and CI have neither."""

import importlib.util
from types import ModuleType

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.user.models import UserRole
from tests.conftest import BACKEND_DIR
from tests.factories import make_event, make_user, make_venue, make_venue_booking

REVISION = "20261106_1200_scrum118_grants"
SEQUENCES = ("attendance_log_id_seq", "event_request_reference_seq", "venue_booking_reference_seq")
SUPABASE_ROLES = ("anon", "authenticated")


def migration() -> ModuleType:
    """The migration module, for the SQL it runs (migrations/versions isn't a package)."""
    path = BACKEND_DIR / "migrations" / "versions" / f"{REVISION}.py"
    spec = importlib.util.spec_from_file_location(REVISION, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def privileges(db: Session, role: str) -> dict[str, bool]:
    held = {"execute": db.scalar(text(f"SELECT has_function_privilege('{role}', 'next_venue_booking_reference()', 'EXECUTE')"))}
    for sequence in SEQUENCES:
        for privilege in ("USAGE", "SELECT"):
            held[f"{sequence} {privilege}"] = db.scalar(
                text(f"SELECT has_sequence_privilege('{role}', '{sequence}', '{privilege}')")
            )
    return held


def test_tc_sec_01_alembic_version_has_row_level_security(db: Session) -> None:
    assert db.scalar(text("SELECT relrowsecurity FROM pg_class WHERE oid = 'alembic_version'::regclass")) is True


def test_tc_sec_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert REVISION in {revision.revision for revision in script.walk_revisions()}


def test_tc_sec_02_supabase_roles_lose_the_function_and_sequences(db: Session) -> None:
    # Supabase's roles, with the grants Supabase gives them by default; created inside the test's own
    # transaction, which is rolled back afterwards.
    for role in SUPABASE_ROLES:
        db.execute(text(f"CREATE ROLE {role} NOLOGIN"))
        db.execute(text(f"GRANT EXECUTE ON FUNCTION next_venue_booking_reference() TO {role}"))
        db.execute(text(f"GRANT USAGE, SELECT ON SEQUENCE {', '.join(SEQUENCES)} TO {role}"))
        assert all(privileges(db, role).values()), role

    db.execute(text(migration().HARDEN))

    for role in SUPABASE_ROLES:
        assert not any(privileges(db, role).values()), role
    # The backend's own role still can, and a new booking still gets its VB- reference.
    assert all(privileges(db, db.scalar(text("SELECT current_user"))).values())
    coordinator = make_user(db, UserRole.COORDINATOR)
    booking = make_venue_booking(db, event=make_event(db, coordinator_id=coordinator.id), venue=make_venue(db), user=coordinator)
    db.refresh(booking)
    assert booking.reference.startswith("VB-")


def test_tc_sec_03_it_runs_where_the_supabase_roles_dont_exist(db: Session) -> None:
    assert db.scalar(text("SELECT count(*) FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")) == 0

    db.execute(text(migration().HARDEN))

    # PUBLIC, which every role is in, can't call the function either.
    assert db.scalar(
        text("SELECT has_function_privilege('public', 'next_venue_booking_reference()', 'EXECUTE')")
    ) is False


def test_tc_sec_04_the_function_has_a_fixed_search_path(db: Session) -> None:
    # The part of the Security Advisor check (TC-SEC-04, manual on Supabase) a test can make.
    config = db.scalar(text("SELECT proconfig FROM pg_proc WHERE oid = 'next_venue_booking_reference()'::regprocedure"))
    assert config == ["search_path=public"]
