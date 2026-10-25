"""record the coordinator's decision on an event request

Revision ID: 20261029_1200_us17_decisions
Revises: 20261027_1200_us16b_roles
Create Date: 2026-10-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261029_1200_us17_decisions"
down_revision: Union[str, None] = "20261027_1200_us16b_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US17 (SCRUM-84): who approved or rejected a request, when (AC 5), and why on a rejection (AC 3).
    # Nullable: a request not yet decided has none, and neither do events made before US17 (the seed
    # and tests put them straight into later statuses, D24), so nothing is backfilled.
    op.add_column("events", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("events", sa.Column("decided_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("events", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.create_foreign_key("fk_events_decided_by_user_id_users", "events", "users", ["decided_by_user_id"], ["id"])
    # A reason only goes with a rejection. The service requires one on every rejection it makes; the
    # database can't, since tests and the seed make rejected rows without one.
    op.create_check_constraint(
        "events_rejection_reason_only_when_rejected",
        "events",
        "status::text = 'rejected' OR rejection_reason IS NULL",
    )
    # D51: no one decides a request they created.
    op.create_check_constraint(
        "events_decider_not_creator",
        "events",
        "decided_by_user_id IS NULL OR created_by_user_id IS NULL OR decided_by_user_id <> created_by_user_id",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM events WHERE decided_at IS NOT NULL "
            "OR decided_by_user_id IS NOT NULL OR rejection_reason IS NOT NULL)"
        )
    ):
        raise RuntimeError("Refusing lossy downgrade: event request decisions would be discarded.")
    op.drop_constraint("events_decider_not_creator", "events", type_="check")
    op.drop_constraint("events_rejection_reason_only_when_rejected", "events", type_="check")
    op.drop_constraint("fk_events_decided_by_user_id_users", "events", type_="foreignkey")
    op.drop_column("events", "rejection_reason")
    op.drop_column("events", "decided_by_user_id")
    op.drop_column("events", "decided_at")
