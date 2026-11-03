"""keep the notices the system raises, one row per recipient, so each user can read their own

Revision ID: 20261116_1200_us31_notifications
Revises: 20261116_1200_us23a_blocks
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261116_1200_us31_notifications"
down_revision: Union[str, None] = "20261116_1200_us23a_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US31 (SCRUM-107): until now a notice was only logged. Each one is also a row for the person it was
    # sent to (AC 2, 6): `read_at` is null until they read it (AC 3, 4). `user_id` and `event_id` are not
    # foreign keys: a notice is written from its own session while the caller may still hold a lock on the
    # event (a waitlist offer goes out inside the withdrawal), and a foreign key insert would wait for it.
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("event_name", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "btrim(kind) <> '' AND btrim(message) <> ''", name="notifications_kind_and_message_not_blank"
        ),
    )
    # Every public table has row level security on, with no policies, so Supabase's anon and authenticated roles
    # can't read it (claude_instructions §1a). The API reads it as the app's own database role.
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.create_index(
        "ix_notifications_user_id_created_at", "notifications", ["user_id", sa.text("created_at DESC")]
    )
    op.create_index(
        "ix_notifications_unread", "notifications", ["user_id"], postgresql_where=sa.text("read_at IS NULL")
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM notifications)")):
        raise RuntimeError("Refusing lossy downgrade: notifications would be discarded.")
    op.drop_index("ix_notifications_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_table("notifications")
