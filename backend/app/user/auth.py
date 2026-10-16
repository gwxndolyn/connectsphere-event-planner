"""Supabase Auth access tokens (US16a, SCRUM-102). Supabase signs them with the project's asymmetric key
(ES256 by default, RS256 if the project uses an RSA key), so the backend checks them against the
project's public keys and holds no secret (§9)."""

import logging
import ssl
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import certifi
import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

# Both asymmetric types Supabase can sign with. The key itself always comes from the project's JWKS.
ALGORITHMS = ["ES256", "RS256"]
AUDIENCE = "authenticated"
# Seconds of clock drift tolerated between Supabase and this server (TC-US16A-09).
LEEWAY = 10


class InvalidToken(Exception):
    """The token can't be trusted. Callers answer 401; the message is the reason, never the token."""


class AuthUnavailable(Exception):
    """Supabase's public keys couldn't be fetched. Callers answer 503 (TC-US16A-46)."""


class AuthNotConfigured(Exception):
    """SUPABASE_URL isn't set: a deployment mistake. Callers answer 500 (TC-US16A-47)."""


@dataclass(frozen=True)
class TokenClaims:
    sub: uuid.UUID
    email: str | None
    # Supabase sets user_metadata.email_verified once the email is confirmed.
    email_verified: bool


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
                leeway=LEEWAY,
                options={"require": ["sub", "exp", "aud", "iss"]},
            )
            metadata = claims.get("user_metadata") or {}
            return TokenClaims(
                sub=uuid.UUID(claims["sub"]),
                email=claims.get("email"),
                email_verified=metadata.get("email_verified") is True,
            )
        except (AuthUnavailable, AuthNotConfigured):
            raise
        except jwt.PyJWKClientConnectionError as error:
            raise AuthUnavailable(type(error).__name__) from error
        except (jwt.PyJWTError, ValueError) as error:
            raise InvalidToken(type(error).__name__) from error


def _issuer() -> str:
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def _project_keys() -> jwt.PyJWKClient:
    """Built on the first token, not at startup, so requests without a token (the dev header stubs)
    work while SUPABASE_URL is unset. PyJWKClient caches the keys, so most tokens need no network call;
    an unknown key id triggers at most one refetch per 30 seconds (its cooldown)."""
    if not settings.supabase_url:
        raise AuthNotConfigured("SUPABASE_URL is not set")
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


def warn_if_dev_headers_enabled() -> None:
    """Called at startup (TC-US16A-48): the stubs let any caller act as any user, so they must never be
    on in production."""
    if settings.auth_dev_headers:
        logger.warning(
            "AUTH_DEV_HEADERS is on: X-User-Id / X-Attendee-Id identify callers without logging in. "
            "Never enable it in production."
        )
