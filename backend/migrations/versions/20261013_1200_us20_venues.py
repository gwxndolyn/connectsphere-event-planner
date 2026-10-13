"""add venue catalogue

Revision ID: 20261013_1200_us20_venues
Revises: 20261008_1200_us8_clarifications
Create Date: 2026-10-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261013_1200_us20_venues"
down_revision: Union[str, None] = "20261008_1200_us8_clarifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Kept in step with FACILITIES, ACCESSIBILITY_FEATURES and ROOM_LAYOUTS in app/venue/models.py (D18).
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
    op.create_table(
        "venues",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        _tags("facilities"),
        _tags("accessibility_features"),
        _tags("room_layouts"),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column("setup_minutes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("turnaround_minutes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # US20 AC 4: invalid data can't be saved. Named so the API can say which field (PR 2).
        sa.CheckConstraint("btrim(name) <> ''", name="venues_name_not_blank"),
        sa.CheckConstraint("btrim(location) <> ''", name="venues_location_not_blank"),
        sa.CheckConstraint("capacity > 0", name="venues_capacity_positive"),
        sa.CheckConstraint("closes_at > opens_at", name="venues_hours_valid"),
        # A setup or turnaround of 0 is valid.
        sa.CheckConstraint("setup_minutes >= 0", name="venues_setup_minutes_non_negative"),
        sa.CheckConstraint("turnaround_minutes >= 0", name="venues_turnaround_minutes_non_negative"),
        # Tags come from fixed lists (D18); an empty list is allowed.
        sa.CheckConstraint(f"facilities <@ {_array(FACILITIES)}", name="venues_facilities_known"),
        sa.CheckConstraint(
            f"accessibility_features <@ {_array(ACCESSIBILITY_FEATURES)}",
            name="venues_accessibility_features_known",
        ),
        sa.CheckConstraint(f"room_layouts <@ {_array(ROOM_LAYOUTS)}", name="venues_room_layouts_known"),
    )
    op.execute("ALTER TABLE venues ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM venues)")):
        raise RuntimeError("Refusing lossy downgrade: venues would be discarded.")
    op.drop_table("venues")
