import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, pg_enum


class EventStatus(enum.StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class DeliveryMode(enum.StrEnum):
    IN_PERSON = "in_person"
    ONLINE = "online"


class Event(Base):
    """Placeholder for Epic 1 output. Seeded only in Sprint 1 (SCRUM-23); no write paths."""

    __tablename__ = "events"
    __table_args__ = (CheckConstraint("capacity >= 0", name="events_capacity_non_negative"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[EventStatus] = mapped_column(
        pg_enum(EventStatus, "event_status"), server_default=EventStatus.DRAFT.value
    )
    # Two separate gates (spec §2): registration can be enabled but not yet open.
    registration_enabled: Mapped[bool] = mapped_column(server_default=text("false"))
    registration_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int]
    delivery_mode: Mapped[DeliveryMode] = mapped_column(pg_enum(DeliveryMode, "delivery_mode"))
    venue_name: Mapped[str | None] = mapped_column(Text)  # in_person only
    room_number: Mapped[str | None] = mapped_column(Text)  # in_person only
    join_link: Mapped[str | None] = mapped_column(Text)  # online only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
