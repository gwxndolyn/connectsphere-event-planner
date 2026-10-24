"""record Venue Staff's decision on a venue booking

Revision ID: 20261025_1300_us4_decisions
Revises: 20261024_1200_us13_buffers
Create Date: 2026-10-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261025_1300_us4_decisions"
down_revision: Union[str, None] = "20261024_1200_us13_buffers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US4 (SCRUM-8): who approved or rejected a request, when, and (on a rejection) why and what
    # else might work (AC 5). Nullable: a pending or withdrawn booking has no decision.
    op.add_column("venue_bookings", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("venue_bookings", sa.Column("decided_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("venue_bookings", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("venue_bookings", sa.Column("alternative_suggestion", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_venue_bookings_decided_by_user_id_users", "venue_bookings", "users", ["decided_by_user_id"], ["id"]
    )
    # Bookings approved or rejected before US4 (only the seed and tests make them) get their last
    # change as the decision time; who decided is unknown, so decided_by_user_id stays null.
    op.execute(
        "UPDATE venue_bookings SET decided_at = updated_at "
        "WHERE status IN ('approved', 'rejected') AND decided_at IS NULL"
    )
    # A booking has a decision time exactly when it was approved or rejected, like withdrawn_at.
    op.create_check_constraint(
        "venue_bookings_decided_consistent",
        "venue_bookings",
        "(status IN ('approved', 'rejected')) = (decided_at IS NOT NULL)",
    )
    # A reason or a suggested alternative only goes with a rejection (AC 5).
    op.create_check_constraint(
        "venue_bookings_rejection_notes_only_when_rejected",
        "venue_bookings",
        "status = 'rejected' OR (rejection_reason IS NULL AND alternative_suggestion IS NULL)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM venue_bookings WHERE decided_by_user_id IS NOT NULL "
            "OR rejection_reason IS NOT NULL OR alternative_suggestion IS NOT NULL)"
        )
    ):
        raise RuntimeError("Refusing lossy downgrade: venue booking decisions would be discarded.")
    op.drop_constraint("venue_bookings_rejection_notes_only_when_rejected", "venue_bookings", type_="check")
    op.drop_constraint("venue_bookings_decided_consistent", "venue_bookings", type_="check")
    op.drop_constraint("fk_venue_bookings_decided_by_user_id_users", "venue_bookings", type_="foreignkey")
    op.drop_column("venue_bookings", "alternative_suggestion")
    op.drop_column("venue_bookings", "rejection_reason")
    op.drop_column("venue_bookings", "decided_by_user_id")
    op.drop_column("venue_bookings", "decided_at")
