"""let an organiser request a change to a submitted event, with a reason

Revision ID: 20261109_1200_us29a_change_reqs
Revises: 20261108_1200_us12_event_edits
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261109_1200_us29a_change_reqs"
down_revision: Union[str, None] = "20261108_1200_us12_event_edits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US29a (SCRUM-97) AC 3: an organiser's change request carries their reason. Nullable: a coordinator's US12
    # edit has none, and the service requires one on every organiser request. Reuses US12's table and its
    # pending_approval status (AC 4's "Pending"), so US29b reviews both kinds in one place.
    op.add_column("event_change_requests", sa.Column("reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "event_change_requests_reason_not_blank",
        "event_change_requests",
        "reason IS NULL OR btrim(reason) <> ''",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM event_change_requests WHERE reason IS NOT NULL)")):
        raise RuntimeError("Refusing lossy downgrade: organisers' change request reasons would be discarded.")
    op.drop_constraint("event_change_requests_reason_not_blank", "event_change_requests", type_="check")
    op.drop_column("event_change_requests", "reason")
