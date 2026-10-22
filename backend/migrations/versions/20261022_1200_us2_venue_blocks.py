"""add venue blocks, the closures venue search leaves out

Revision ID: 20261022_1200_us2_venue_blocks
Revises: 20261021_1200_us22_bookings
Create Date: 2026-10-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261022_1200_us2_venue_blocks"
down_revision: Union[str, None] = "20261021_1200_us22_bookings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US2 AC 5: a venue "blocked for the requested date and time" is out of use with no event behind
    # it (maintenance, a closure), so it can't be a venue_bookings row, whose event and requester are
    # required. US23a (SCRUM-90, CR-02) builds Venue Staff's screens for these.
    op.create_table(
        "venue_blocks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], name="fk_venue_blocks_venue_id_venues"),
        sa.CheckConstraint("ends_at > starts_at", name="venue_blocks_window_valid"),
    )
    # US2 AC 8: search finds a venue's blocks by range overlap (&&). GiST on the same expression as
    # venue_bookings_no_overlap's index, so one query shape serves both; btree_gist (enabled by
    # US22's migration, which runs first) lets it hold venue_id with =. Not an exclusion constraint:
    # blocks may overlap each other.
    op.execute(
        "CREATE INDEX venue_blocks_venue_window ON venue_blocks "
        "USING gist (venue_id, tstzrange(starts_at, ends_at, '[)'))"
    )
    op.execute("ALTER TABLE venue_blocks ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM venue_blocks)")):
        raise RuntimeError("Refusing lossy downgrade: venue blocks would be discarded.")
    op.drop_index("venue_blocks_venue_window", table_name="venue_blocks")
    op.drop_table("venue_blocks")
