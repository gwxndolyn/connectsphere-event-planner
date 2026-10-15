"""Supabase Auth access tokens (US16a, SCRUM-102). Supabase signs them with asymmetric keys (ES256), so
the backend checks them against the project's public keys and holds no secret (§9)."""

import ssl
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import certifi
import jwt

from app.core.config import settings

ALGORITHMS = ["ES256", "RS256"]
AUDIENCE = "authenticated"


class InvalidToken(Exception):
    """Any reason a token can't be trusted. Callers answer 401 without saying which."""


@dataclass(frozen=True)
class TokenClaims:
    sub: uuid.UUID
    email: str | None


class TokenVerifier:
    """`key_for` returns the public key a token was signed with: the project's JWKS in production,
    a key made for the test run in tests."""

    def __init__(self, *, issuer: str, key_for: Callable[[str], object]) -> None:
        self.issuer = issuer
        self.key_for = key_for

    def verify(self, token: str) -> TokenClaims:
        try:
            claims = jwt.decode(
                token,
                self.key_for(token),
                algorithms=ALGORITHMS,
                audience=AUDIENCE,
                issuer=self.issuer,
                options={"require": ["sub", "exp", "aud", "iss"]},
            )
            return TokenClaims(sub=uuid.UUID(claims["sub"]), email=claims.get("email"))
        except InvalidToken:
            raise
        except (jwt.PyJWTError, ValueError) as error:
            raise InvalidToken from error


def _issuer() -> str:
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def _project_keys() -> jwt.PyJWKClient:
    """Built on the first token, not at startup, so requests without a token (the dev header stubs)
    work while SUPABASE_URL is unset. PyJWKClient caches the keys, so most tokens need no network call."""
    if not settings.supabase_url:
        raise InvalidToken("SUPABASE_URL is not set")
    # certifi's CA bundle, not the system's: python.org builds on macOS ship without one, and every
    # key fetch (so every login) would fail certificate verification.
    return jwt.PyJWKClient(
        f"{_issuer()}/.well-known/jwks.json",
        cache_keys=True,
        timeout=10,
        ssl_context=ssl.create_default_context(cafile=certifi.where()),
    )


def _signing_key(token: str) -> object:
    return _project_keys().get_signing_key_from_jwt(token).key


def get_token_verifier() -> TokenVerifier:
    """The production verifier; tests override this dependency with their own key."""
    return TokenVerifier(issuer=_issuer(), key_for=_signing_key)


def auth_dev_headers_enabled() -> bool:
    """Whether the X-User-Id / X-Attendee-Id stubs still work (local dev, tests, CI E2E)."""
    return settings.auth_dev_headers
