import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.main import app
from tests.factories import NOW

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Deliberately NOT settings.database_url: a developer's .env may point at the shared Supabase database.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://connectsphere:connectsphere@localhost:5432/connectsphere_test",
)


def _create_database_if_missing(url: str) -> None:
    parsed = make_url(url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("select 1 from pg_database where datname = :n"), {"n": parsed.database})
        if not exists:
            conn.execute(text(f'create database "{parsed.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    if "supabase" in (make_url(TEST_DATABASE_URL).host or ""):
        pytest.exit("Refusing to run tests against Supabase. Point TEST_DATABASE_URL at a local Postgres.")

    _create_database_if_missing(TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL)
    # Rebuild the schema from the migrations every run, so the tests also prove the migrations work.
    with engine.begin() as conn:
        conn.execute(text("drop schema public cascade"))
        conn.execute(text("create schema public"))
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        config.attributes["connection"] = conn
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """A session inside a transaction that's rolled back after each test. Commits made by the code
    under test only release a savepoint, so nothing leaks between tests."""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(db: Session) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_now] = lambda: NOW
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
