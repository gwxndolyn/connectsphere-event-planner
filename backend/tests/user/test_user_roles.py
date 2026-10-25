"""US16b role-based access, PR 1 (SCRUM-119, story SCRUM-82): a user holds a list of roles (D45),
the API checks every role a user holds (D46), `venue_staff` replaces D19's `operations_manager`
stand-in (D49), and the seed adds a Safety officer and a two-role user (D50). Scoping and the
self-decision rule are PR 2's (SCRUM-120); the role switcher is PR 3's (SCRUM-121). See
docs/testing/US16b-role-based-access.md."""

import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import timedelta

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import AsyncClient
from sqlalchemy import Connection, Engine, func, inspect, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import EventStatus
from app.seed import (
    ATTENDEES,
    EVENT_COORDINATOR_LEAD_EMAILS,
    MULTI_ROLE_EMAIL,
    SAFETY_OFFICER_EMAIL,
    SEEDED_LOGIN_EMAILS,
    seed,
    seed_id,
)
from app.user.models import User, UserRole
from tests.conftest import BACKEND_DIR, FakeNotifier
from tests.event.test_event_requests import complete_request
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking
from tests.tokens import api_client, bearer, make_token

pytestmark = pytest.mark.anyio

REVISION = "20261027_1200_us16b_roles"
PREVIOUS_REVISION = "20261026_1200_us10d_history"


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def alembic_config(connection: Connection) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def migration_connection(engine: Engine) -> Generator[Connection, None, None]:
    """Schema changes rolled back afterwards (Postgres DDL is transactional), as in
    tests/user/test_auth_link_schema.py."""
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


@pytest.fixture
async def token_client(db: Session, notifier: FakeNotifier) -> AsyncGenerator[AsyncClient, None]:
    async with api_client(db, notifier) as client:
        yield client


def stored_roles(connection: Connection, email: str) -> list[str]:
    return list(connection.execute(text("select roles::text[] from users where email = :e"), {"e": email}).scalar_one())


# --- TC-US16B-01 the schema ---


def test_tc_us16b_01_users_hold_a_list_of_roles(engine: Engine, db: Session) -> None:
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("users")}

    assert "role" not in columns
    assert isinstance(columns["roles"]["type"], ARRAY)
    assert columns["roles"]["nullable"] is False
    checks = {check["name"] for check in inspector.get_check_constraints("users")}
    assert {"users_roles_not_empty", "users_roles_no_repeats"} <= checks
    values = db.scalars(text("select unnest(enum_range(null::user_role))::text")).all()
    assert {"venue_staff", "safety_officer"} <= set(values)
    assert db.scalar(text("select relrowsecurity from pg_class where oid = 'users'::regclass")) is True


def test_tc_us16b_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert REVISION in {revision.revision for revision in script.walk_revisions()}


def test_tc_us16b_01_operations_manager_is_no_longer_a_role_the_app_knows() -> None:
    """D49: the value stays in the database type (Postgres can't drop one), but nothing uses it."""
    assert "operations_manager" not in {role.value for role in UserRole}
    assert {UserRole.VENUE_STAFF.value, UserRole.SAFETY_OFFICER.value} == {"venue_staff", "safety_officer"}


# --- TC-US16B-02 the upgrade and the downgrade ---


def test_tc_us16b_02_the_upgrade_moves_each_role_into_the_list(migration_connection: Connection) -> None:
    config = alembic_config(migration_connection)
    command.downgrade(config, PREVIOUS_REVISION)
    old_roles = ["organiser", "coordinator", "coordinator_lead", "operations_manager", "attendee", "tech_support"]
    for role in old_roles:
        migration_connection.execute(
            text("insert into users (email, role) values (:email, cast(:role as user_role))"),
            {"email": f"{role}@upgrade.test", "role": role},
        )

    command.upgrade(config, "head")

    for role in old_roles:
        expected = ["venue_staff"] if role == "operations_manager" else [role]
        assert stored_roles(migration_connection, f"{role}@upgrade.test") == expected, role


def test_tc_us16b_02_the_downgrade_restores_one_role(migration_connection: Connection) -> None:
    migration_connection.execute(
        text(
            "insert into users (email, roles) values"
            " ('staff@downgrade.test', '{venue_staff}'), ('organiser@downgrade.test', '{organiser}')"
        )
    )

    command.downgrade(alembic_config(migration_connection), PREVIOUS_REVISION)

    rows = dict(
        migration_connection.execute(
            text("select email, role::text from users where email like '%@downgrade.test'")
        ).all()
    )
    assert rows == {"staff@downgrade.test": "operations_manager", "organiser@downgrade.test": "organiser"}
    columns = {column["name"] for column in inspect(migration_connection).get_columns("users")}
    assert "roles" not in columns


@pytest.mark.parametrize("roles", ["{coordinator,venue_staff}", "{safety_officer}"], ids=["two roles", "safety officer"])
def test_tc_us16b_02_the_downgrade_refuses_what_one_role_cant_hold(
    migration_connection: Connection, roles: str
) -> None:
    migration_connection.execute(text("insert into users (email, roles) values ('lossy@downgrade.test', :roles)"), {"roles": roles})

    with pytest.raises(RuntimeError, match="Refusing lossy downgrade"):
        command.downgrade(alembic_config(migration_connection), PREVIOUS_REVISION)


# --- TC-US16B-03 at least one role, no repeats ---


@pytest.mark.parametrize(
    ("roles", "constraint"),
    [([], "users_roles_not_empty"), ([UserRole.COORDINATOR, UserRole.COORDINATOR], "users_roles_no_repeats")],
    ids=["no roles", "a role twice"],
)
def test_tc_us16b_03_a_user_needs_at_least_one_role_and_no_repeats(
    db: Session, roles: list[UserRole], constraint: str
) -> None:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            db.add(User(email=f"{uuid.uuid4().hex}@smu.edu.sg", roles=roles))
            db.flush()

    assert raised.value.orig.diag.constraint_name == constraint


# --- TC-US16B-04 the seed ---


def test_tc_us16b_04_the_seed_has_one_user_per_role_and_a_two_role_user(db: Session) -> None:
    seed(db, now=NOW)
    expected = {
        "event-organiser": [UserRole.ORGANISER],
        "event-coordinator": [UserRole.COORDINATOR],
        "venue-staff": [UserRole.VENUE_STAFF],
        "tech-support": [UserRole.TECH_SUPPORT],
        "safety-officer": [UserRole.SAFETY_OFFICER],
        "multi-role": [UserRole.COORDINATOR, UserRole.VENUE_STAFF],
        **{email: [UserRole.COORDINATOR_LEAD] for email in EVENT_COORDINATOR_LEAD_EMAILS},
    }

    for slug, roles in expected.items():
        user = db.get(User, seed_id("user", slug))
        assert user is not None, slug
        assert (list(user.roles), user.is_active) == (roles, True), slug
        assert user.full_name, slug
    calvin = db.get(User, seed_id("attendee", ATTENDEES[0]))
    assert (list(calvin.roles), bool(calvin.full_name)) == ([UserRole.ATTENDEE], True)
    assert db.get(User, seed_id("user", "safety-officer")).email == SAFETY_OFFICER_EMAIL
    assert db.get(User, seed_id("user", "multi-role")).email == MULTI_ROLE_EMAIL
    # Each gets a Supabase login like the other seeded users (SCRUM-104).
    assert {SAFETY_OFFICER_EMAIL, MULTI_ROLE_EMAIL} <= set(SEEDED_LOGIN_EMAILS)
    assert db.scalar(text("select count(*) from users where 'operations_manager' = any(roles)")) == 0


def test_tc_us16b_04_reseeding_adds_no_users(db: Session) -> None:
    seed(db, now=NOW)
    before = db.scalar(select(func.count()).select_from(User))

    seed(db, now=NOW)

    assert db.scalar(select(func.count()).select_from(User)) == before


# --- TC-US16B-05 the API checks every role a user holds ---


async def test_tc_us16b_05_a_two_role_user_uses_both_roles_and_no_other(client: AsyncClient, db: Session) -> None:
    both = make_user(db, UserRole.COORDINATOR, UserRole.VENUE_STAFF)

    as_coordinator = await client.get("/api/v1/event-requests", headers=auth(both))
    as_venue_staff = await client.get("/api/v1/venue-bookings/pending", headers=auth(both))
    as_lead = await client.get("/api/v1/event-requests/unassigned", headers=auth(both))

    assert (as_coordinator.status_code, as_venue_staff.status_code) == (200, 200)
    assert as_lead.status_code == 403
    assert as_lead.json() == {"code": "FORBIDDEN"}


# --- TC-US16B-06 Venue Staff is the real role ---


async def test_tc_us16b_06_venue_staff_edit_venues_and_decide_bookings(client: AsyncClient, db: Session) -> None:
    staff = make_user(db, UserRole.VENUE_STAFF)
    coordinator = make_user(db, UserRole.COORDINATOR)
    venue = make_venue(db, name="Hall A")
    event = make_event(db, name="Data Science Summit", status=EventStatus.APPROVED, coordinator_id=coordinator.id)
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator)

    edited = await client.patch(f"/api/v1/venues/{venue.id}", headers=auth(staff), json={"capacity": 45})
    pending = await client.get("/api/v1/venue-bookings/pending", headers=auth(staff))
    approved = await client.post(f"/api/v1/venue-bookings/{booking.id}/approve", headers=auth(staff))

    assert (edited.status_code, pending.status_code, approved.status_code) == (200, 200, 200)
    assert [row["id"] for row in pending.json()["bookings"]] == [str(booking.id)]
    assert approved.json()["status"] == "approved"


# --- TC-US16B-07 /me and sign-up ---


async def test_tc_us16b_07_27_me_lists_every_role_in_the_types_order(token_client: AsyncClient, db: Session) -> None:
    """SCRUM-121 removed the interim `role` once the frontend read `roles` (TC-US16B-27, PR #86 review)."""
    user = User(
        email=f"{uuid.uuid4().hex[:12]}@smu.edu.sg",
        roles=[UserRole.VENUE_STAFF, UserRole.COORDINATOR],
        auth_user_id=uuid.uuid4(),
        full_name="Morgan Multi",
    )
    db.add(user)
    db.flush()

    response = await token_client.get("/api/v1/me", headers=bearer(make_token(user.auth_user_id, user.email)))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "full_name": "Morgan Multi",
        "roles": ["coordinator", "venue_staff"],
    }


@pytest.mark.parametrize("role", ["organiser", "attendee"])
async def test_tc_us16b_07_sign_up_creates_a_list_of_one(token_client: AsyncClient, db: Session, role: str) -> None:
    sub, email = uuid.uuid4(), f"{uuid.uuid4().hex[:12]}@example.com"

    response = await token_client.post(
        "/api/v1/auth/profile", headers=bearer(make_token(sub, email)), json={"full_name": "Pat Person", "role": role}
    )

    assert response.status_code == 201
    assert response.json()["roles"] == [role]
    assert "role" not in response.json()  # TC-US16B-27
    user = db.scalars(select(User).where(User.auth_user_id == sub)).one()
    assert list(user.roles) == [UserRole(role)]


# --- TC-US16B-08 email linking reads every held role ---


@pytest.mark.parametrize(
    "roles",
    [[UserRole.ORGANISER, UserRole.COORDINATOR], [UserRole.VENUE_STAFF], [UserRole.SAFETY_OFFICER]],
    ids=["organiser and coordinator", "venue staff", "safety officer"],
)
async def test_tc_us16b_08_a_user_holding_any_staff_role_is_never_linked_by_email(
    token_client: AsyncClient, db: Session, roles: list[UserRole]
) -> None:
    """SCRUM-102's rule (deviation 20): only an Organiser or Attendee row is linked by email. A row that
    also holds a staff role is linked by the seed only, or the email's owner would take that role."""
    user = User(email=f"{uuid.uuid4().hex[:12]}@smu.edu.sg", roles=roles)
    db.add(user)
    db.flush()

    response = await token_client.get("/api/v1/me", headers=bearer(make_token(uuid.uuid4(), user.email)))

    assert response.status_code == 401
    db.refresh(user)
    assert user.auth_user_id is None


# --- TC-US16B-24 the other role checks read every held role ---


async def test_tc_us16b_24_a_two_role_coordinator_is_in_the_picker_and_can_be_assigned(
    client: AsyncClient, db: Session
) -> None:
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    organiser = make_user(db, UserRole.ORGANISER)
    both = make_user(db, UserRole.COORDINATOR, UserRole.VENUE_STAFF)
    both.full_name = "Morgan Multi"
    db.flush()
    # One event they're already planning, so the count is checked too (D30).
    make_event(db, status=EventStatus.PLANNING, coordinator_id=both.id)
    draft = (await client.post("/api/v1/event-requests", headers=auth(organiser), json=complete_request())).json()
    assert (await client.post(f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser))).status_code == 200

    picker = await client.get("/api/v1/coordinators", headers=auth(lead))
    assigned = await client.post(
        f"/api/v1/event-requests/{draft['id']}/assignment", headers=auth(lead), json={"coordinator_id": str(both.id)}
    )

    rows = {row["id"]: row for row in picker.json()["coordinators"]}
    assert rows[str(both.id)]["name"] == "Morgan Multi"
    assert rows[str(both.id)]["planning_count"] == 1
    assert assigned.status_code == 200
    assert assigned.json()["coordinator"]["id"] == str(both.id)


async def test_tc_us16b_24_leads_and_venue_staff_with_other_roles_still_get_their_notices(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    lead_and_organiser = make_user(db, UserRole.ORGANISER, UserRole.COORDINATOR_LEAD)
    staff_and_tech = make_user(db, UserRole.VENUE_STAFF, UserRole.TECH_SUPPORT)
    coordinator = make_user(db, UserRole.COORDINATOR)
    venue = make_venue(db, name="Hall A")
    event = make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)

    draft = (await client.post("/api/v1/event-requests", headers=auth(organiser), json=complete_request())).json()
    await client.post(f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser))
    start = NOW + timedelta(days=7)
    requested = await client.post(
        "/api/v1/venue-bookings",
        headers=auth(coordinator),
        json={
            "event_id": str(event.id),
            "venue_id": str(venue.id),
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
            "expected_attendees": 30,
            "room_layout": "theatre",
        },
    )

    assert requested.status_code == 201
    assert [call["email"] for call in notifier.queued] == [lead_and_organiser.email]
    assert [call["email"] for call in notifier.venue_bookings] == [staff_and_tech.email]
