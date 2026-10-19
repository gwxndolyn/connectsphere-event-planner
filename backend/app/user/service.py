import logging

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.user.auth import TokenClaims
from app.user.models import Attendee, User, UserRole
from app.user.schemas import ProfileWrite

logger = logging.getLogger(__name__)

# The only roles sign-up may choose (US16a AC 7). Staff accounts come from the seed (SCRUM-104).
SIGN_UP_ROLES = {UserRole.ORGANISER.value: UserRole.ORGANISER, UserRole.ATTENDEE.value: UserRole.ATTENDEE}


def create_profile(db: Session, claims: TokenClaims, body: ProfileWrite) -> User:
    """The `users` row (and, for an attendee, its `attendees` row) for a confirmed Supabase account
    that has none yet (SCRUM-103). `auth_user_id` and `email` come from the token, never the body."""
    full_name = (body.full_name or "").strip()
    role = (body.role or "").strip()
    missing = [field for field, value in (("full_name", full_name), ("role", role)) if not value]
    if missing:
        raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)  # TC-US16A-24
    if role not in SIGN_UP_ROLES:
        raise DomainError(422, "INVALID_ROLE")  # TC-US16A-20
    if not claims.email:
        # Email/password sign-ups always carry one; without it there's no profile to make.
        logger.warning("Token refused: no email claim to create a profile from")
        raise DomainError(401, "UNAUTHENTICATED")

    # Any existing row for this account or email, seeded staff included (TC-US16A-21 to 23).
    existing = db.scalar(
        select(User.id).where(
            or_(User.auth_user_id == claims.sub, func.lower(User.email) == claims.email.lower())
        )
    )
    if existing is not None:
        raise DomainError(409, "EMAIL_ALREADY_REGISTERED")

    user = User(email=claims.email, role=SIGN_UP_ROLES[role], full_name=full_name, auth_user_id=claims.sub)
    db.add(user)
    try:
        db.flush()
        if user.role is UserRole.ATTENDEE:
            # Every attendee has a users row with the same id (§2).
            db.add(Attendee(id=user.id, email=user.email))
        db.commit()
    except IntegrityError:
        # A simultaneous call for the same account or email passed the check above first.
        db.rollback()
        raise DomainError(409, "EMAIL_ALREADY_REGISTERED") from None
    db.refresh(user)
    return user
