"""US16a, PR 3 (SCRUM-103): POST /api/v1/auth/profile creates a confirmed user's profile on their first
login. Identity comes from the Supabase token, never the body; only Organiser and Attendee can be chosen."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import app
from app.user.models import Attendee, User, UserRole
from tests.tokens import OTHER_KEY, bearer, make_token, token_client

pytestmark = pytest.mark.anyio

PROFILE = "/api/v1/auth/profile"


@pytest.fixture
async def client(db: Session, notifier) -> AsyncGenerator[AsyncClient, None]:
    """Production settings: tokens only, header stubs off."""
    async with token_client(db, notifier) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def dev_client(db: Session, notifier) -> AsyncGenerator[AsyncClient, None]:
    """Header stubs on, as in local dev and CI E2E."""
    async with token_client(db, notifier, dev_headers=True) as client:
        yield client
    app.dependency_overrides.clear()


def new_email() -> str:
    return f"{uuid.uuid4().hex[:12]}@smu.edu.sg"


def users_with(db: Session, email: str) -> int:
    return db.scalar(select(func.count()).select_from(User).where(func.lower(User.email) == email.lower()))


def make_user(db: Session, role: UserRole, **fields) -> User:
    user = User(email=new_email(), role=role, **fields)
    db.add(user)
    db.flush()
    return user


async def test_tc_us16a_18_an_organiser_profile_takes_its_identity_from_the_token(
    client: AsyncClient, db: Session
) -> None:
    sub, email = uuid.uuid4(), new_email()

    response = await client.post(
        PROFILE, headers=bearer(make_token(sub, email)), json={"full_name": "  Olivia Organiser ", "role": "organiser"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {"id": body["id"], "email": email, "full_name": "Olivia Organiser", "role": "organiser"}
    user = db.get(User, uuid.UUID(body["id"]))
    assert (user.auth_user_id, user.email, user.role, user.full_name) == (
        sub,
        email,
        UserRole.ORGANISER,
        "Olivia Organiser",
    )
    assert db.get(Attendee, user.id) is None


async def test_tc_us16a_19_an_attendee_profile_gets_its_attendees_row(client: AsyncClient, db: Session) -> None:
    sub, email = uuid.uuid4(), new_email()
    token = make_token(sub, email)

    response = await client.post(PROFILE, headers=bearer(token), json={"full_name": "Ada Attendee", "role": "attendee"})

    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    attendee = db.get(Attendee, user_id)
    assert attendee is not None and attendee.email == email
    registrations = await client.get("/api/v1/me/registrations", headers=bearer(token))
    assert registrations.status_code == 200
    assert registrations.json() == {"confirmed": [], "waitlisted": [], "offered": []}


@pytest.mark.parametrize("role", ["coordinator", "operations_manager", "venue_staff", "admin"])
async def test_tc_us16a_20_staff_and_unknown_roles_are_refused(client: AsyncClient, db: Session, role: str) -> None:
    email = new_email()

    response = await client.post(
        PROFILE, headers=bearer(make_token(uuid.uuid4(), email)), json={"full_name": "Sam Staff", "role": role}
    )

    assert response.status_code == 422
    assert response.json() == {"code": "INVALID_ROLE"}
    assert users_with(db, email) == 0


async def test_tc_us16a_21_a_seeded_staff_email_is_refused_and_left_unlinked(client: AsyncClient, db: Session) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR)

    response = await client.post(
        PROFILE,
        headers=bearer(make_token(uuid.uuid4(), coordinator.email)),
        json={"full_name": "Not The Coordinator", "role": "organiser"},
    )

    assert response.status_code == 409
    assert response.json() == {"code": "EMAIL_ALREADY_REGISTERED"}
    db.refresh(coordinator)
    assert (coordinator.role, coordinator.auth_user_id, coordinator.full_name) == (UserRole.COORDINATOR, None, None)


async def test_tc_us16a_22_any_existing_email_is_refused_ignoring_case(client: AsyncClient, db: Session) -> None:
    attendee = make_user(db, UserRole.ATTENDEE)

    response = await client.post(
        PROFILE,
        headers=bearer(make_token(uuid.uuid4(), attendee.email.upper())),
        json={"full_name": "Someone Else", "role": "attendee"},
    )

    assert response.status_code == 409
    assert response.json() == {"code": "EMAIL_ALREADY_REGISTERED"}
    assert users_with(db, attendee.email) == 1


async def test_tc_us16a_23_a_second_call_for_the_same_account_is_refused(client: AsyncClient, db: Session) -> None:
    sub, email = uuid.uuid4(), new_email()
    headers = bearer(make_token(sub, email))

    first = await client.post(PROFILE, headers=headers, json={"full_name": "Once", "role": "organiser"})
    second = await client.post(PROFILE, headers=headers, json={"full_name": "Twice", "role": "attendee"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"code": "EMAIL_ALREADY_REGISTERED"}
    assert db.scalar(select(func.count()).select_from(User).where(User.auth_user_id == sub)) == 1


@pytest.mark.parametrize(
    ("body", "missing"),
    [
        ({"role": "organiser"}, ["full_name"]),
        ({"full_name": "   ", "role": "organiser"}, ["full_name"]),
        ({"full_name": "Named"}, ["role"]),
        ({"full_name": "Named", "role": " "}, ["role"]),
        ({}, ["full_name", "role"]),
    ],
    ids=["no name", "blank name", "no role", "blank role", "neither"],
)
async def test_tc_us16a_24_missing_name_or_role_is_listed(
    client: AsyncClient, db: Session, body: dict, missing: list[str]
) -> None:
    email = new_email()

    response = await client.post(PROFILE, headers=bearer(make_token(uuid.uuid4(), email)), json=body)

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": missing}
    assert users_with(db, email) == 0


@pytest.mark.parametrize("field", ["email", "auth_user_id"])
async def test_tc_us16a_25_identity_cannot_come_from_the_body(client: AsyncClient, db: Session, field: str) -> None:
    email = new_email()
    body = {"full_name": "Sneaky", "role": "organiser", field: "victim@smu.edu.sg" if field == "email" else str(uuid.uuid4())}

    response = await client.post(PROFILE, headers=bearer(make_token(uuid.uuid4(), email)), json=body)

    assert response.status_code == 422
    assert users_with(db, email) == 0 and users_with(db, "victim@smu.edu.sg") == 0


async def test_tc_us16a_26_no_token_or_an_invalid_one_is_unauthenticated(client: AsyncClient) -> None:
    body = {"full_name": "Nobody", "role": "attendee"}

    missing = await client.post(PROFILE, json=body)
    forged = await client.post(PROFILE, headers=bearer(make_token(uuid.uuid4(), new_email(), key=OTHER_KEY)), json=body)

    assert (missing.status_code, missing.json()) == (401, {"code": "UNAUTHENTICATED"})
    assert (forged.status_code, forged.json()) == (401, {"code": "UNAUTHENTICATED"})


async def test_tc_us16a_26_the_dev_header_stubs_do_not_create_profiles(dev_client: AsyncClient, db: Session) -> None:
    """Token only: even with AUTH_DEV_HEADERS on, X-User-Id can't stand in for a new account."""
    organiser = make_user(db, UserRole.ORGANISER)

    response = await dev_client.post(
        PROFILE, headers={"X-User-Id": str(organiser.id)}, json={"full_name": "Stub", "role": "attendee"}
    )

    assert response.status_code == 401
