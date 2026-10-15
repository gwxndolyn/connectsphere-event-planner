"""US16a, PR 2 (SCRUM-102): the backend accepts a Supabase access token in place of the header stubs.
Tokens here are signed with a key pair made for the test run, so nothing reaches the network (§9)."""

import time
import uuid
from collections.abc import AsyncGenerator

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.main import app
from app.notification.service import get_notifier
from app.user.auth import TokenVerifier, auth_dev_headers_enabled, get_token_verifier
from app.user.models import Attendee, User, UserRole
from tests.factories import NOW

pytestmark = pytest.mark.anyio

ISSUER = "https://test-project.supabase.co/auth/v1"
SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


def make_token(
    sub: uuid.UUID,
    email: str,
    *,
    key: ec.EllipticCurvePrivateKey = SIGNING_KEY,
    expires_in: int = 3600,
    aud: str = "authenticated",
    iss: str = ISSUER,
) -> str:
    now = int(time.time())
    claims = {"sub": str(sub), "email": email, "aud": aud, "iss": iss, "iat": now, "exp": now + expires_in}
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key"})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_user(db: Session, role: UserRole = UserRole.ORGANISER, **fields) -> User:
    user = User(email=f"{uuid.uuid4().hex[:12]}@smu.edu.sg", role=role, **fields)
    db.add(user)
    db.flush()
    return user


def make_attendee_user(db: Session, **fields) -> User:
    user = make_user(db, UserRole.ATTENDEE, **fields)
    db.add(Attendee(id=user.id, email=user.email))
    db.flush()
    return user


def client_for(db: Session, notifier, *, dev_headers: bool) -> AsyncClient:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_notifier] = lambda: notifier
    app.dependency_overrides[get_token_verifier] = lambda: TokenVerifier(
        issuer=ISSUER, key_for=lambda _token: SIGNING_KEY.public_key()
    )
    app.dependency_overrides[auth_dev_headers_enabled] = lambda: dev_headers
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def token_client(db: Session, notifier) -> AsyncGenerator[AsyncClient, None]:
    """Production settings: tokens only, header stubs off."""
    async with client_for(db, notifier, dev_headers=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def dev_client(db: Session, notifier) -> AsyncGenerator[AsyncClient, None]:
    """Local dev, tests and CI E2E: tokens and header stubs both work."""
    async with client_for(db, notifier, dev_headers=True) as client:
        yield client
    app.dependency_overrides.clear()


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


@pytest.mark.parametrize("role", [UserRole.COORDINATOR, UserRole.OPERATIONS_MANAGER])
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
    assert response.json() == {"confirmed": [], "waitlisted": [], "offered": []}


async def test_tc_us16a_17_an_organiser_token_on_an_attendee_route_is_unauthenticated(
    token_client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, auth_user_id=uuid.uuid4())

    response = await token_client.get(
        "/api/v1/me/registrations", headers=bearer(make_token(organiser.auth_user_id, organiser.email))
    )

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
