"""Supabase-style access tokens for tests, signed with a key pair made for the test run, plus a client
that checks them against that key. Nothing reaches the network (§9)."""

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.main import app
from app.notification.service import get_notifier
from app.user.auth import TokenVerifier, auth_dev_headers_enabled, get_token_verifier
from tests.factories import NOW

ISSUER = "https://test-project.supabase.co/auth/v1"
SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


def make_token(
    sub: uuid.UUID,
    email: str | None,
    *,
    key: ec.EllipticCurvePrivateKey = SIGNING_KEY,
    expires_in: int = 3600,
    aud: str = "authenticated",
    iss: str = ISSUER,
    email_verified: bool = True,
) -> str:
    now = int(time.time())
    claims = {
        "sub": str(sub),
        "aud": aud,
        "iss": iss,
        "iat": now,
        "exp": now + expires_in,
        # Where Supabase says the email was confirmed ("Confirm email" is on).
        "user_metadata": {"email_verified": email_verified},
    }
    if email is not None:
        claims["email"] = email
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key"})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@asynccontextmanager
async def api_client(db: Session, notifier, *, dev_headers: bool = False) -> AsyncIterator[AsyncClient]:
    """A client whose app checks tokens against SIGNING_KEY, with the header stubs on or off. Clears
    the dependency overrides on exit, so no test file has to remember to."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_notifier] = lambda: notifier
    app.dependency_overrides[get_token_verifier] = lambda: TokenVerifier(
        issuer=ISSUER, key_for=lambda _token: SIGNING_KEY.public_key()
    )
    app.dependency_overrides[auth_dev_headers_enabled] = lambda: dev_headers
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()
