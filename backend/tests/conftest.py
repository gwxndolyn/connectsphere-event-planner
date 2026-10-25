import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import date, datetime
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
from app.notification.service import get_notifier
from app.user.auth import auth_dev_headers_enabled
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


class FakeNotifier:
    """Records calls instead of sending. `fail = True` makes every call raise (TC-US7-15)."""

    def __init__(self) -> None:
        self.offers: list[dict[str, object]] = []
        self.clarifications: list[dict[str, object]] = []
        self.venue_bookings: list[dict[str, object]] = []
        self.booking_decisions: list[dict[str, object]] = []
        self.queued: list[dict[str, object]] = []
        self.assignments: list[dict[str, object]] = []
        self.equipment_reviews: list[dict[str, object]] = []
        self.request_decisions: list[dict[str, object]] = []
        self.fail = False

    def waitlist_offer(
        self, *, email: str, event_name: str, expires_at: datetime, registration_id: uuid.UUID
    ) -> None:
        if self.fail:
            raise RuntimeError("mail server unavailable")
        self.offers.append(
            {"email": email, "event_name": event_name, "expires_at": expires_at, "registration_id": registration_id}
        )

    def clarification_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        round: int,
        sections: list[str],
        comment: str,
    ) -> None:
        self.clarifications.append(
            {
                "email": email,
                "request_reference": request_reference,
                "event_name": event_name,
                "round": round,
                "sections": sections,
                "comment": comment,
            }
        )
        if self.fail:
            raise RuntimeError("mail server unavailable")

    def venue_booking_requested(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        if self.fail:
            raise RuntimeError("mail server unavailable")
        self.venue_bookings.append(
            {
                "email": email,
                "booking_id": booking_id,
                "event_name": event_name,
                "venue_name": venue_name,
                "starts_at": starts_at,
                "ends_at": ends_at,
            }
        )

    def venue_booking_decided(self, **call: object) -> None:
        if self.fail:
            raise RuntimeError("mail server unavailable")
        self.booking_decisions.append(call)

    def request_queued(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        organiser_name: str,
        preferred_dates: list[date],
    ) -> None:
        self.queued.append(
            {
                "email": email,
                "request_reference": request_reference,
                "event_name": event_name,
                "organiser_name": organiser_name,
                "preferred_dates": preferred_dates,
            }
        )
        if self.fail:
            raise RuntimeError("mail server unavailable")

    def assignment_made(
        self,
        *,
        email: str,
        recipient: str,
        request_reference: str,
        event_name: str,
        coordinator_name: str,
        event_dates: list[date],
    ) -> None:
        self.assignments.append(
            {
                "email": email,
                "recipient": recipient,
                "request_reference": request_reference,
                "event_name": event_name,
                "coordinator_name": coordinator_name,
                "event_dates": event_dates,
            }
        )
        if self.fail:
            raise RuntimeError("mail server unavailable")

    def equipment_line_reviewed(
        self,
        *,
        email: str,
        line_id: uuid.UUID,
        event_name: str,
        equipment_type: str,
        quantity: int,
        decision: str,
        note: str | None,
    ) -> None:
        self.equipment_reviews.append(
            {
                "email": email,
                "line_id": line_id,
                "event_name": event_name,
                "equipment_type": equipment_type,
                "quantity": quantity,
                "decision": decision,
                "note": note,
            }
        )
        if self.fail:
            raise RuntimeError("mail server unavailable")

    def request_decided(self, **call: object) -> None:
        if self.fail:
            raise RuntimeError("mail server unavailable")
        self.request_decisions.append(call)


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
async def client(db: Session, notifier: FakeNotifier) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_notifier] = lambda: notifier
    # The existing tests identify callers with the X-User-Id / X-Attendee-Id stubs, as local dev and
    # CI E2E do (TC-US16A-15). Token tests use their own clients (tests/user/test_token_identity.py).
    app.dependency_overrides[auth_dev_headers_enabled] = lambda: True
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
