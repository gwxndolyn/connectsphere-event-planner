"""add event-request groundwork

Revision ID: 20260930_1200_us1_request_schema
Revises: 5733a3c705f7
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260930_1200_us1_request_schema"
down_revision: Union[str, None] = "5733a3c705f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_EVENT_STATUSES = ("draft", "submitted", "confirmed", "cancelled")
REQUEST_STATUSES = (
    "draft",
    "submitted",
    "under_review",
    "awaiting_clarification",
    "approved",
    "rejected",
)
NEW_EVENT_STATUSES = (
    "under_review",
    "awaiting_clarification",
    "approved",
    "rejected",
    "planning",
    "completed",
)
REQUEST_COLUMNS = (
    "event_category",
    "purpose",
    "preferred_dates",
    "preferred_start_time",
    "preferred_end_time",
    "expected_attendees",
    "room_layout_preference",
    "accessibility_needs",
    "equipment_needs",
    "registration_required",
    "created_by_user_id",
    "submitted_by_user_id",
    "submitted_at",
    "request_reference",
)


def upgrade() -> None:
    # Add values around the existing labels so enum ordering follows the request lifecycle.
    op.execute("ALTER TYPE event_status ADD VALUE 'under_review' AFTER 'submitted'")
    op.execute("ALTER TYPE event_status ADD VALUE 'awaiting_clarification' AFTER 'under_review'")
    op.execute("ALTER TYPE event_status ADD VALUE 'approved' AFTER 'awaiting_clarification'")
    op.execute("ALTER TYPE event_status ADD VALUE 'rejected' AFTER 'approved'")
    op.execute("ALTER TYPE event_status ADD VALUE 'planning' BEFORE 'confirmed'")
    op.execute("ALTER TYPE event_status ADD VALUE 'completed' AFTER 'cancelled'")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "organiser",
                "coordinator",
                "operations_manager",
                "attendee",
                name="user_role",
            ),
            server_default="attendee",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.execute(
        """
        INSERT INTO users (id, email, role, is_active, created_at)
        SELECT id, email, 'attendee', true, created_at FROM attendees
        """
    )
    op.alter_column("attendees", "id", server_default=None)
    op.create_foreign_key("fk_attendees_id_users", "attendees", "users", ["id"], ["id"])

    op.alter_column("events", "name", existing_type=sa.Text(), nullable=True)
    op.alter_column("events", "start_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("events", "end_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("events", "capacity", existing_type=sa.Integer(), nullable=True)
    op.alter_column("events", "delivery_mode", existing_type=sa.Enum(name="delivery_mode"), nullable=True)

    op.add_column("events", sa.Column("waitlist_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("events", sa.Column("event_category", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("purpose", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("preferred_dates", postgresql.ARRAY(sa.Date()), nullable=True))
    op.add_column("events", sa.Column("preferred_start_time", sa.Time(timezone=False), nullable=True))
    op.add_column("events", sa.Column("preferred_end_time", sa.Time(timezone=False), nullable=True))
    op.add_column("events", sa.Column("expected_attendees", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("room_layout_preference", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("accessibility_needs", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("equipment_needs", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("registration_required", sa.Boolean(), nullable=True))
    op.add_column("events", sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("events", sa.Column("submitted_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("events", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("events", sa.Column("request_reference", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_events_created_by_user_id_users", "events", "users", ["created_by_user_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_events_submitted_by_user_id_users", "events", "users", ["submitted_by_user_id"], ["id"]
    )
    op.execute("CREATE SEQUENCE event_request_reference_seq")
    op.create_unique_constraint("events_request_reference_key", "events", ["request_reference"])
    op.create_check_constraint(
        "events_expected_attendees_positive",
        "events",
        "expected_attendees IS NULL OR expected_attendees >= 1",
    )
    op.create_check_constraint(
        "events_final_fields_required",
        "events",
        "status::text IN ('draft', 'submitted', 'under_review', 'awaiting_clarification', 'approved', 'rejected') "
        "OR (name IS NOT NULL AND start_at IS NOT NULL AND end_at IS NOT NULL "
        "AND capacity IS NOT NULL AND delivery_mode IS NOT NULL)",
    )

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    request_data_exists = bind.scalar(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM events
                WHERE status::text NOT IN ('draft', 'submitted', 'confirmed', 'cancelled')
                   OR event_category IS NOT NULL
                   OR purpose IS NOT NULL
                   OR preferred_dates IS NOT NULL
                   OR preferred_start_time IS NOT NULL
                   OR preferred_end_time IS NOT NULL
                   OR expected_attendees IS NOT NULL
                   OR room_layout_preference IS NOT NULL
                   OR accessibility_needs IS NOT NULL
                   OR equipment_needs IS NOT NULL
                   OR registration_required IS NOT NULL
                   OR created_by_user_id IS NOT NULL
                   OR submitted_by_user_id IS NOT NULL
                   OR submitted_at IS NOT NULL
                   OR request_reference IS NOT NULL
                   OR waitlist_enabled
            )
            """
        )
    )
    non_mirrored_users_exist = bind.scalar(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM users AS u
                LEFT JOIN attendees AS a ON a.id = u.id
                WHERE a.id IS NULL OR a.email <> u.email OR u.role <> 'attendee' OR NOT u.is_active
            )
            """
        )
    )
    sequence_used = bind.scalar(sa.text("SELECT is_called FROM event_request_reference_seq"))
    if request_data_exists or non_mirrored_users_exist or sequence_used:
        raise RuntimeError(
            "Refusing lossy downgrade: event-request data/statuses, a used reference sequence, "
            "or non-mirrored user data would be discarded."
        )

    op.drop_constraint("events_final_fields_required", "events", type_="check")
    op.drop_constraint("events_expected_attendees_positive", "events", type_="check")
    op.drop_constraint("events_request_reference_key", "events", type_="unique")
    op.execute("DROP SEQUENCE event_request_reference_seq")
    op.drop_constraint("fk_events_submitted_by_user_id_users", "events", type_="foreignkey")
    op.drop_constraint("fk_events_created_by_user_id_users", "events", type_="foreignkey")
    for column_name in reversed(REQUEST_COLUMNS):
        op.drop_column("events", column_name)
    op.drop_column("events", "waitlist_enabled")

    op.drop_constraint("fk_attendees_id_users", "attendees", type_="foreignkey")
    op.alter_column(
        "attendees", "id", existing_type=sa.Uuid(), server_default=sa.text("gen_random_uuid()")
    )
    op.drop_table("users")
    sa.Enum(name="user_role").drop(bind)

    op.execute("ALTER TABLE events ALTER COLUMN status DROP DEFAULT")
    op.execute("CREATE TYPE event_status_legacy AS ENUM ('draft', 'submitted', 'confirmed', 'cancelled')")
    op.execute(
        "ALTER TABLE events ALTER COLUMN status TYPE event_status_legacy USING status::text::event_status_legacy"
    )
    op.execute("DROP TYPE event_status")
    op.execute("ALTER TYPE event_status_legacy RENAME TO event_status")
    op.execute("ALTER TABLE events ALTER COLUMN status SET DEFAULT 'draft'")

    op.alter_column("events", "name", existing_type=sa.Text(), nullable=False)
    op.alter_column("events", "start_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("events", "end_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("events", "capacity", existing_type=sa.Integer(), nullable=False)
    op.alter_column("events", "delivery_mode", existing_type=sa.Enum(name="delivery_mode"), nullable=False)