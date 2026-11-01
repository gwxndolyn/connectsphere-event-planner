import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.notification.inbox_service import DEFAULT_LIMIT, MAX_LIMIT, inbox_service
from app.notification.schemas import NotificationListOut, NotificationOut, ReadAllOut, UnreadCountOut
from app.user.dependencies import get_current_user
from app.user.models import User

# US31 (SCRUM-107): any logged-in user reads their own notifications, whatever role they hold.
router = APIRouter(prefix="/api/v1/me/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
def list_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    unread_only: bool = False,
) -> NotificationListOut:
    return inbox_service.list(db, user, limit=limit, unread_only=unread_only)


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UnreadCountOut:
    return inbox_service.unread_count(db, user)


# Declared before "/{id}/read" so "read-all" is never taken for an id.
@router.post("/read-all", response_model=ReadAllOut)
def read_all(
    user: User = Depends(get_current_user), db: Session = Depends(get_db), now: datetime = Depends(get_now)
) -> ReadAllOut:
    return inbox_service.mark_all_read(db, user, now)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def read_one(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> NotificationOut:
    return inbox_service.mark_read(db, user, notification_id, now)
