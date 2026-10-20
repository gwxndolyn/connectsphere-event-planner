import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func, text
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
    __table_args__ = (CheckConstraint("btrim(name) <> ''", name="equipment_types_name_not_blank"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EquipmentRequestLine(Base):
    """One equipment type an event needs, with its quantity (US26 AC 1). Tech Support approves it for
    the full quantity or rejects it (AC 3, 6)."""

    __tablename__ = "equipment_request_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="equipment_request_lines_quantity_positive"),)

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
