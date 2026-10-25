"""add the reason to the coordinator assignment history

Revision ID: 20261030_1200_us10e_reassign
Revises: 20261029_1200_us17_decisions
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261030_1200_us10e_reassign"
down_revision: Union[str, None] = "20261029_1200_us17_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Null for an assignment (US10a asks for no reason); a reassignment always carries one.
    op.add_column("coordinator_assignments", sa.Column("reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "coordinator_assignments_reassignment_has_reason",
        "coordinator_assignments",
        "kind::text <> 'reassignment' OR (reason IS NOT NULL AND btrim(reason) <> '')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM coordinator_assignments WHERE reason IS NOT NULL)")):
        raise RuntimeError("Refusing lossy downgrade: the reassignment reasons would be discarded.")
    op.drop_constraint("coordinator_assignments_reassignment_has_reason", "coordinator_assignments", type_="check")
    op.drop_column("coordinator_assignments", "reason")
