"""add event-request clarification thread

Revision ID: 20261008_1200_us8_clarifications
Revises: 20260930_1200_us1_request_schema
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261008_1200_us8_clarifications"
down_revision: Union[str, None] = "20260930_1200_us1_request_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Kept in step with CLARIFICATION_SECTIONS in app/event/models.py (D13).
SECTIONS = (
    "details",
    "schedule",
    "attendance",
    "layout",
    "accessibility",
    "equipment",
    "registration",
)
SECTIONS_ARRAY = "ARRAY[" + ", ".join(f"'{section}'" for section in SECTIONS) + "]::text[]"


def upgrade() -> None:
    op.create_table(
        "event_request_clarifications",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("request", "response", name="clarification_kind"),
            nullable=False,
        ),
        sa.Column("sections", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_event_request_clarifications_event_id_events"),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"], name="fk_event_request_clarifications_author_user_id_users"
        ),
        # One coordinator question and at most one organiser reply per round.
        sa.UniqueConstraint("event_id", "round", "kind", name="event_request_clarifications_round_kind_key"),
        sa.CheckConstraint("round >= 1", name="event_request_clarifications_round_positive"),
        sa.CheckConstraint("btrim(comment) <> ''", name="event_request_clarifications_comment_not_blank"),
        # A question tags at least one known section; a reply tags none.
        sa.CheckConstraint(
            "(kind = 'request' AND cardinality(sections) >= 1 AND sections <@ "
            f"{SECTIONS_ARRAY}) OR (kind = 'response' AND sections IS NULL)",
            name="event_request_clarifications_sections_valid",
        ),
    )
    op.execute("ALTER TABLE event_request_clarifications ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM event_request_clarifications)")):
        raise RuntimeError("Refusing lossy downgrade: clarification messages would be discarded.")
    op.drop_table("event_request_clarifications")
    sa.Enum(name="clarification_kind").drop(bind)
