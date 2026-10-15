import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import DomainError
from app.user.auth import InvalidToken, TokenVerifier, auth_dev_headers_enabled, get_token_verifier
from app.user.models import Attendee, User, UserRole

# Roles a first login may link to by email (TC-US16A-06). Staff rows are linked by the seed instead
# (SCRUM-104): with "Confirm email" off, anyone can create a Supabase account for an unused email.
EMAIL_LINKABLE_ROLES = (UserRole.ORGANISER, UserRole.ATTENDEE)


def _bearer_token(authorization: str | None) -> str | None:
    """The token from `Authorization: Bearer <token>`, or None when no Authorization header was sent.
    Any other Authorization header is refused rather than ignored."""
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise DomainError(401, "UNAUTHENTICATED")
    return token.strip()


def _user_for_token(db: Session, verifier: TokenVerifier, token: str) -> User:
    """Verify the token, then find its user: by `auth_user_id`, else link an unlinked Organiser or
    Attendee with the same email on first login (§9)."""
    try:
        claims = verifier.verify(token)
    except InvalidToken:
        raise DomainError(401, "UNAUTHENTICATED") from None

    user = db.scalar(select(User).where(User.auth_user_id == claims.sub))
    if user is None and claims.email:
        by_email = db.scalar(select(User).where(func.lower(User.email) == claims.email.lower()))
        if by_email is not None:
            if by_email.auth_user_id is not None or by_email.role not in EMAIL_LINKABLE_ROLES:
                # Linked to another account (TC-US16A-07), or staff (TC-US16A-06).
                raise DomainError(401, "UNAUTHENTICATED")
            by_email.auth_user_id = claims.sub
            db.commit()
            user = by_email
    if user is None:
        # Signed up in Supabase, but no profile yet (SCRUM-103 creates it).
        raise DomainError(403, "PROFILE_REQUIRED")
    if not user.is_active:
        raise DomainError(403, "FORBIDDEN")
    return user


def get_current_attendee(
    authorization: Annotated[str | None, Header()] = None,
    x_attendee_id: Annotated[uuid.UUID | None, Header()] = None,
    db: Session = Depends(get_db),
    verifier: TokenVerifier = Depends(get_token_verifier),
    dev_headers: bool = Depends(auth_dev_headers_enabled),
) -> Attendee:
    """The calling attendee: from a Supabase token, or from the X-Attendee-Id stub when dev headers
    are on (spec §3, §9). Only this function and get_current_user know how identity arrives."""
    token = _bearer_token(authorization)
    if token is not None:
        attendee = db.get(Attendee, _user_for_token(db, verifier, token).id)
    elif dev_headers and x_attendee_id:
        attendee = db.get(Attendee, x_attendee_id)
    else:
        attendee = None
    if attendee is None:
        raise DomainError(401, "UNAUTHENTICATED")
    return attendee


# DECISION-PENDING: D12 — the X-User-Id stub stays for local dev, tests and CI E2E behind
# AUTH_DEV_HEADERS (US16a). X-Attendee-Id likewise. Production identifies callers by token only.
def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_user_id: Annotated[uuid.UUID | None, Header()] = None,
    db: Session = Depends(get_db),
    verifier: TokenVerifier = Depends(get_token_verifier),
    dev_headers: bool = Depends(auth_dev_headers_enabled),
) -> User:
    """The calling user for role-aware routes: from a Supabase token, or from the X-User-Id stub when
    dev headers are on. A token that fails verification never falls back to the stub."""
    token = _bearer_token(authorization)
    if token is not None:
        return _user_for_token(db, verifier, token)
    user = db.get(User, x_user_id) if dev_headers and x_user_id else None
    if user is None:
        raise DomainError(401, "UNAUTHENTICATED")
    if not user.is_active:
        raise DomainError(403, "FORBIDDEN")
    return user


def require_user_roles(*allowed_roles: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise DomainError(403, "FORBIDDEN")
        return user

    return dependency
