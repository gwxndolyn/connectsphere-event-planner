"""add venue booking requests

Revision ID: 20261021_1200_us22_bookings
Revises: 20261015_1200_us16a_auth_link
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261021_1200_us22_bookings"
down_revision: Union[str, None] = "20261015_1200_us16a_auth_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Kept in step with FACILITIES, ACCESSIBILITY_FEATURES and ROOM_LAYOUTS in app/venue/models.py (D18),
# and with the copy in migrations/versions/20261013_1200_us20_venues.py (venues' CHECKs).
# Change all three together.
FACILITIES = (
    "projector",
    "screen",
    "sound_system",
    "microphone",
    "stage",
    "wifi",
    "whiteboard",
    "video_conferencing",
    "power_outlets",
)
ACCESSIBILITY_FEATURES = ("wheelchair", "lift", "accessible_toilet", "hearing_loop", "step_free_entrance")
ROOM_LAYOUTS = ("theatre", "classroom", "banquet", "boardroom", "u_shape", "cabaret", "standing")


def _array(values: tuple[str, ...]) -> str:
    return "ARRAY[" + ", ".join(f"'{value}'" for value in values) + "]::text[]"


def _tags(name: str) -> sa.Column:
    return sa.Column(name, postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False)


def upgrade() -> None:
    # The overlap guard compares venue_id with = inside a GiST index, which needs btree_gist.
    # Supabase ships it; applying this migration there installs it if it isn't already.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "venue_bookings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_attendees", sa.Integer(), nullable=False),
        sa.Column("room_layout", sa.Text(), nullable=False),
        _tags("required_facilities"),
        _tags("required_accessibility_features"),
        sa.Column("special_requirements", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("requested", "approved", "rejected", "withdrawn", name="venue_booking_status"),
            server_default="requested",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_venue_bookings_event_id_events"),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], name="fk_venue_bookings_venue_id_venues"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], name="fk_venue_bookings_requested_by_user_id_users"
        ),
        # Named so PR 2's API can say which field (TC-US22-07).
        sa.CheckConstraint("ends_at > starts_at", name="venue_bookings_window_valid"),
        sa.CheckConstraint("expected_attendees >= 1", name="venue_bookings_expected_attendees_positive"),
        # Layout and tags come from D18's fixed lists; empty tag lists are allowed.
        sa.CheckConstraint(f"room_layout = ANY ({_array(ROOM_LAYOUTS)})", name="venue_bookings_room_layout_known"),
        sa.CheckConstraint(
            f"required_facilities <@ {_array(FACILITIES)}", name="venue_bookings_required_facilities_known"
        ),
        sa.CheckConstraint(
            f"required_accessibility_features <@ {_array(ACCESSIBILITY_FEATURES)}",
            name="venue_bookings_required_accessibility_features_known",
        ),
        # A withdrawn booking records when, and nothing else carries a withdrawal time (AC 5).
        sa.CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)", name="venue_bookings_withdrawn_consistent"
        ),
    )
    # US22 AC 3 and 7: no two live bookings at one venue may overlap, even by one second. '[)'
    # includes the start and excludes the end, so back-to-back is allowed. A concurrent second
    # insert waits for the first to commit and then fails, so the first request wins.
    # DECISION-PENDING: D21 — Requested blocks as well as Approved (LIVE_BOOKING_STATUSES).
    # DECISION-PENDING: D22 — plain start to end; US13 adds the venue's setup and turnaround.
    op.execute(
        "ALTER TABLE venue_bookings ADD CONSTRAINT venue_bookings_no_overlap "
        "EXCLUDE USING gist (venue_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) "
        "WHERE (status IN ('requested', 'approved'))"
    )
    op.execute("ALTER TABLE venue_bookings ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM venue_bookings)")):
        raise RuntimeError("Refusing lossy downgrade: venue bookings would be discarded.")
    op.drop_table("venue_bookings")
    sa.Enum(name="venue_booking_status").drop(bind)
    # btree_gist stays installed: dropping an extension could break other objects that use it.
