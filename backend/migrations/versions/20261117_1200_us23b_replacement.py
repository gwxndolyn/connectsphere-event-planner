"""replace or restore a booking that needs rearrangement, and let Venue staff end a venue block early

Revision ID: 20261117_1200_us23b_replacement
Revises: 20261116_1200_us31_notifications
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261117_1200_us23b_replacement"
down_revision: Union[str, None] = "20261116_1200_us31_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US23b (SCRUM-91) AC 4 (D117): once its replacement is approved, the original booking is Replaced. Like withdrawn
    # and expired, a replaced booking no longer holds its window. Added with ADD VALUE (as US10a did) rather than by
    # rebuilding the type: nothing below compares the status with the new value as an enum, only as text, so it
    # needn't be committed first.
    op.execute("ALTER TYPE venue_booking_status ADD VALUE IF NOT EXISTS 'replaced'")
    op.add_column("venue_bookings", sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "venue_bookings_replaced_consistent",
        "venue_bookings",
        # Only a booking needing rearrangement is replaced, so it keeps the block's marker (Chloe's #134 review).
        "(status::text = 'replaced') = (replaced_at IS NOT NULL) "
        "AND (status::text <> 'replaced' OR rearrangement_block_id IS NOT NULL)",
    )

    # AC 3: a replacement is a new request that names the booking it replaces.
    op.add_column("venue_bookings", sa.Column("replaces_booking_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_venue_bookings_replaces_booking_id_venue_bookings",
        "venue_bookings",
        "venue_bookings",
        ["replaces_booking_id"],
        ["id"],
    )
    op.create_check_constraint(
        "venue_bookings_replaces_another", "venue_bookings", "replaces_booking_id IS NULL OR replaces_booking_id <> id"
    )
    # D117: at most one live replacement per booking. It is requested as non-primary while the original holds the
    # primary (venue_bookings_one_primary_per_event, D68, which isn't deferrable); approving it makes the original
    # Replaced first and then the replacement primary, in one transaction (Chloe's #134 review). One that is rejected or withdrawn makes way for another. Over
    # every status that holds a window (BLOCKING_STATUSES), so a held one would count too (Matt's #134 review), though
    # a replacement is always a request.
    op.create_index(
        "venue_bookings_one_live_replacement",
        "venue_bookings",
        ["replaces_booking_id"],
        unique=True,
        postgresql_where=sa.text("replaces_booking_id IS NOT NULL AND status IN ('requested', 'approved', 'held')"),
    )

    # AC 5 (D118): the coordinator asks to restore a booking that needs rearrangement; Venue staff confirm or decline,
    # which clears the request. Only a marked booking can be asked for.
    op.add_column("venue_bookings", sa.Column("restore_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("venue_bookings", sa.Column("restore_requested_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_venue_bookings_restore_requested_by_user_id_users",
        "venue_bookings",
        "users",
        ["restore_requested_by_user_id"],
        ["id"],
    )
    op.create_check_constraint(
        "venue_bookings_restore_consistent",
        "venue_bookings",
        "(restore_requested_at IS NULL) = (restore_requested_by_user_id IS NULL) "
        "AND (restore_requested_at IS NULL OR rearrangement_block_id IS NOT NULL) "
        # Only while the booking or hold is live (BLOCKING_STATUSES): replacing, withdrawing, rejecting, cancelling or
        # expiring it clears the request in the same update (Chloe's #134 review).
        "AND (restore_requested_at IS NULL OR status::text IN ('requested', 'approved', 'held'))",
    )
    # AC 5 (D118, Matt's #134 review): Venue staff's last decline, when, who and why, so the coordinator sees it on the
    # event. Kept until the coordinator asks again; a reason only with a decline.
    op.add_column("venue_bookings", sa.Column("restore_declined_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("venue_bookings", sa.Column("restore_declined_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("venue_bookings", sa.Column("restore_decline_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_venue_bookings_restore_declined_by_user_id_users",
        "venue_bookings",
        "users",
        ["restore_declined_by_user_id"],
        ["id"],
    )
    op.create_check_constraint(
        "venue_bookings_restore_decline_consistent",
        "venue_bookings",
        "(restore_declined_at IS NULL) = (restore_declined_by_user_id IS NULL) "
        "AND (restore_decline_reason IS NULL OR restore_declined_at IS NOT NULL)",
    )

    # AC 5 (D118): Venue staff end a block early, so its venue can be free again. ends_at moves to when it was ended
    # (or to its start, if it hadn't begun: an empty range, which overlaps nothing), and scheduled_ends_at keeps the
    # end it had. Search, the availability check and the calendar read ends_at as before.
    op.add_column("venue_blocks", sa.Column("ended_early_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("venue_blocks", sa.Column("ended_early_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("venue_blocks", sa.Column("scheduled_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_venue_blocks_ended_early_by_user_id_users", "venue_blocks", "users", ["ended_early_by_user_id"], ["id"]
    )
    op.drop_constraint("venue_blocks_window_valid", "venue_blocks", type_="check")
    op.create_check_constraint(
        "venue_blocks_window_valid",
        "venue_blocks",
        "ends_at > starts_at OR (ended_early_at IS NOT NULL AND ends_at = starts_at)",
    )
    op.create_check_constraint(
        "venue_blocks_ended_early_consistent",
        "venue_blocks",
        "(ended_early_at IS NULL) = (ended_early_by_user_id IS NULL) "
        "AND (ended_early_at IS NULL) = (scheduled_ends_at IS NULL) "
        "AND (scheduled_ends_at IS NULL OR ends_at < scheduled_ends_at)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    lossy = bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM venue_bookings WHERE status::text = 'replaced' "
            "OR replaces_booking_id IS NOT NULL OR restore_requested_at IS NOT NULL OR restore_declined_at IS NOT NULL) "
            "OR EXISTS (SELECT 1 FROM venue_blocks WHERE ended_early_at IS NOT NULL)"
        )
    )
    if lossy:
        raise RuntimeError(
            "Refusing lossy downgrade: replaced bookings, replacement or restore requests, declined restores, "
            "or venue blocks ended early would be discarded."
        )
    op.drop_constraint("venue_blocks_ended_early_consistent", "venue_blocks", type_="check")
    op.drop_constraint("venue_blocks_window_valid", "venue_blocks", type_="check")
    op.create_check_constraint("venue_blocks_window_valid", "venue_blocks", "ends_at > starts_at")
    op.drop_constraint("fk_venue_blocks_ended_early_by_user_id_users", "venue_blocks", type_="foreignkey")
    op.drop_column("venue_blocks", "scheduled_ends_at")
    op.drop_column("venue_blocks", "ended_early_by_user_id")
    op.drop_column("venue_blocks", "ended_early_at")
    op.drop_constraint("venue_bookings_restore_decline_consistent", "venue_bookings", type_="check")
    op.drop_constraint("fk_venue_bookings_restore_declined_by_user_id_users", "venue_bookings", type_="foreignkey")
    op.drop_column("venue_bookings", "restore_decline_reason")
    op.drop_column("venue_bookings", "restore_declined_by_user_id")
    op.drop_column("venue_bookings", "restore_declined_at")
    op.drop_constraint("venue_bookings_restore_consistent", "venue_bookings", type_="check")
    op.drop_constraint("fk_venue_bookings_restore_requested_by_user_id_users", "venue_bookings", type_="foreignkey")
    op.drop_column("venue_bookings", "restore_requested_by_user_id")
    op.drop_column("venue_bookings", "restore_requested_at")
    op.drop_index("venue_bookings_one_live_replacement", table_name="venue_bookings")
    op.drop_constraint("venue_bookings_replaces_another", "venue_bookings", type_="check")
    op.drop_constraint("fk_venue_bookings_replaces_booking_id_venue_bookings", "venue_bookings", type_="foreignkey")
    op.drop_column("venue_bookings", "replaces_booking_id")
    op.drop_constraint("venue_bookings_replaced_consistent", "venue_bookings", type_="check")
    op.drop_column("venue_bookings", "replaced_at")
    # Postgres can't drop one value from a type, and no row uses 'replaced' (checked above), so the value stays;
    # VenueBookingStatus without it never writes it.
