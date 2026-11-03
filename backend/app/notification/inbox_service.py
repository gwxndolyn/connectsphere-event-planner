import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event
from app.event.request_service import event_request_service
from app.notification.models import Notification
from app.notification.schemas import NotificationListOut, NotificationOut, ReadAllOut, UnreadCountOut
from app.user.models import User

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


class InboxService:
    """US31 (SCRUM-107): a user's own notifications. Every query is scoped to the caller, so another
    user's notification is the same 404 as one that doesn't exist (AC 2)."""

    def list(self, db: Session, user: User, *, limit: int = DEFAULT_LIMIT, unread_only: bool = False) -> NotificationListOut:
        query = select(Notification).where(Notification.user_id == user.id)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        rows = db.scalars(query.order_by(Notification.created_at.desc(), Notification.id).limit(limit)).all()
        events = self._readable_events(db, user, {row.event_id for row in rows if row.event_id})
        return NotificationListOut(
            notifications=[self._out(row, row.event_id in events) for row in rows],
            unread_count=self._unread(db, user),
        )

    def unread_count(self, db: Session, user: User) -> UnreadCountOut:
        return UnreadCountOut(unread_count=self._unread(db, user))

    def mark_read(self, db: Session, user: User, notification_id: uuid.UUID, now: datetime) -> NotificationOut:
        """AC 4: idempotent, and the time it was first read is kept."""
        row = db.scalars(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
        ).one_or_none()
        if row is None:
            raise DomainError(404, "NOT_FOUND")
        if row.read_at is None:
            row.read_at = now
            db.commit()
        return self._out(row, row.event_id in self._readable_events(db, user, {row.event_id} - {None}))

    def mark_all_read(self, db: Session, user: User, now: datetime) -> ReadAllOut:
        result = db.execute(
            update(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
            .values(read_at=now)
        )
        db.commit()
        return ReadAllOut(updated=result.rowcount, unread_count=self._unread(db, user))

    def _unread(self, db: Session, user: User) -> int:
        return db.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
        ) or 0

    def _readable_events(self, db: Session, user: User, event_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """AC 5: the events among `event_ids` whose request the user may open, by the rules the request routes use."""
        if not event_ids:
            return set()
        events = db.scalars(select(Event).where(Event.id.in_(event_ids))).all()
        return {event.id for event in events if event_request_service.can_read(event, user)}

    def _out(self, row: Notification, can_open: bool) -> NotificationOut:
        return NotificationOut(
            id=row.id,
            kind=row.kind,
            event_id=row.event_id,
            event_name=row.event_name,
            message=row.message,
            created_at=row.created_at,
            read=row.read_at is not None,
            can_open=can_open,
        )


inbox_service = InboxService()
