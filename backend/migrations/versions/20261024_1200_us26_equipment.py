"""add equipment catalogue, request lines and the tech_support role

Revision ID: 20261024_1200_us26_equipment
Revises: 20261022_1300_us10a_coordinator
Create Date: 2026-10-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261024_1200_us26_equipment"
down_revision: Union[str, None] = "20261022_1300_us10a_coordinator"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Technical Support Staff (US26). The name US16b (SCRUM-82) plans for the role; it adds the others.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'tech_support'")

    op.create_table(
        "equipment_types",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="equipment_types_name_key"),
        sa.CheckConstraint("btrim(name) <> ''", name="equipment_types_name_not_blank"),
    )
    op.execute("ALTER TABLE equipment_types ENABLE ROW LEVEL SECURITY")

    line_status = postgresql.ENUM("pending", "approved", "rejected", name="equipment_line_status")
    line_status.create(op.get_bind())
    op.create_table(
        "equipment_request_lines",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("equipment_type_id", sa.Uuid(), sa.ForeignKey("equipment_types.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="equipment_line_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # US26 AC 4: quantity must be a positive whole number.
        sa.CheckConstraint("quantity > 0", name="equipment_request_lines_quantity_positive"),
    )
    op.execute("ALTER TABLE equipment_request_lines ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM equipment_request_lines)")):
        raise RuntimeError("Refusing lossy downgrade: equipment request lines would be discarded.")
    op.drop_table("equipment_request_lines")
    sa.Enum(name="equipment_line_status").drop(bind)
    op.drop_table("equipment_types")
    # Postgres can't drop one value from an enum, so 'tech_support' stays in user_role; it's unused
    # without the equipment routes, and the upgrade's IF NOT EXISTS makes re-applying safe.
