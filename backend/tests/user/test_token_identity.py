"""US16a, PR 2 (SCRUM-102): the backend accepts a Supabase access token in place of the header stubs.
Tokens here are signed with a key pair made for the test run, so nothing reaches the network (§9)."""

import logging
import uuid
from collections.abc import AsyncGenerator

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.user.auth import TokenVerifier, _project_keys, get_token_verifier
from app.user.models import Attendee, User, UserRole
from tests.tokens import ISSUER, OTHER_KEY, api_client, bearer, make_token

pytestmark = pytest.mark.anyio

def make_user(db: Session, role: UserRole = UserRole.ORGANISER, **fields) -> User:
    user = User(email=f"{uuid.uuid4().hex[:12]}@smu.edu.sg", roles=[role], **fields)
    db.add(user)
    db.flush()
    return user


def make_attendee_user(db: Session, **fields) -> User:
    user = make_user(db, UserRole.ATTENDEE, **fields)
    db.add(Attendee(id=user.id, email=user.email))
    db.flush()
    return user


@pytest.fixture
async def token_client(db: Session, notifier) -> AsyncGenerator[AsyncClient, None]:
    """Production settings: tokens only, header stubs off."""
    async with api_client(db, notifier) as client:
        yield client


@pytest.fixture
async def dev_client(db: Session, notifier) -> AsyncGenerator[AsyncClient, None]:
    """Local dev, tests and CI E2E: tokens and header stubs both work."""
    async with api_client(db, notifier, dev_headers=True) as client:
        yield client


async def create_draft(client: AsyncClient, headers: dict[str, str]):
    return await client.post("/api/v1/event-requests", headers=headers, json={"name": "Token test"})


async def test_tc_us16a_05_a_linked_user_is_the_caller(token_client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4())

    response = await create_draft(token_client, bearer(make_token(organiser.auth_user_id, organiser.email)))

    assert response.status_code == 201
    assert response.json()["created_by_user_id"] == str(organiser.id)


async def test_tc_us16a_06_first_login_links_an_unlinked_user_by_email(
    token_client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    sub = uuid.uuid4()

    first = await create_draft(token_client, bearer(make_token(sub, organiser.email)))

    assert first.status_code == 201
    db.refresh(organiser)
    assert organiser.auth_user_id == sub
    # Later calls find the row by auth_user_id, even if the token's email has since changed.
    second = await create_draft(token_client, bearer(make_token(sub, "renamed@smu.edu.sg")))
    assert second.json()["created_by_user_id"] == str(organiser.id)


async def test_tc_us16a_06_email_match_ignores_case(token_client: AsyncClient, db: Session) -> None:
    organiser = make_user(db)
    sub = uuid.uuid4()

    response = await create_draft(token_client, bearer(make_token(sub, organiser.email.upper())))

    assert response.status_code == 201
    db.refresh(organiser)
    assert organiser.auth_user_id == sub


@pytest.mark.parametrize("role", [UserRole.COORDINATOR, UserRole.VENUE_STAFF])
async def test_tc_us16a_06_staff_rows_are_never_linked_by_email(
    token_client: AsyncClient, db: Session, role: UserRole
) -> None:
    """With "Confirm email" off, anyone can create a Supabase account for an unused email. Linking a
    staff row by email would hand them that role, so staff are linked only by the seed (SCRUM-104)."""
    staff = make_user(db, role)

    response = await token_client.get(
        "/api/v1/event-requests", headers=bearer(make_token(uuid.uuid4(), staff.email))
    )

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
    db.refresh(staff)
    assert staff.auth_user_id is None


async def test_tc_us16a_06_an_unverified_email_is_never_linked(token_client: AsyncClient, db: Session) -> None:
    """Review on PR #55: a token for an email nobody confirmed must not take over an existing profile."""
    organiser = make_user(db)

    response = await create_draft(
        token_client, bearer(make_token(uuid.uuid4(), organiser.email, email_verified=False))
    )

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
    db.refresh(organiser)
    assert organiser.auth_user_id is None


async def test_tc_us16a_06_an_inactive_row_is_never_linked(token_client: AsyncClient, db: Session) -> None:
    """Review on PR #55: a deactivated account isn't bound to whoever claims its email first."""
    organiser = make_user(db, is_active=False)

    response = await create_draft(token_client, bearer(make_token(uuid.uuid4(), organiser.email)))

    assert response.status_code == 403
    assert response.json() == {"code": "FORBIDDEN"}
    db.refresh(organiser)
    assert organiser.auth_user_id is None


async def test_tc_us16a_07_an_email_already_linked_to_another_account_is_refused(
    token_client: AsyncClient, db: Session
) -> None:
    original = uuid.uuid4()
    organiser = make_user(db, auth_user_id=original)

    response = await create_draft(token_client, bearer(make_token(uuid.uuid4(), organiser.email)))

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
    db.refresh(organiser)
    assert organiser.auth_user_id == original


async def test_tc_us16a_08_no_token_is_unauthenticated(token_client: AsyncClient) -> None:
    response = await token_client.get("/api/v1/me/event-requests")

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer not-a-jwt"])
async def test_tc_us16a_08_a_malformed_authorization_header_is_unauthenticated(
    token_client: AsyncClient, header: str
) -> None:
    response = await token_client.get("/api/v1/me/event-requests", headers={"Authorization": header})

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}


async def test_tc_us16a_09_an_expired_token_is_unauthenticated(token_client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4())
    token = make_token(organiser.auth_user_id, organiser.email, expires_in=-60)

    response = await token_client.get("/api/v1/me/event-requests", headers=bearer(token))

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}


async def test_tc_us16a_09_a_token_that_just_expired_is_still_accepted(
    token_client: AsyncClient, db: Session
) -> None:
    """10 seconds of leeway, so clock drift between Supabase and the server doesn't reject fresh tokens."""
    organiser = make_user(db, auth_user_id=uuid.uuid4())
    token = make_token(organiser.auth_user_id, organiser.email, expires_in=-3)

    response = await token_client.get("/api/v1/me/event-requests", headers=bearer(token))

    assert response.status_code == 200


async def test_tc_us16a_10_a_token_signed_by_another_key_is_unauthenticated(
    token_client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4())
    token = make_token(organiser.auth_user_id, organiser.email, key=OTHER_KEY)

    response = await token_client.get("/api/v1/me/event-requests", headers=bearer(token))

    assert response.status_code == 401


async def test_tc_us16a_10_a_tampered_token_is_unauthenticated(token_client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4())
    other = make_user(db, auth_user_id=uuid.uuid4())
    header, _payload, signature = make_token(organiser.auth_user_id, organiser.email).split(".")
    _, forged_payload, _ = make_token(other.auth_user_id, other.email).split(".")

    response = await token_client.get(
        "/api/v1/me/event-requests", headers=bearer(f"{header}.{forged_payload}.{signature}")
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "claims",
    [{"aud": "anon"}, {"iss": "https://another-project.supabase.co/auth/v1"}],
    ids=["wrong audience", "wrong issuer"],
)
async def test_tc_us16a_11_wrong_audience_or_issuer_is_unauthenticated(
    token_client: AsyncClient, db: Session, claims: dict[str, str]
) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4())
    token = make_token(organiser.auth_user_id, organiser.email, **claims)

    response = await token_client.get("/api/v1/me/event-requests", headers=bearer(token))

    assert response.status_code == 401


async def test_tc_us16a_12_a_valid_token_without_a_profile_needs_one(token_client: AsyncClient) -> None:
    token = make_token(uuid.uuid4(), "brand.new@smu.edu.sg")

    response = await token_client.get("/api/v1/me/event-requests", headers=bearer(token))

    assert response.status_code == 403
    assert response.json() == {"code": "PROFILE_REQUIRED"}


async def test_tc_us16a_13_an_inactive_user_is_forbidden(token_client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4(), is_active=False)

    response = await token_client.get(
        "/api/v1/me/event-requests", headers=bearer(make_token(organiser.auth_user_id, organiser.email))
    )

    assert response.status_code == 403
    assert response.json() == {"code": "FORBIDDEN"}


async def test_tc_us16a_14_header_stubs_are_ignored_when_dev_headers_are_off(
    token_client: AsyncClient, db: Session
) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR)
    attendee = make_attendee_user(db)

    as_user = await token_client.get("/api/v1/event-requests", headers={"X-User-Id": str(coordinator.id)})
    as_attendee = await token_client.get("/api/v1/me/registrations", headers={"X-Attendee-Id": str(attendee.id)})

    assert as_user.status_code == 401
    assert as_attendee.status_code == 401


async def test_tc_us16a_15_header_stubs_still_work_when_dev_headers_are_on(
    dev_client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    attendee = make_attendee_user(db)

    as_user = await create_draft(dev_client, {"X-User-Id": str(organiser.id)})
    as_attendee = await dev_client.get("/api/v1/me/registrations", headers={"X-Attendee-Id": str(attendee.id)})

    assert as_user.status_code == 201
    assert as_attendee.status_code == 200


async def test_tc_us16a_15_a_bad_token_is_refused_even_when_dev_headers_are_on(
    dev_client: AsyncClient, db: Session
) -> None:
    """A token that fails verification never falls back to the header stub."""
    organiser = make_user(db)

    response = await create_draft(
        dev_client, {"Authorization": "Bearer not-a-jwt", "X-User-Id": str(organiser.id)}
    )

    assert response.status_code == 401


async def test_tc_us16a_16_an_attendee_token_reads_their_registrations(
    token_client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee_user(db, auth_user_id=uuid.uuid4())

    response = await token_client.get(
        "/api/v1/me/registrations", headers=bearer(make_token(attendee.auth_user_id, attendee.email))
    )

    assert response.status_code == 200
    assert response.json() == {"confirmed": [], "waitlisted": [], "offered": [], "expired": []}


async def test_tc_us16a_17_an_organiser_token_on_an_attendee_route_is_unauthenticated(
    token_client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4())

    response = await token_client.get(
        "/api/v1/me/registrations", headers=bearer(make_token(organiser.auth_user_id, organiser.email))
    )

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}


async def test_tc_us16a_46_unreachable_keys_are_a_503_not_a_logout(
    token_client: AsyncClient, db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Review on PR #55: if Supabase can't be reached, a 401 would make the frontend log everyone out."""

    def unreachable(_token: str) -> object:
        raise jwt.PyJWKClientConnectionError("Fail to fetch data from the url")

    app.dependency_overrides[get_token_verifier] = lambda: TokenVerifier(issuer=ISSUER, key_for=unreachable)
    organiser = make_user(db, auth_user_id=uuid.uuid4())

    with caplog.at_level(logging.WARNING, logger="app.user"):
        response = await token_client.get(
            "/api/v1/me/event-requests", headers=bearer(make_token(organiser.auth_user_id, organiser.email))
        )

    assert response.status_code == 503
    assert response.json() == {"code": "AUTH_UNAVAILABLE"}
    assert "unreachable" in caplog.text.lower()


async def test_tc_us16a_47_a_missing_supabase_url_is_a_server_error(
    token_client: AsyncClient, db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Review on PR #55: a deployment mistake must be loud, not look like the user's bad token."""
    app.dependency_overrides.pop(get_token_verifier)  # the production verifier
    monkeypatch.setattr(settings, "supabase_url", "")
    _project_keys.cache_clear()
    organiser = make_user(db, auth_user_id=uuid.uuid4())

    with caplog.at_level(logging.ERROR, logger="app.user"):
        response = await token_client.get(
            "/api/v1/me/event-requests", headers=bearer(make_token(organiser.auth_user_id, organiser.email))
        )

    _project_keys.cache_clear()
    assert response.status_code == 500
    assert response.json() == {"code": "AUTH_NOT_CONFIGURED"}
    assert "SUPABASE_URL" in caplog.text


@pytest.mark.parametrize("enabled", [True, False])
def test_tc_us16a_48_startup_warns_while_the_header_stubs_are_on(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, enabled: bool
) -> None:
    monkeypatch.setattr(settings, "auth_dev_headers", enabled)

    with caplog.at_level(logging.WARNING, logger="app.user"):
        with TestClient(app):
            pass

    assert ("AUTH_DEV_HEADERS" in caplog.text) is enabled


async def test_tc_us16a_49_a_refused_token_is_logged_without_the_token(
    token_client: AsyncClient, db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4())
    token = make_token(organiser.auth_user_id, organiser.email, key=OTHER_KEY)

    with caplog.at_level(logging.WARNING, logger="app.user"):
        response = await token_client.get("/api/v1/me/event-requests", headers=bearer(token))

    assert response.status_code == 401
    assert "InvalidSignatureError" in caplog.text
    assert token not in caplog.text
    assert token.split(".")[1] not in caplog.text
