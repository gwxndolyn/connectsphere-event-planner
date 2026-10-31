"""add each venue booking's purpose, preparation status and its event's primary venue

Revision ID: 20261103_1200_us24_multi_venue
Revises: 20261102_1200_us5_check_outcome
Create Date: 2026-11-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261103_1200_us24_multi_venue"
down_revision: Union[str, None] = "20261102_1200_us5_check_outcome"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US24 (SCRUM-92) AC 1: what each venue is for, e.g. "Main hall" or "Breakout A".
    # DECISION-PENDING: D66 — required, trimmed, 1 to 100 characters; existing bookings become
    # "Main venue". The server default keeps US22's create working until PR 2 asks for a purpose.
    op.add_column(
        "venue_bookings", sa.Column("purpose", sa.Text(), server_default="Main venue", nullable=False)
    )
    op.create_check_constraint(
        "venue_bookings_purpose_valid",
        "venue_bookings",
        "purpose = btrim(purpose) AND char_length(purpose) BETWEEN 1 AND 100",
    )

    # AC 4: the venue attendees see.
    # DECISION-PENDING: D68 — at most one live primary per event; a withdrawn or rejected one no
    # longer counts, so the coordinator can choose another.
    op.add_column(
        "venue_bookings", sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    # Each event's first live booking, by when it was made, becomes its primary.
    op.execute(
        """
        UPDATE venue_bookings SET is_primary = true
        WHERE id IN (
            SELECT DISTINCT ON (event_id) id FROM venue_bookings
            WHERE status IN ('requested', 'approved')
            ORDER BY event_id, created_at, id
        )
        """
    )
    op.create_index(
        "venue_bookings_one_primary_per_event",
        "venue_bookings",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("is_primary AND status IN ('requested', 'approved')"),
    )

    # AC 7: how far Venue staff are with getting each venue ready.
    # DECISION-PENDING: D73 — tracked per venue (CS3-49): not_started, in_progress or ready. Every
    # booking starts not_started, existing ones included; Venue staff move an approved one on (PR 2).
    op.add_column(
        "venue_bookings",
        sa.Column("preparation_status", sa.Text(), server_default="not_started", nullable=False),
    )
    op.create_check_constraint(
        "venue_bookings_preparation_status_known",
        "venue_bookings",
        "preparation_status IN ('not_started', 'in_progress', 'ready')",
    )


def downgrade() -> None:
    # A purpose someone gave, or preparation Venue staff recorded, would be lost; the defaults aren't,
    # and the upgrade works out the primary flag again (#96 review).
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM venue_bookings "
            "WHERE purpose <> 'Main venue' OR preparation_status <> 'not_started')"
        )
    ):
        raise RuntimeError(
            "Refusing lossy downgrade: venue booking purposes or preparation statuses would be discarded."
        )
    op.drop_constraint("venue_bookings_preparation_status_known", "venue_bookings", type_="check")
    op.drop_column("venue_bookings", "preparation_status")
    op.drop_index("venue_bookings_one_primary_per_event", table_name="venue_bookings")
    op.drop_column("venue_bookings", "is_primary")
    op.drop_constraint("venue_bookings_purpose_valid", "venue_bookings", type_="check")
    op.drop_column("venue_bookings", "purpose")
