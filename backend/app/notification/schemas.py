import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    """One notification as its recipient reads it (US31 AC 2, 3): the event it is about, what happened and when."""

    id: uuid.UUID
    kind: str
    event_id: uuid.UUID | None
    event_name: str | None
    message: str
    created_at: datetime
    read: bool
    # AC 5: whether the recipient may open the event's request; the notice names it either way.
    can_open: bool


class NotificationListOut(BaseModel):
    # Newest first.
    notifications: list[NotificationOut]
    # Every unread one, not just the ones listed (AC 3).
    unread_count: int


class UnreadCountOut(BaseModel):
    unread_count: int


class ReadAllOut(BaseModel):
    updated: int
    unread_count: int
