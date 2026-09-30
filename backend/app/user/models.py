import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, pg_enum


class UserRole(enum.StrEnum):
    ORGANISER = "organiser"
    COORDINATOR = "coordinator"
    OPERATIONS_MANAGER = "operations_manager"
    ATTENDEE = "attendee"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(Text, unique=True)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), server_default=UserRole.ATTENDEE.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attendee(Base):
    """Minimal attendee record. The spec references attendees(id) without defining the table;
    this is the smallest shape that satisfies it until Supabase Auth lands."""

    __tablename__ = "attendees"

    id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
