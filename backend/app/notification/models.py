import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notification(Base):
    """One notice the system raised for one user (US31, SCRUM-107): what the Notifier logs, kept so the
    person can read it later. `message` is the sentence they read, written when it was raised.

    `user_id` and `event_id` are deliberately not foreign keys. A notice is written from its own session
    while the code that raised it can still hold a lock on the event (a waitlist offer is sent inside the
    withdrawal's transaction), and a foreign key insert waits for that lock: the request would wait on
    itself. Users and events are never deleted, so nothing is left dangling."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("btrim(kind) <> '' AND btrim(message) <> ''", name="notifications_kind_and_message_not_blank"),
        # The inbox, newest first, and the unread count.
        Index("ix_notifications_user_id_created_at", "user_id", text("created_at DESC")),
        Index("ix_notifications_unread", "user_id", postgresql_where=text("read_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column()
    # The Notifier method that raised it, e.g. `event_confirmed`.
    kind: Mapped[str] = mapped_column(Text)
    # The event it is about, when the notice named one that could be found.
    event_id: Mapped[uuid.UUID | None] = mapped_column()
    event_name: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
