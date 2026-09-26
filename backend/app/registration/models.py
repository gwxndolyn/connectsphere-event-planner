import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, pg_enum
from app.event.models import Event


class RegistrationStatus(enum.StrEnum):
    CONFIRMED = "confirmed"  # holds a seat
    WAITLISTED = "waitlisted"  # queued, holds no seat
    OFFERED = "offered"  # a freed seat is held for this person until offer_expires_at
    WITHDRAWN = "withdrawn"  # attendee withdrew
    DECLINED = "declined"  # declined or let an offer lapse
    EXPIRED = "expired"


ACTIVE_STATUSES = (RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLISTED, RegistrationStatus.OFFERED)


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        # "Cannot register twice for the same event" — enforced in the DB, not only in app code.
        Index(
            "registrations_one_active_per_attendee",
            "event_id",
            "attendee_id",
            unique=True,
            postgresql_where=text("status in ('confirmed', 'waitlisted', 'offered')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    # Null only for email-only waitlist entries — see spec §6 D3.
    attendee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attendees.id"))
    attendee_email: Mapped[str] = mapped_column(Text)
    status: Mapped[RegistrationStatus] = mapped_column(pg_enum(RegistrationStatus, "registration_status"))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Ordering key for the waitlist. Position is derived from this, never stored.
    waitlist_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[Event] = relationship()


class RegistrationAnswer(Base):
    """One answer to one `EventRegistrationField`, keyed by the registration it belongs to."""

    __tablename__ = "registration_answers"

    registration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), primary_key=True
    )
    field_key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class AttendanceLog(Base):
    """Append-only audit trail. Never update or delete a row."""

    __tablename__ = "attendance_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    registration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("registrations.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    attendee_id: Mapped[uuid.UUID | None]
    # registered | waitlisted | withdrawn | offered | offer_expired | declined
    action: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)
