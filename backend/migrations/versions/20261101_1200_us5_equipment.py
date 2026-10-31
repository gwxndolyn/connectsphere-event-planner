"""add equipment stock, out-of-service count, storage location and reservations

Revision ID: 20261101_1200_us5_equipment
Revises: 20261031_1200_us16b_d51_checks
Create Date: 2026-11-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261101_1200_us5_equipment"
down_revision: Union[str, None] = "20261031_1200_us16b_d51_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DECISION-PENDING: D62. Stock is counted per type (customer clarification 1, D41); damaged, under
    # repair and otherwise unavailable units are one count (US5 AC 3). Existing types own nothing until
    # stock is recorded, which is the seed's job for now (D63).
    op.add_column("equipment_types", sa.Column("total_quantity", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "equipment_types", sa.Column("out_of_service_quantity", sa.Integer(), server_default="0", nullable=False)
    )
    # US5 AC 7: where it's kept, for reference only.
    op.add_column("equipment_types", sa.Column("storage_location", sa.Text(), nullable=True))
    # One check, so a negative stock is always refused under this name (Postgres tests CHECKs by name).
    op.create_check_constraint(
        "equipment_types_stock_in_range",
        "equipment_types",
        "out_of_service_quantity >= 0 AND out_of_service_quantity <= total_quantity",
    )
    op.create_check_constraint(
        "equipment_types_storage_location_not_blank", "equipment_types", "btrim(storage_location) <> ''"
    )

    # US27 (SCRUM-95) reserves equipment; US5's check subtracts other events' reservations (AC 2), so the
    # table comes first. US27 adds the link to the approved line, who reserved and release in its own migration.
    op.create_table(
        "equipment_reservations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("equipment_type_id", sa.Uuid(), sa.ForeignKey("equipment_types.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity > 0", name="equipment_reservations_quantity_positive"),
    )
    # The check sums a type's reservations.
    op.create_index("ix_equipment_reservations_equipment_type_id", "equipment_reservations", ["equipment_type_id"])
    op.execute("ALTER TABLE equipment_reservations ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM equipment_reservations)")):
        raise RuntimeError("Refusing lossy downgrade: equipment reservations would be discarded.")
    op.drop_table("equipment_reservations")
    op.drop_constraint("equipment_types_storage_location_not_blank", "equipment_types", type_="check")
    op.drop_constraint("equipment_types_stock_in_range", "equipment_types", type_="check")
    op.drop_column("equipment_types", "storage_location")
    op.drop_column("equipment_types", "out_of_service_quantity")
    op.drop_column("equipment_types", "total_quantity")
