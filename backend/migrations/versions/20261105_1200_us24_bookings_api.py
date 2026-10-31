"""require each booking's purpose and let a withdrawn booking keep its decision

Revision ID: 20261105_1200_us24_bookings_api
Revises: 20261103_1200_us24_multi_venue
Create Date: 2026-11-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261105_1200_us24_bookings_api"
down_revision: Union[str, None] = "20261103_1200_us24_multi_venue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STRICT = "(status IN ('approved', 'rejected')) = (decided_at IS NOT NULL)"


def upgrade() -> None:
    # US24 PR 2 (SCRUM-128). DECISION-PENDING: D66 — the API asks every request for its purpose now,
    # so the column no longer fills one in.
    op.alter_column("venue_bookings", "purpose", server_default=None)

    # DECISION-PENDING: D77 — an approved booking can be withdrawn (D69) and keeps who approved it and
    # when. Approved and rejected bookings still need a decision time and a pending one has none.
    op.drop_constraint("venue_bookings_decided_consistent", "venue_bookings", type_="check")
    op.create_check_constraint(
        "venue_bookings_decided_consistent",
        "venue_bookings",
        "(status NOT IN ('approved', 'rejected') OR decided_at IS NOT NULL) "
        "AND (status <> 'requested' OR decided_at IS NULL)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM venue_bookings WHERE status = 'withdrawn' AND decided_at IS NOT NULL)")
    ):
        raise RuntimeError("Refusing lossy downgrade: withdrawn venue bookings' decisions would be discarded.")
    op.drop_constraint("venue_bookings_decided_consistent", "venue_bookings", type_="check")
    op.create_check_constraint("venue_bookings_decided_consistent", "venue_bookings", STRICT)
    op.alter_column("venue_bookings", "purpose", server_default="Main venue")
