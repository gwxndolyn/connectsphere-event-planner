"""US16a sign up, log in and log out, PR 1 (SCRUM-101): the columns that link a `users` row to its
Supabase Auth account. Token checking (SCRUM-102) and sign-up (SCRUM-103) use them in later PRs."""

import uuid
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.user.models import User, UserRole
from tests.conftest import BACKEND_DIR

REVISION = "20261015_1200_us16a_auth_link"
PREVIOUS_REVISION = "20261013_1200_us20_venues"


def alembic_config(connection: Connection) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def migration_connection(engine: Engine) -> Generator[Connection, None, None]:
    """A connection whose schema changes are rolled back afterwards: Postgres DDL is transactional,
    so a test can migrate up and down without disturbing the schema the rest of the suite uses."""
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


def make_user(db: Session, **fields) -> User:
    user = User(email=f"{uuid.uuid4().hex}@smu.edu.sg", role=UserRole.ORGANISER, **fields)
    db.add(user)
    db.flush()
    return user


def test_tc_us16a_01_users_gain_nullable_auth_link_and_full_name(engine: Engine) -> None:
    columns = {column["name"]: column for column in inspect(engine).get_columns("users")}

    assert str(columns["auth_user_id"]["type"]) == "UUID"
    assert columns["auth_user_id"]["nullable"] is True
    assert str(columns["full_name"]["type"]) == "TEXT"
    assert columns["full_name"]["nullable"] is True
    unique = {tuple(constraint["column_names"]) for constraint in inspect(engine).get_unique_constraints("users")}
    assert ("auth_user_id",) in unique


def test_tc_us16a_01_existing_users_are_unchanged_by_the_upgrade(migration_connection: Connection) -> None:
    config = alembic_config(migration_connection)
    command.downgrade(config, PREVIOUS_REVISION)
    user_id = uuid.uuid4()
    migration_connection.execute(
        text("insert into users (id, email, role) values (:id, 'existing@smu.edu.sg', 'coordinator')"),
        {"id": user_id},
    )

    command.upgrade(config, "head")

    row = migration_connection.execute(
        text("select email, role::text, is_active, auth_user_id, full_name from users where id = :id"),
        {"id": user_id},
    ).one()
    assert tuple(row) == ("existing@smu.edu.sg", "coordinator", True, None, None)


def test_tc_us16a_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    assert ScriptDirectory.from_config(config).get_heads() == [REVISION]


def test_tc_us16a_02_two_users_cannot_share_an_auth_account(db: Session) -> None:
    auth_user_id = uuid.uuid4()
    make_user(db, auth_user_id=auth_user_id)

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_user(db, auth_user_id=auth_user_id)

    assert raised.value.orig.diag.constraint_name == "users_auth_user_id_key"


def test_tc_us16a_02_many_users_can_be_unlinked(db: Session) -> None:
    """Seeded users have no Supabase account until they first log in, so null must not collide."""
    first = make_user(db)
    second = make_user(db)

    assert first.auth_user_id is None and second.auth_user_id is None


@pytest.mark.parametrize(
    "column",
    ["auth_user_id", "full_name"],
)
def test_tc_us16a_03_downgrade_refuses_to_discard_account_data(
    migration_connection: Connection, column: str
) -> None:
    value = uuid.uuid4() if column == "auth_user_id" else "Calvin Ng"
    migration_connection.execute(
        text(f"insert into users (email, role, {column}) values ('linked@smu.edu.sg', 'attendee', :value)"),
        {"value": value},
    )

    with pytest.raises(RuntimeError, match="Refusing lossy downgrade"):
        command.downgrade(alembic_config(migration_connection), PREVIOUS_REVISION)


def test_tc_us16a_03_downgrade_drops_the_columns_when_nothing_is_linked(
    migration_connection: Connection,
) -> None:
    command.downgrade(alembic_config(migration_connection), PREVIOUS_REVISION)

    columns = {column["name"] for column in inspect(migration_connection).get_columns("users")}
    assert not {"auth_user_id", "full_name"} & columns
