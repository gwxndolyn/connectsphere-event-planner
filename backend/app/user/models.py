import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Attendee(Base):
    """Minimal attendee record. The spec references attendees(id) without defining the table;
    this is the smallest shape that satisfies it until Supabase Auth lands."""

    __tablename__ = "attendees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
