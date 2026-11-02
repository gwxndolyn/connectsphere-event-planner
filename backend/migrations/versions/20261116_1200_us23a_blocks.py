"""add a reason to venue blocks, and mark the bookings a block leaves needing rearrangement

Revision ID: 20261116_1200_us23a_blocks
Revises: 20261115_1200_us25_holds
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261116_1200_us23a_blocks"
down_revision: Union[str, None] = "20261115_1200_us25_holds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# US23a (SCRUM-90) AC 1: VenueBlockReason's values, stored as text like preparation_status (D73). Change both together.
REASONS = ("maintenance", "equipment_failure", "renovation", "safety", "other")


def upgrade() -> None:
    # AC 1: why the venue is out of use. Blocks made before US23a (the seed's) have none, so they read as "other";
    # the default only fills them and is then dropped, so every new block names its reason.
    op.add_column("venue_blocks", sa.Column("reason", sa.Text(), server_default="other", nullable=False))
    op.alter_column("venue_blocks", "reason", server_default=None)
    listed = ", ".join(f"'{reason}'" for reason in REASONS)
    op.create_check_constraint("venue_blocks_reason_known", "venue_blocks", f"reason IN ({listed})")
    # Who recorded it; null for blocks made before US23a.
    op.add_column("venue_blocks", sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_venue_blocks_created_by_user_id_users", "venue_blocks", "users", ["created_by_user_id"], ["id"]
    )

    # AC 3 (D113): a booking or hold the block overlaps is marked "Needs rearrangement" by naming the block, and keeps
    # its status, so US23b (SCRUM-91) can replace it or restore it. Nothing else on it changes.
    op.add_column("venue_bookings", sa.Column("rearrangement_block_id", sa.Uuid(), nullable=True))
    op.add_column("venue_bookings", sa.Column("rearrangement_flagged_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_venue_bookings_rearrangement_block_id_venue_blocks",
        "venue_bookings",
        "venue_blocks",
        ["rearrangement_block_id"],
        ["id"],
    )
    op.create_check_constraint(
        "venue_bookings_rearrangement_consistent",
        "venue_bookings",
        "(rearrangement_block_id IS NULL) = (rearrangement_flagged_at IS NULL)",
    )
    # A block's affected bookings, for the screens that list them. Partial: almost no booking is ever flagged.
    op.create_index(
        "ix_venue_bookings_rearrangement_block_id",
        "venue_bookings",
        ["rearrangement_block_id"],
        postgresql_where=sa.text("rearrangement_block_id IS NOT NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    lossy = bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM venue_bookings WHERE rearrangement_block_id IS NOT NULL) "
            "OR EXISTS (SELECT 1 FROM venue_blocks WHERE reason <> 'other' OR created_by_user_id IS NOT NULL)"
        )
    )
    if lossy:
        raise RuntimeError(
            "Refusing lossy downgrade: block reasons, who recorded them, or bookings needing rearrangement would be discarded."
        )
    op.drop_index("ix_venue_bookings_rearrangement_block_id", table_name="venue_bookings")
    op.drop_constraint("venue_bookings_rearrangement_consistent", "venue_bookings", type_="check")
    op.drop_constraint("fk_venue_bookings_rearrangement_block_id_venue_blocks", "venue_bookings", type_="foreignkey")
    op.drop_column("venue_bookings", "rearrangement_flagged_at")
    op.drop_column("venue_bookings", "rearrangement_block_id")
    op.drop_constraint("fk_venue_blocks_created_by_user_id_users", "venue_blocks", type_="foreignkey")
    op.drop_column("venue_blocks", "created_by_user_id")
    op.drop_constraint("venue_blocks_reason_known", "venue_blocks", type_="check")
    op.drop_column("venue_blocks", "reason")
