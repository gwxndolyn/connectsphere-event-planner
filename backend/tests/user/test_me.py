"""US16a, PR 5 (SCRUM-105): GET /api/v1/me tells the login page who is logged in, so it can show the
role's home screen (AC 2)."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.user.models import User, UserRole
from app.user.schemas import MeOut, ProfileOut
from tests.tokens import api_client, bearer, make_token

pytestmark = pytest.mark.anyio

ME = "/api/v1/me"


@pytest.fixture
async def client(db: Session, notifier) -> AsyncGenerator[AsyncClient, None]:
    async with api_client(db, notifier) as client:
        yield client


def make_user(db: Session, role: UserRole, **fields) -> User:
    user = User(email=f"{uuid.uuid4().hex[:12]}@smu.edu.sg", roles=[role], auth_user_id=uuid.uuid4(), **fields)
    db.add(user)
    db.flush()
    return user


@pytest.mark.parametrize("role", [UserRole.ORGANISER, UserRole.COORDINATOR, UserRole.ATTENDEE])
async def test_tc_us16a_51_returns_the_logged_in_users_profile(
    client: AsyncClient, db: Session, role: UserRole
) -> None:
    user = make_user(db, role, full_name="Pat Person")

    response = await client.get(ME, headers=bearer(make_token(user.auth_user_id, user.email)))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": user.email,
        "full_name": "Pat Person",
        # Only `roles` since SCRUM-121 (TC-US16B-27).
        "roles": [role.value],
    }


async def test_tc_us16a_51_a_user_without_a_name_gets_null(client: AsyncClient, db: Session) -> None:
    user = make_user(db, UserRole.COORDINATOR)

    response = await client.get(ME, headers=bearer(make_token(user.auth_user_id, user.email)))

    assert response.status_code == 200
    assert response.json()["full_name"] is None


async def test_tc_us16a_51_an_inactive_user_is_forbidden(client: AsyncClient, db: Session) -> None:
    # The frontend shows its own message for this one, so the body must stay FORBIDDEN (PR #62 review).
    user = make_user(db, UserRole.ORGANISER, full_name="Pat Person", is_active=False)

    response = await client.get(ME, headers=bearer(make_token(user.auth_user_id, user.email)))

    assert (response.status_code, response.json()) == (403, {"code": "FORBIDDEN"})


def test_tc_us16a_51_only_me_allows_a_missing_name() -> None:
    # POST /auth/profile always sets the name; GET /me can return a user without one (PR #62 review).
    assert MeOut.model_fields["full_name"].annotation == str | None
    assert ProfileOut.model_fields["full_name"].annotation is str


async def test_tc_us16a_51_no_profile_yet_is_profile_required(client: AsyncClient) -> None:
    response = await client.get(ME, headers=bearer(make_token(uuid.uuid4(), "brand.new@smu.edu.sg")))

    assert (response.status_code, response.json()) == (403, {"code": "PROFILE_REQUIRED"})


async def test_tc_us16a_51_no_token_is_unauthenticated(client: AsyncClient) -> None:
    response = await client.get(ME)

    assert (response.status_code, response.json()) == (401, {"code": "UNAUTHENTICATED"})
