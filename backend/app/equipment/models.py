import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, pg_enum


class EquipmentLineStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EquipmentType(Base):
    """The equipment catalogue (US26 AC 4: a line's type must exist here). Stock, condition and storage
    location come with US5 (SCRUM-9)."""

    __tablename__ = "equipment_types"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="equipment_types_name_not_blank"),
        Index("equipment_types_name_lower_unique", text("lower(btrim(name))"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EquipmentRequestLine(Base):
    """One equipment type an event needs, with its quantity (US26 AC 1). Tech Support approves it for
    the full quantity or rejects it (AC 3, 6)."""

    __tablename__ = "equipment_request_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="equipment_request_lines_quantity_positive"),
        CheckConstraint(
            "(status = 'pending' AND reviewed_at IS NULL AND reviewed_by_user_id IS NULL)"
            " OR (status <> 'pending' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL)",
            name="equipment_request_lines_reviewed_consistent",
        ),
        CheckConstraint(
            "review_note IS NULL OR status <> 'pending'", name="equipment_request_lines_note_only_when_reviewed"
        ),
        # DECISION-PENDING: D51 — no one reviews a line they requested (US16b, SCRUM-120).
        CheckConstraint(
            "reviewed_by_user_id <> requested_by_user_id", name="equipment_request_lines_reviewer_not_requester"
        ),
        Index("ix_equipment_request_lines_event_id", "event_id"),
        Index("ix_equipment_request_lines_pending", "created_at", postgresql_where=text("status = 'pending'")),
        # DECISION-PENDING: D41 — one pending or approved line per type per event.
        Index(
            "equipment_request_lines_one_live_per_type",
            "event_id",
            "equipment_type_id",
            unique=True,
            postgresql_where=text("status <> 'rejected'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    equipment_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipment_types.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EquipmentLineStatus] = mapped_column(
        pg_enum(EquipmentLineStatus, "equipment_line_status"), server_default=EquipmentLineStatus.PENDING.value
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
