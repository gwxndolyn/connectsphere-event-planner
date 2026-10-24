"""store each venue booking's occupied window and give bookings a reference

Revision ID: 20261024_1200_us13_buffers
Revises: 20261025_1200_us26_equipment
Create Date: 2026-10-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261024_1200_us13_buffers"
# After US26 (#63), which merged first: one Alembic head. US13 PR 1 was written on US10a.
down_revision: Union[str, None] = "20261025_1200_us26_equipment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LIVE = "status IN ('requested', 'approved')"  # D21: LIVE_BOOKING_STATUSES in app/venue/models.py


def upgrade() -> None:
    bind = op.get_bind()

    # US13 AC 2: the venue is occupied from the start of setup to the end of turnaround. An exclusion
    # constraint can only use the row's own columns, not venues.setup_minutes, so each booking stores
    # the window its venue's buffers produce (occupied_window in app/venue/models.py computes it).
    op.add_column("venue_bookings", sa.Column("occupied_starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("venue_bookings", sa.Column("occupied_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE venue_bookings AS b SET "
        "occupied_starts_at = b.starts_at - make_interval(mins => v.setup_minutes), "
        "occupied_ends_at = b.ends_at + make_interval(mins => v.turnaround_minutes) "
        "FROM venues AS v WHERE v.id = b.venue_id"
    )
    op.alter_column("venue_bookings", "occupied_starts_at", nullable=False)
    op.alter_column("venue_bookings", "occupied_ends_at", nullable=False)
    # A stored window can never be narrower than the booking itself.
    op.create_check_constraint(
        "venue_bookings_occupied_covers_window",
        "venue_bookings",
        "occupied_starts_at <= starts_at AND occupied_ends_at >= ends_at",
    )

    # DECISION-PENDING: D34 — CR-01: bookings the buffers make conflicting are identified, not
    # removed. An exclusion constraint can't be added NOT VALID, so stop and name them for a person
    # to resolve (withdraw or reject one of each pair) before rerunning.
    clashes = bind.execute(
        sa.text(
            "SELECT a.id AS first, b.id AS second, a.venue_id, "
            "a.occupied_starts_at AS a_from, a.occupied_ends_at AS a_to, "
            "b.occupied_starts_at AS b_from, b.occupied_ends_at AS b_to "
            "FROM venue_bookings a JOIN venue_bookings b ON a.venue_id = b.venue_id AND a.id < b.id "
            f"WHERE a.{LIVE} AND b.{LIVE} "
            "AND tstzrange(a.occupied_starts_at, a.occupied_ends_at, '[)') "
            "&& tstzrange(b.occupied_starts_at, b.occupied_ends_at, '[)') "
            "ORDER BY a.venue_id, a.occupied_starts_at"
        )
    ).all()
    if clashes:
        listed = "; ".join(
            f"{row.first} ({row.a_from:%Y-%m-%d %H:%M}-{row.a_to:%H:%M}) and {row.second} "
            f"({row.b_from:%Y-%m-%d %H:%M}-{row.b_to:%H:%M}) at venue {row.venue_id}"
            for row in clashes
        )
        raise RuntimeError(
            f"Refusing to add buffers: {len(clashes)} pair(s) of live bookings would overlap once setup "
            f"and turnaround are included: {listed}. Withdraw or reject one of each pair, then rerun."
        )

    # US22 AC 3 and 7, now on the occupied window (US13 AC 3): no two live bookings at one venue may
    # overlap, even by one second. '[)' lets a setup start exactly when the earlier turnaround ends.
    # D21 (decided): Requested blocks as well as Approved.
    op.execute("ALTER TABLE venue_bookings DROP CONSTRAINT venue_bookings_no_overlap")
    op.execute(
        "ALTER TABLE venue_bookings ADD CONSTRAINT venue_bookings_no_overlap "
        "EXCLUDE USING gist (venue_id WITH =, tstzrange(occupied_starts_at, occupied_ends_at, '[)') WITH &&) "
        f"WHERE ({LIVE})"
    )

    # US13 AC 4 names the conflicting booking by reference. DECISION-PENDING: D33 — VB-<year>-<6+
    # digits>, the year the booking was made in Singapore. One function, used as the column default
    # so every insert path (the API, the seed, tests) gets one.
    op.execute("CREATE SEQUENCE venue_booking_reference_seq")
    op.execute(
        "CREATE FUNCTION next_venue_booking_reference() RETURNS text LANGUAGE sql VOLATILE AS $$ "
        "SELECT 'VB-' || to_char(now() AT TIME ZONE 'Asia/Singapore', 'YYYY') || '-' "
        "|| lpad(n::text, greatest(6, length(n::text)), '0') "
        "FROM (SELECT nextval('venue_booking_reference_seq') AS n) AS next $$"
    )
    op.add_column("venue_bookings", sa.Column("reference", sa.Text(), nullable=True))
    # Existing bookings, numbered in the order they were made, under the year they were made in.
    op.execute(
        "UPDATE venue_bookings AS b SET reference = 'VB-' "
        "|| to_char(b.created_at AT TIME ZONE 'Asia/Singapore', 'YYYY') || '-' "
        "|| lpad(numbered.n::text, greatest(6, length(numbered.n::text)), '0') "
        "FROM (SELECT id, nextval('venue_booking_reference_seq') AS n "
        "      FROM (SELECT id FROM venue_bookings ORDER BY created_at, id) AS ordered) AS numbered "
        "WHERE numbered.id = b.id"
    )
    op.alter_column(
        "venue_bookings", "reference", nullable=False, server_default=sa.text("next_venue_booking_reference()")
    )
    op.create_unique_constraint("venue_bookings_reference_key", "venue_bookings", ["reference"])
    # venue_bookings already has row level security on (US22's migration); new columns inherit it.


def downgrade() -> None:
    # The occupied window and the reference can be dropped without losing a booking: the plain
    # window is a subset of the occupied one, so the old guard holds for every row that's left.
    op.drop_constraint("venue_bookings_reference_key", "venue_bookings", type_="unique")
    op.drop_column("venue_bookings", "reference")
    op.execute("DROP FUNCTION next_venue_booking_reference()")
    op.execute("DROP SEQUENCE venue_booking_reference_seq")
    op.execute("ALTER TABLE venue_bookings DROP CONSTRAINT venue_bookings_no_overlap")
    op.execute(
        "ALTER TABLE venue_bookings ADD CONSTRAINT venue_bookings_no_overlap "
        "EXCLUDE USING gist (venue_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) "
        f"WHERE ({LIVE})"
    )
    op.drop_constraint("venue_bookings_occupied_covers_window", "venue_bookings", type_="check")
    op.drop_column("venue_bookings", "occupied_ends_at")
    op.drop_column("venue_bookings", "occupied_starts_at")
