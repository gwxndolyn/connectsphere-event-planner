"""add tentative venue holds: a held status that blocks the window until it's confirmed or expires

Revision ID: 20261115_1200_us25_holds
Revises: 20261114_1200_us30a_rls
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261115_1200_us25_holds"
down_revision: Union[str, None] = "20261114_1200_us30a_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_STATUSES = ("requested", "approved", "rejected", "withdrawn")
# US25 (SCRUM-93): a hold Venue staff placed, and one that lapsed (AC 3) or lapsed after being confirmed (AC 5).
NEW_STATUSES = OLD_STATUSES + ("held", "expired")

# D21: Requested and Approved block the window; since US25 a hold does too (AC 2). Holds are not bookings
# anywhere else (AC 6), so the one-primary index keeps the old pair.
BLOCKING = "status IN ('requested', 'approved', 'held')"
OLD_BLOCKING = "status IN ('requested', 'approved')"
LIVE = "status IN ('requested', 'approved')"

STATUS_CONSTRAINTS = (
    ("venue_bookings_withdrawn_consistent", "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)"),
    (
        "venue_bookings_rejection_notes_only_when_rejected",
        "status = 'rejected' OR (rejection_reason IS NULL AND alternative_suggestion IS NULL)",
    ),
)
OLD_DECIDED = (
    "(status NOT IN ('approved', 'rejected') OR decided_at IS NOT NULL) "
    "AND (status <> 'requested' OR decided_at IS NULL)"
)
# A hold, and a confirmed hold that lapsed before Venue staff decided, has no decision yet.
NEW_DECIDED = (
    "(status NOT IN ('approved', 'rejected') OR decided_at IS NOT NULL) "
    "AND (status NOT IN ('requested', 'held', 'expired') OR decided_at IS NULL)"
)


def _overlap(where: str) -> str:
    return (
        "ALTER TABLE venue_bookings ADD CONSTRAINT venue_bookings_no_overlap "
        "EXCLUDE USING gist (venue_id WITH =, tstzrange(occupied_starts_at, occupied_ends_at, '[)') WITH &&) "
        f"WHERE ({where})"
    )


def _retype(type_name: str, values: tuple[str, ...], decided: str, overlap: str) -> None:
    """Rebuild the status type with `values`, as US16b did for roles: a value added with ADD VALUE can't be used
    until the transaction commits, and the new overlap guard needs 'held' at once. Everything that compares
    the status is dropped first and made again on the new type."""
    listed = ", ".join(f"'{value}'" for value in values)
    op.execute(f"CREATE TYPE {type_name} AS ENUM ({listed})")
    op.execute("ALTER TABLE venue_bookings DROP CONSTRAINT venue_bookings_no_overlap")
    op.drop_index("venue_bookings_one_primary_per_event", table_name="venue_bookings")
    for name, _ in STATUS_CONSTRAINTS:
        op.drop_constraint(name, "venue_bookings", type_="check")
    op.drop_constraint("venue_bookings_decided_consistent", "venue_bookings", type_="check")
    op.execute("ALTER TABLE venue_bookings ALTER COLUMN status DROP DEFAULT")
    op.execute(f"ALTER TABLE venue_bookings ALTER COLUMN status TYPE {type_name} USING status::text::{type_name}")
    op.execute("DROP TYPE venue_booking_status")
    op.execute(f"ALTER TYPE {type_name} RENAME TO venue_booking_status")
    op.execute("ALTER TABLE venue_bookings ALTER COLUMN status SET DEFAULT 'requested'")
    for name, condition in STATUS_CONSTRAINTS:
        op.create_check_constraint(name, "venue_bookings", condition)
    op.create_check_constraint("venue_bookings_decided_consistent", "venue_bookings", decided)
    op.execute(_overlap(overlap))
    op.create_index(
        "venue_bookings_one_primary_per_event",
        "venue_bookings",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text(f"is_primary AND {LIVE}"),
    )


def upgrade() -> None:
    _retype("venue_booking_status_us25", NEW_STATUSES, NEW_DECIDED, BLOCKING)

    # AC 1: who placed the hold and until when. Kept once the hold is confirmed into a request (AC 5), so Venue
    # staff must decide it before the same expiry.
    op.add_column("venue_bookings", sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("venue_bookings", sa.Column("held_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_venue_bookings_held_by_user_id_users", "venue_bookings", "users", ["held_by_user_id"], ["id"]
    )
    # AC 4: the 24-hour warning went out (D2: sent on the first read inside the last 24 hours, once).
    op.add_column("venue_bookings", sa.Column("hold_warned_at", sa.DateTime(timezone=True), nullable=True))
    # AC 3: when the hold lapsed.
    op.add_column("venue_bookings", sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True))

    op.create_check_constraint(
        "venue_bookings_hold_consistent",
        "venue_bookings",
        "(hold_expires_at IS NULL) = (held_by_user_id IS NULL) "
        "AND (status NOT IN ('held', 'expired') OR hold_expires_at IS NOT NULL) "
        "AND (hold_warned_at IS NULL OR hold_expires_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "venue_bookings_expired_consistent", "venue_bookings", "(status = 'expired') = (expired_at IS NOT NULL)"
    )
    # A hold isn't a venue the event has yet (AC 6), so it can't be the one attendees see (US24, D68).
    op.create_check_constraint("venue_bookings_hold_not_primary", "venue_bookings", "status <> 'held' OR NOT is_primary")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM venue_bookings WHERE hold_expires_at IS NOT NULL)")):
        raise RuntimeError("Refusing lossy downgrade: venue holds, or bookings confirmed from one, would be discarded.")
    op.drop_constraint("venue_bookings_hold_not_primary", "venue_bookings", type_="check")
    op.drop_constraint("venue_bookings_expired_consistent", "venue_bookings", type_="check")
    op.drop_constraint("venue_bookings_hold_consistent", "venue_bookings", type_="check")
    op.drop_column("venue_bookings", "expired_at")
    op.drop_column("venue_bookings", "hold_warned_at")
    op.drop_constraint("fk_venue_bookings_held_by_user_id_users", "venue_bookings", type_="foreignkey")
    op.drop_column("venue_bookings", "held_by_user_id")
    op.drop_column("venue_bookings", "hold_expires_at")
    _retype("venue_booking_status_old", OLD_STATUSES, OLD_DECIDED, OLD_BLOCKING)
