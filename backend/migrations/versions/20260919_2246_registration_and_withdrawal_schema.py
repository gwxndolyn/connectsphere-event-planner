"""registration and withdrawal schema

Revision ID: dcc645f2c595
Revises: 7c7df258ccf2
Create Date: 2026-09-19 22:46:34.762661

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'dcc645f2c595'
down_revision: Union[str, None] = '7c7df258ccf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EVENT_STATUSES = ("draft", "submitted", "confirmed", "cancelled")
DELIVERY_MODES = ("in_person", "online")
REGISTRATION_STATUSES = ("confirmed", "waitlisted", "offered", "withdrawn", "declined", "expired")


def upgrade() -> None:
    # Replace the Sprint 0 placeholder events table (int id, title) with the spec §2 schema.
    # It holds no data, and an int primary key can't be converted to uuid in place.
    op.drop_table("events")

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum(*EVENT_STATUSES, name="event_status"), server_default="draft", nullable=False),
        sa.Column("registration_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("registration_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("delivery_mode", sa.Enum(*DELIVERY_MODES, name="delivery_mode"), nullable=False),
        sa.Column("venue_name", sa.Text(), nullable=True),
        sa.Column("room_number", sa.Text(), nullable=True),
        sa.Column("join_link", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("capacity >= 0", name="events_capacity_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "attendees",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "registrations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("attendee_id", sa.Uuid(), nullable=True),
        sa.Column("attendee_email", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum(*REGISTRATION_STATUSES, name="registration_status"), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waitlist_joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attendee_id"], ["attendees.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # "Cannot register twice for the same event" — enforced in the DB, not only in app code.
    op.create_index(
        "registrations_one_active_per_attendee",
        "registrations",
        ["event_id", "attendee_id"],
        unique=True,
        postgresql_where=sa.text("status in ('confirmed', 'waitlisted', 'offered')"),
    )

    op.create_table(
        "attendance_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("registration_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("attendee_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("attendance_log")
    op.drop_index("registrations_one_active_per_attendee", table_name="registrations")
    op.drop_table("registrations")
    op.drop_table("attendees")
    op.drop_table("events")
    sa.Enum(name="registration_status").drop(op.get_bind())
    sa.Enum(name="delivery_mode").drop(op.get_bind())
    sa.Enum(name="event_status").drop(op.get_bind())

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
