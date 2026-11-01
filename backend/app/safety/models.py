import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.user.models import User

# US30a AC 2: the structured checklist, in the order the form shows it. The key is what is stored and
# sent; the label is what the screens say.
CHECKLIST = (
    ("attendance_capacity", "Expected attendance against venue capacity"),
    ("layout", "Room layout"),
    ("emergency_access", "Emergency access"),
    ("accessibility", "Accessibility"),
    ("equipment_placement", "Equipment placement"),
    ("crowd_movement", "Expected crowd movement"),
    ("venue_restrictions", "Known venue restrictions"),
)
CHECKLIST_KEYS = tuple(key for key, _ in CHECKLIST)
CHECKLIST_RESULTS = ("satisfactory", "issue")

# US30b AC 1: the areas a Safety Officer ticks when asking for changes. The key is what is stored and sent.
CHANGE_AREAS = (
    ("venue", "Venue"),
    ("layout", "Layout"),
    ("equipment", "Equipment"),
    ("accessibility", "Accessibility"),
    ("other", "Other"),
)
CHANGE_AREA_KEYS = tuple(key for key, _ in CHANGE_AREAS)


class SafetyReview(Base):
    """One Safety Officer's review of an event's arrangements (US30a): who, the outcome, the checklist,
    the comments the Coordinator and Organiser read, and the Safety Officer's internal notes (AC 6).
    US30b: the outcome may also be `changes_requested`, with the areas affected."""

    __tablename__ = "safety_reviews"
    __table_args__ = (
        CheckConstraint("outcome IN ('approved', 'rejected', 'changes_requested')", name="safety_reviews_outcome_known"),
        CheckConstraint(
            "outcome <> 'rejected' OR (comments IS NOT NULL AND btrim(comments) <> '')",
            name="safety_reviews_rejection_has_comments",
        ),
        CheckConstraint(
            "outcome <> 'changes_requested' OR (comments IS NOT NULL AND btrim(comments) <> '' "
            "AND areas IS NOT NULL AND jsonb_array_length(areas) > 0)",
            name="safety_reviews_changes_have_comments_and_areas",
        ),
        Index("ix_safety_reviews_event_id_created_at", "event_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(Text)
    # {key: {"result": "satisfactory" | "issue", "comment": str | null}} for every CHECKLIST key.
    checklist: Mapped[dict[str, Any]] = mapped_column(JSONB)
    comments: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    # US30b AC 1: the CHANGE_AREAS keys a request for changes marks for review; null for any other outcome.
    areas: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewer: Mapped[User] = relationship(foreign_keys=[reviewer_id], viewonly=True)
