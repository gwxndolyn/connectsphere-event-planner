"""link each equipment reservation to the approved line it fulfils, and who reserved it

Revision ID: 20261104_1200_us27_reservations
Revises: 20261103_1200_us24_multi_venue
Create Date: 2026-11-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261104_1200_us27_reservations"
down_revision: Union[str, None] = "20261103_1200_us24_multi_venue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _refuse_if_reservations(action: str) -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM equipment_reservations)")):
        raise RuntimeError(f"Refusing to {action}: equipment_reservations has rows, and they have no line to link.")


def upgrade() -> None:
    # US5 created the table and nothing writes it before US27's API, so it's empty; the new columns
    # are NOT NULL and an existing row couldn't say which line it fulfils.
    _refuse_if_reservations("add the reservation's line")

    # US27 (SCRUM-95) AC 1, 6: a reservation fulfils one approved line, for that line's full quantity.
    op.add_column("equipment_reservations", sa.Column("request_line_id", sa.Uuid(), nullable=False))
    op.add_column(
        "equipment_reservations",
        sa.Column(
            "reserved_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="equipment_reservations_reserved_by_user_id_fkey"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "equipment_reservations_request_line_id_key", "equipment_reservations", ["request_line_id"]
    )
    # The reservation's event and type are its line's: a composite foreign key onto the line's id, event
    # and type, so they can't disagree (US5's check reads event_id and equipment_type_id directly).
    op.create_unique_constraint(
        "equipment_request_lines_id_event_type_key",
        "equipment_request_lines",
        ["id", "event_id", "equipment_type_id"],
    )
    op.create_foreign_key(
        "equipment_reservations_line_fkey",
        "equipment_reservations",
        "equipment_request_lines",
        ["request_line_id", "event_id", "equipment_type_id"],
        ["id", "event_id", "equipment_type_id"],
    )


def downgrade() -> None:
    _refuse_if_reservations("drop the reservation's line")
    op.drop_constraint("equipment_reservations_line_fkey", "equipment_reservations", type_="foreignkey")
    op.drop_constraint("equipment_request_lines_id_event_type_key", "equipment_request_lines", type_="unique")
    op.drop_constraint("equipment_reservations_request_line_id_key", "equipment_reservations", type_="unique")
    op.drop_column("equipment_reservations", "reserved_by_user_id")
    op.drop_column("equipment_reservations", "request_line_id")
