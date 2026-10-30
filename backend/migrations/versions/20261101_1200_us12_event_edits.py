"""add change requests and the audit log for editing an event in planning

Revision ID: 20261101_1200_us12_event_edits
Revises: 20261031_1200_us16b_d51_checks
Create Date: 2026-11-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261101_1200_us12_event_edits"
down_revision: Union[str, None] = "20261031_1200_us16b_d51_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US12 (SCRUM-15) AC 3: a critical-field edit is held here, Pending Approval, and the event keeps its values.
    op.create_table(
        "event_change_requests",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending_approval", "approved", "rejected", name="change_request_status"),
            server_default="pending_approval",
            nullable=False,
        ),
        # Each changed field with its old and new value: [{"field", "old_value", "new_value"}, ...].
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_event_change_requests_event_id_events"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], name="fk_event_change_requests_requested_by_user_id_users"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(changes) = 'array' AND jsonb_array_length(changes) >= 1",
            name="event_change_requests_changes_not_empty",
        ),
    )
    op.create_index("ix_event_change_requests_event_id", "event_change_requests", ["event_id"])
    op.execute("ALTER TABLE event_change_requests ENABLE ROW LEVEL SECURITY")

    # AC 5: one row per field of every successful save. Append-only; `seq` orders rows written in one save.
    op.create_table(
        "event_audit_entries",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column("previous_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("change_request_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_event_audit_entries_event_id_events"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_event_audit_entries_user_id_users"),
        sa.ForeignKeyConstraint(
            ["change_request_id"],
            ["event_change_requests.id"],
            name="fk_event_audit_entries_change_request_id_event_change_requests",
        ),
    )
    op.create_index("ix_event_audit_entries_event_id", "event_audit_entries", ["event_id"])
    op.execute("ALTER TABLE event_audit_entries ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM event_audit_entries) OR EXISTS (SELECT 1 FROM event_change_requests)")
    ):
        raise RuntimeError("Refusing lossy downgrade: event edit history or change requests would be discarded.")
    op.drop_index("ix_event_audit_entries_event_id", table_name="event_audit_entries")
    op.drop_table("event_audit_entries")
    op.drop_index("ix_event_change_requests_event_id", table_name="event_change_requests")
    op.drop_table("event_change_requests")
    op.execute("DROP TYPE change_request_status")
