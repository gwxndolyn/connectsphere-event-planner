"""add Tech support staff assignments to events, which are also their log

Revision ID: 20261107_1200_us14_tech_staff
Revises: 20261106_1200_scrum118_grants
Create Date: 2026-11-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261107_1200_us14_tech_staff"
down_revision: Union[str, None] = "20261106_1200_scrum118_grants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US14 (SCRUM-17) AC 3, 5, 6. D79 (decided by the acting PO, 31 Oct): one row per assignment, active
    # until it's unassigned, and the rows are the log of who assigned and unassigned whom, and when.
    # Reassigning is an unassign and an assign, so both are logged.
    op.create_table(
        "tech_staff_assignments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("staff_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("unassigned_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # An unassign is both who and when.
        sa.CheckConstraint(
            "(unassigned_at IS NULL) = (unassigned_by_user_id IS NULL)",
            name="tech_staff_assignments_unassigned_consistent",
        ),
    )
    # One active assignment per person per event; once unassigned, they can be assigned again.
    op.create_index(
        "tech_staff_assignments_one_active",
        "tech_staff_assignments",
        ["event_id", "staff_user_id"],
        unique=True,
        postgresql_where=sa.text("unassigned_at IS NULL"),
    )
    # SCRUM-134's availability check reads a person's active assignments.
    op.create_index(
        "ix_tech_staff_assignments_active_staff",
        "tech_staff_assignments",
        ["staff_user_id"],
        postgresql_where=sa.text("unassigned_at IS NULL"),
    )
    op.execute("ALTER TABLE tech_staff_assignments ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM tech_staff_assignments)")):
        raise RuntimeError(
            "Refusing lossy downgrade: Tech support staff assignments and their log would be discarded."
        )
    op.drop_table("tech_staff_assignments")
