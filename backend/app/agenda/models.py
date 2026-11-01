import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, pg_enum


class SessionType(enum.StrEnum):
    """US15 AC 2: the AC's examples, plus `other` for opening remarks, Q&A and the like (decided by the
    acting PO, 1 Nov)."""

    PRESENTATION = "presentation"
    WORKSHOP = "workshop"
    PANEL = "panel"
    BREAK = "break"
    OTHER = "other"


class EventSession(Base):
    """One item on an event's agenda (US15, SCRUM-18, AC 2). Each event is one track (AC 4, decided by
    the acting PO, 1 Nov): no two of its sessions overlap, as the migration's `event_sessions_no_overlap`
    exclusion constraint enforces, which also indexes the sessions by event."""

    __tablename__ = "event_sessions"
    __table_args__ = (
        CheckConstraint("btrim(title) <> ''", name="event_sessions_title_not_blank"),
        CheckConstraint("ends_at > starts_at", name="event_sessions_window_valid"),
        # A break has no speaker; every other session names one (decided by the acting PO, 1 Nov).
        CheckConstraint(
            "session_type = 'break' OR btrim(coalesce(speaker_name, '')) <> ''",
            name="event_sessions_speaker_required",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    title: Mapped[str] = mapped_column(Text)
    session_type: Mapped[SessionType] = mapped_column(pg_enum(SessionType, "event_session_type"))
    speaker_name: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
