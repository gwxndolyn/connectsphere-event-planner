"""add the coordinator assignment history

Revision ID: 20261026_1200_us10d_history
Revises: 20261025_1300_us4_decisions
Create Date: 2026-10-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261026_1200_us10d_history"
down_revision: Union[str, None] = "20261025_1300_us4_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coordinator_assignments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("coordinator_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Enum("assignment", "reassignment", name="assignment_kind"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_coordinator_assignments_event_id_events"),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"], ["users.id"], name="fk_coordinator_assignments_assigned_by_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["coordinator_id"], ["users.id"], name="fk_coordinator_assignments_coordinator_id_users"
        ),
    )
    op.create_index("ix_coordinator_assignments_event_id", "coordinator_assignments", ["event_id"])
    op.execute("ALTER TABLE coordinator_assignments ENABLE ROW LEVEL SECURITY")
    # No backfill: who assigned an earlier request was never recorded, and a guessed name would
    # defeat an accountable record. Those events simply start with an empty history.


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM coordinator_assignments)")):
        raise RuntimeError("Refusing lossy downgrade: the coordinator assignment history would be discarded.")
    op.drop_index("ix_coordinator_assignments_event_id", table_name="coordinator_assignments")
    op.drop_table("coordinator_assignments")
    op.execute("DROP TYPE assignment_kind")
