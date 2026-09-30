import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import DomainError
from app.user.models import Attendee, User, UserRole


def get_current_attendee(
    x_attendee_id: Annotated[uuid.UUID | None, Header()] = None,
    db: Session = Depends(get_db),
) -> Attendee:
    """Sprint 1 identity stub: the caller is whoever the X-Attendee-Id header names (spec §3).
    When Supabase Auth lands, only this function changes."""
    attendee = db.get(Attendee, x_attendee_id) if x_attendee_id else None
    if attendee is None:
        raise DomainError(401, "UNAUTHENTICATED")
    return attendee


def get_current_user(
    x_user_id: Annotated[uuid.UUID | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    """Role-aware development identity stub for event-management routes."""
    user = db.get(User, x_user_id) if x_user_id else None
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
