import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, pg_enum


class UserRole(enum.StrEnum):
    """In the database type's order, which is the order `/me` lists a user's roles in (TC-US16B-07).
    The type also holds 'operations_manager', retired by US16b (D49): no user holds it and the app
    can't give it out."""

    ORGANISER = "organiser"
    COORDINATOR = "coordinator"
    COORDINATOR_LEAD = "coordinator_lead"
    ATTENDEE = "attendee"
    # Technical Support Staff (US26, SCRUM-108).
    TECH_SUPPORT = "tech_support"
    # US16b (SCRUM-82): Venue Staff replaces D19's operations_manager stand-in.
    VENUE_STAFF = "venue_staff"
    SAFETY_OFFICER = "safety_officer"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("cardinality(roles) > 0", name="users_roles_not_empty"),
        CheckConstraint("array_has_no_repeats(roles)", name="users_roles_no_repeats"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(Text, unique=True)
    # One or more roles (US16b, D45); the API allows whatever any of them allows (D46).
    roles: Mapped[list[UserRole]] = mapped_column(
        ARRAY(pg_enum(UserRole, "user_role")), server_default=text("'{attendee}'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # The Supabase Auth user id (token `sub`); null until the person first logs in or signs up (US16a).
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(unique=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def holds(self, *roles: UserRole) -> bool:
        """Whether the user holds any of `roles` (D46)."""
        return any(role in self.roles for role in roles)

    @property
    def display_name(self) -> str:
        """What other people see: the full name once the profile has one, else the email."""
        return self.full_name or self.email


class Attendee(Base):
    """Minimal attendee record. The spec references attendees(id) without defining the table;
    this is the smallest shape that satisfies it until Supabase Auth lands."""

    __tablename__ = "attendees"

    id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
