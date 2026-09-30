import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, pg_enum

REGISTRATION_FIELD_TYPES = ("text", "email", "select", "number")


class EventStatus(enum.StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    APPROVED = "approved"
    REJECTED = "rejected"
    PLANNING = "planning"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class DeliveryMode(enum.StrEnum):
    IN_PERSON = "in_person"
    ONLINE = "online"


class Event(Base):
    """Placeholder for Epic 1 output. Seeded only in Sprint 1 (SCRUM-23); no write paths."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("capacity >= 0", name="events_capacity_non_negative"),
        CheckConstraint(
            "expected_attendees IS NULL OR expected_attendees >= 1",
            name="events_expected_attendees_positive",
        ),
        CheckConstraint(
            "status::text IN ('draft', 'submitted', 'under_review', 'awaiting_clarification', 'approved', 'rejected') "
            "OR (name IS NOT NULL AND start_at IS NOT NULL AND end_at IS NOT NULL "
            "AND capacity IS NOT NULL AND delivery_mode IS NOT NULL)",
            name="events_final_fields_required",
        ),
        UniqueConstraint("request_reference", name="events_request_reference_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EventStatus] = mapped_column(
        pg_enum(EventStatus, "event_status"), server_default=EventStatus.DRAFT.value
    )
    # Two separate gates (spec §2): registration can be enabled but not yet open.
    registration_enabled: Mapped[bool] = mapped_column(server_default=text("false"))
    registration_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int | None]
    delivery_mode: Mapped[DeliveryMode | None] = mapped_column(pg_enum(DeliveryMode, "delivery_mode"))
    venue_name: Mapped[str | None] = mapped_column(Text)  # in_person only
    room_number: Mapped[str | None] = mapped_column(Text)  # in_person only
    join_link: Mapped[str | None] = mapped_column(Text)  # online only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    waitlist_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    # DECISION-PENDING: SCRUM-20 does not define the event-category options.
    event_category: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    preferred_dates: Mapped[list[date] | None] = mapped_column(ARRAY(Date))
    # DECISION-PENDING: times are local Asia/Singapore values; confirm before event conversion.
    preferred_start_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    preferred_end_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    expected_attendees: Mapped[int | None] = mapped_column(Integer)
    room_layout_preference: Mapped[str | None] = mapped_column(Text)
    accessibility_needs: Mapped[str | None] = mapped_column(Text)
    equipment_needs: Mapped[str | None] = mapped_column(Text)
    registration_required: Mapped[bool | None] = mapped_column(Boolean)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # DECISION-PENDING: reference format is provisional; uniqueness and sequence are schema-owned.
    request_reference: Mapped[str | None] = mapped_column(Text)


class EventRegistrationField(Base):
    """A piece of information an event asks a registrant for (spec §2, AC: "Provides the
    registration information required for that event"). The set of fields differs per event,
    so they can't be columns on `registrations`."""

    __tablename__ = "event_registration_fields"
    __table_args__ = (
        UniqueConstraint("event_id", "field_key"),
        CheckConstraint(
            f"field_type in {REGISTRATION_FIELD_TYPES}", name="event_registration_fields_type_valid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    field_key: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    field_type: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str] | None] = mapped_column(JSONB)
    required: Mapped[bool] = mapped_column(server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
