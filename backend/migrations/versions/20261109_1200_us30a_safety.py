"""record each safety review of an event and when a rejected one is sent back

Revision ID: 20261109_1200_us30a_safety
Revises: 20261108_1200_us18_confirm
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261109_1200_us30a_safety"
down_revision: Union[str, None] = "20261108_1200_us18_confirm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US30a (SCRUM-99): one row per review, kept for good, so a rejection and the later approval both
    # stay on record (AC 6). `comments` are what the Coordinator and Organiser read; `internal_notes`
    # are the Safety Officer's own and never leave the Safety Officer's routes.
    op.create_table(
        "safety_reviews",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("checklist", postgresql.JSONB(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("outcome IN ('approved', 'rejected')", name="safety_reviews_outcome_known"),
        # AC 4: rejecting the safety arrangement needs comments the Coordinator can act on.
        sa.CheckConstraint(
            "outcome <> 'rejected' OR (comments IS NOT NULL AND btrim(comments) <> '')",
            name="safety_reviews_rejection_has_comments",
        ),
    )
    op.create_index("ix_safety_reviews_event_id_created_at", "safety_reviews", ["event_id", "created_at"])
    # AC 4: after a rejection the Coordinator revises the arrangement and sends it for another review;
    # this is when. A rejected event is back in the queue once it is later than the rejection.
    op.add_column("events", sa.Column("safety_review_requested_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM safety_reviews) "
            "OR EXISTS (SELECT 1 FROM events WHERE safety_review_requested_at IS NOT NULL)"
        )
    ):
        raise RuntimeError("Refusing lossy downgrade: safety reviews would be discarded.")
    op.drop_column("events", "safety_review_requested_at")
    op.drop_index("ix_safety_reviews_event_id_created_at", table_name="safety_reviews")
    op.drop_table("safety_reviews")
