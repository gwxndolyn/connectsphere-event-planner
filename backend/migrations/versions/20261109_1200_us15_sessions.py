"""add event sessions, an event's agenda on one track

Revision ID: 20261109_1200_us15_sessions
Revises: 20261107_1200_us14_tech_staff
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261109_1200_us15_sessions"
down_revision: Union[str, None] = "20261107_1200_us14_tech_staff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US15 (SCRUM-18) AC 2: the AC's session types, plus `other` (decided by the acting PO, 1 Nov).
    session_type = postgresql.ENUM(
        "presentation", "workshop", "panel", "break", "other", name="event_session_type"
    )
    session_type.create(op.get_bind())
    op.create_table(
        "event_sessions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("session_type", postgresql.ENUM(name="event_session_type", create_type=False), nullable=False),
        sa.Column("speaker_name", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("btrim(title) <> ''", name="event_sessions_title_not_blank"),
        sa.CheckConstraint("ends_at > starts_at", name="event_sessions_window_valid"),
        # A break has no speaker; every other session names one (decided by the acting PO, 1 Nov).
        sa.CheckConstraint(
            "session_type = 'break' OR btrim(coalesce(speaker_name, '')) <> ''",
            name="event_sessions_speaker_required",
        ),
    )
    # AC 4 (decided by the acting PO, 1 Nov): each event is one track, so no two of its sessions
    # overlap. '[)' allows back-to-back. A concurrent second insert waits for the first to commit and
    # then fails, so SCRUM-139's race (TC-US15-12) has one winner. Its GiST index also serves lookups by
    # event. btree_gist is already installed (US22).
    op.execute(
        "ALTER TABLE event_sessions ADD CONSTRAINT event_sessions_no_overlap "
        "EXCLUDE USING gist (event_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&)"
    )
    op.execute("ALTER TABLE event_sessions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM event_sessions)")):
        raise RuntimeError("Refusing lossy downgrade: event agendas would be discarded.")
    op.drop_table("event_sessions")
    sa.Enum(name="event_session_type").drop(bind)
