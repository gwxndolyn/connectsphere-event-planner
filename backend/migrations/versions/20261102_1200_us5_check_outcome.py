"""record the latest equipment availability check on its request line

Revision ID: 20261102_1200_us5_check_outcome
Revises: 20261101_1200_us5_equipment
Create Date: 2026-11-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261102_1200_us5_check_outcome"
down_revision: Union[str, None] = "20261101_1200_us5_equipment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # D64 (decided by the acting PO, 30 Oct). US5 AC 5 "records the outcome": the latest check is kept on
    # the line, who and when with it; a newer check replaces it, and editing its quantity or type clears it.
    op.add_column("equipment_request_lines", sa.Column("availability_checked_at", sa.DateTime(timezone=True)))
    op.add_column(
        "equipment_request_lines",
        sa.Column("availability_checked_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("equipment_request_lines", sa.Column("availability_sufficient", sa.Boolean()))
    op.add_column("equipment_request_lines", sa.Column("availability_shortfall", sa.Integer()))
    # All or nothing, and the shortfall agrees with the outcome: sufficient means short by 0.
    op.create_check_constraint(
        "equipment_request_lines_availability_check_consistent",
        "equipment_request_lines",
        "(availability_checked_at IS NULL AND availability_checked_by_user_id IS NULL"
        " AND availability_sufficient IS NULL AND availability_shortfall IS NULL)"
        " OR (availability_checked_at IS NOT NULL AND availability_checked_by_user_id IS NOT NULL"
        " AND availability_sufficient IS NOT NULL AND availability_shortfall IS NOT NULL"
        " AND ((availability_sufficient AND availability_shortfall = 0)"
        " OR (NOT availability_sufficient AND availability_shortfall > 0)))",
    )


def downgrade() -> None:
    op.drop_constraint("equipment_request_lines_availability_check_consistent", "equipment_request_lines", type_="check")
    op.drop_column("equipment_request_lines", "availability_shortfall")
    op.drop_column("equipment_request_lines", "availability_sufficient")
    op.drop_column("equipment_request_lines", "availability_checked_by_user_id")
    op.drop_column("equipment_request_lines", "availability_checked_at")
