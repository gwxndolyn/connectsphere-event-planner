"""add the Preparation status and what confirming an event records

Revision ID: 20261101_1200_us18_confirm
Revises: 20261031_1200_us16b_d51_checks
Create Date: 2026-11-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261101_1200_us18_confirm"
down_revision: Union[str, None] = "20261031_1200_us16b_d51_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US18 (SCRUM-85): Preparation is its own status after Confirmed (customer session 3, 13 Oct).
    op.execute("ALTER TYPE event_status ADD VALUE IF NOT EXISTS 'preparation' AFTER 'confirmed'")
    # The Safety Officer's approval (US30a, not built yet): confirming needs it (AC 1). Both columns are
    # set together by whoever approves; US30a writes them, and until then the seed and tests do.
    op.add_column("events", sa.Column("safety_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("events", sa.Column("safety_approved_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_events_safety_approved_by_user_id_users", "events", "users", ["safety_approved_by_user_id"], ["id"]
    )
    op.create_check_constraint(
        "events_safety_approval_consistent",
        "events",
        "(safety_approved_at IS NULL) = (safety_approved_by_user_id IS NULL)",
    )
    # Who confirmed the event and when (AC 3). Null until confirmed, and for events made before US18
    # (the seed and tests put them straight into Confirmed), so nothing is backfilled.
    op.add_column("events", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("events", sa.Column("confirmed_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_events_confirmed_by_user_id_users", "events", "users", ["confirmed_by_user_id"], ["id"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM events WHERE status::text = 'preparation' "
            "OR confirmed_at IS NOT NULL OR confirmed_by_user_id IS NOT NULL "
            "OR safety_approved_at IS NOT NULL OR safety_approved_by_user_id IS NOT NULL)"
        )
    ):
        raise RuntimeError("Refusing lossy downgrade: confirmations, safety approvals or Preparation events exist.")
    op.drop_constraint("fk_events_confirmed_by_user_id_users", "events", type_="foreignkey")
    op.drop_column("events", "confirmed_by_user_id")
    op.drop_column("events", "confirmed_at")
    op.drop_constraint("events_safety_approval_consistent", "events", type_="check")
    op.drop_constraint("fk_events_safety_approved_by_user_id_users", "events", type_="foreignkey")
    op.drop_column("events", "safety_approved_by_user_id")
    op.drop_column("events", "safety_approved_at")
    # Postgres can't drop an enum value, so 'preparation' stays in the type (the roles migration did the same).
