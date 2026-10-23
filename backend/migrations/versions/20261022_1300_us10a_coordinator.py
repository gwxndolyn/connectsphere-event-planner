"""add coordinator assignment groundwork

Revision ID: 20261022_1300_us10a_coordinator
Revises: 20261022_1200_us2_venue_blocks
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261022_1300_us10a_coordinator"
down_revision: Union[str, None] = "20261022_1200_us2_venue_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DECISION-PENDING: SCRUM-82 owns the new roles. US10a needs the Lead first, so this adds only
    # that one value; US16b must not add it again and should add the rest after it.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'coordinator_lead' AFTER 'coordinator'")

    # NULL means unassigned: the Lead's queue is submitted requests with no coordinator (SCRUM-13 AC 1).
    op.add_column("events", sa.Column("coordinator_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_events_coordinator_id_users", "events", "users", ["coordinator_id"], ["id"])
    op.create_index("ix_events_coordinator_id", "events", ["coordinator_id"])


def downgrade() -> None:
    op.drop_index("ix_events_coordinator_id", table_name="events")
    op.drop_constraint("fk_events_coordinator_id_users", "events", type_="foreignkey")
    op.drop_column("events", "coordinator_id")
    # Postgres can't drop an enum value, so 'coordinator_lead' stays in user_role.
