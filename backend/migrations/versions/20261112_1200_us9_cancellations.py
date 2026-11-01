"""add event cancellations: an organiser's request, the coordinator's decision, or a direct cancel

Revision ID: 20261112_1200_us9_cancellations
Revises: 20261111_1200_us15_sessions
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261112_1200_us9_cancellations"
down_revision: Union[str, None] = "20261111_1200_us15_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUEST_STAGE = "'draft', 'submitted', 'under_review', 'awaiting_clarification', 'approved', 'rejected'"
FINAL_FIELDS = (
    "(name IS NOT NULL AND start_at IS NOT NULL AND end_at IS NOT NULL "
    "AND capacity IS NOT NULL AND delivery_mode IS NOT NULL)"
)


def upgrade() -> None:
    # US9 (SCRUM-12) AC 8: who asked, why and when, and who decided and when. An organiser's request is pending
    # until the assigned coordinator approves or rejects it (AC 1, 2); a coordinator's direct cancel (AC 3) is
    # one row, already approved, with the coordinator as both requester and decider.
    op.create_table(
        "event_cancellations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="cancellation_status"),
            server_default="pending",
            nullable=False,
        ),
        # The service always sets it from the same clock as decided_at; the default is for hand-written rows.
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        # The coordinator's reason for rejecting a request; required then, and only then.
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        # AC 3: the coordinator cancelled it themselves, rather than deciding an organiser's request.
        sa.Column("direct", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name="fk_event_cancellations_event_id_events"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], name="fk_event_cancellations_requested_by_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"], ["users.id"], name="fk_event_cancellations_decided_by_user_id_users"
        ),
        sa.CheckConstraint(
            "btrim(reason) <> '' AND char_length(reason) <= 1000", name="event_cancellations_reason_not_blank"
        ),
        sa.CheckConstraint(
            "(status = 'pending') = (decided_at IS NULL) AND (decided_at IS NULL) = (decided_by_user_id IS NULL) "
            "AND (decided_at IS NULL OR decided_at >= requested_at)",
            name="event_cancellations_decided_consistent",
        ),
        sa.CheckConstraint(
            "(status = 'rejected') = (rejection_reason IS NOT NULL) "
            "AND (rejection_reason IS NULL OR (btrim(rejection_reason) <> '' AND char_length(rejection_reason) <= 1000))",
            name="event_cancellations_rejection_reason_only_when_rejected",
        ),
        # A direct cancel is approved at once, by whoever asked; a decided organiser request had another decider (D51).
        sa.CheckConstraint(
            "(NOT direct OR status = 'approved') "
            "AND (decided_by_user_id IS NULL OR direct = (decided_by_user_id = requested_by_user_id))",
            name="event_cancellations_direct_consistent",
        ),
    )
    op.create_index("ix_event_cancellations_event_id", "event_cancellations", ["event_id"])
    # At most one open row per event: a pending request or, once cancelled (AC 4: it can't be undone), the approved
    # one. So no second request while one waits, none after a cancel, and a cancel must decide the pending request.
    op.create_index(
        "event_cancellations_one_open",
        "event_cancellations",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'approved')"),
    )
    op.execute("ALTER TABLE event_cancellations ENABLE ROW LEVEL SECURITY")

    # DECISION-PENDING: D98 — an Approved event can be cancelled (AC 1) but may have no date or capacity yet
    # (US18 takes them from its bookings), so a cancelled event needs only its name (AC 6's notices name it).
    op.drop_constraint("events_final_fields_required", "events", type_="check")
    op.create_check_constraint(
        "events_final_fields_required",
        "events",
        f"status::text IN ({REQUEST_STAGE}) OR (status::text = 'cancelled' AND name IS NOT NULL) OR {FINAL_FIELDS}",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM event_cancellations)")):
        raise RuntimeError("Refusing lossy downgrade: event cancellation records would be discarded.")
    if bind.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM events WHERE status = 'cancelled' AND NOT {FINAL_FIELDS})")):
        raise RuntimeError("Refusing downgrade: a cancelled event has no date or capacity of its own.")
    op.drop_constraint("events_final_fields_required", "events", type_="check")
    op.create_check_constraint(
        "events_final_fields_required",
        "events",
        f"status::text IN ({REQUEST_STAGE}) OR {FINAL_FIELDS}",
    )
    op.drop_index("event_cancellations_one_open", table_name="event_cancellations")
    op.drop_index("ix_event_cancellations_event_id", table_name="event_cancellations")
    op.drop_table("event_cancellations")
    op.execute("DROP TYPE cancellation_status")
