"""record a change request's decision, say what each history entry is, and flag arrangements for review

Revision ID: 20261114_1200_us29b_decisions
Revises: 20261114_1200_us30a_rls
Create Date: 2026-11-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261114_1200_us29b_decisions"
down_revision: Union[str, None] = "20261114_1200_us30a_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AUDIT_ACTIONS = (
    "saved",  # a save that changed the event (US12 AC 2)
    "requested",  # a critical save held in a change request (US12 AC 3, D89)
    "applied",  # a field an approved change request changed (US29b AC 2)
    "decided",  # the approval or rejection itself (US29b AC 5)
    "status_changed",  # a significant change moved the event back to Planning (D103)
    "confirmation_cleared",  # ...and so it is no longer confirmed (D103)
    "safety_approval_cleared",  # ...and needs a new safety review (US29b AC 6, D104)
)


def upgrade() -> None:
    # US29b (SCRUM-98) AC 2, 5: who decided, when, and a rejection's reason. Compared as text, as US17's
    # CHECKs on events are, so they don't depend on the enum's state in the migration's transaction.
    op.add_column("event_change_requests", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "event_change_requests",
        sa.Column("decided_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("event_change_requests", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "event_change_requests_decision_consistent",
        "event_change_requests",
        "(status::text = 'pending_approval') = (decided_at IS NULL)"
        " AND (decided_at IS NULL) = (decided_by_user_id IS NULL)",
    )
    op.create_check_constraint(
        "event_change_requests_rejection_reason_only_when_rejected",
        "event_change_requests",
        "(status::text = 'rejected') = (rejection_reason IS NOT NULL)",
    )
    op.create_check_constraint(
        "event_change_requests_rejection_reason_not_blank",
        "event_change_requests",
        "rejection_reason IS NULL OR btrim(rejection_reason) <> ''",
    )
    # D51: no one decides a request they made. A coordinator's own US12 edit goes to a Lead (D100).
    op.create_check_constraint(
        "event_change_requests_decider_not_requester",
        "event_change_requests",
        "decided_by_user_id IS NULL OR decided_by_user_id <> requested_by_user_id",
    )
    # The coordinator's list of pending requests (AC 1).
    op.create_index(
        "ix_event_change_requests_pending",
        "event_change_requests",
        ["event_id"],
        postgresql_where=sa.text("status = 'pending_approval'"),
    )

    # AC 5: History tells a held request from the change it later applied. Existing entries tied to a
    # change request are critical saves still waiting (D89), so they're 'requested'.
    op.add_column(
        "event_audit_entries",
        sa.Column("action", sa.Text(), server_default=sa.text("'saved'"), nullable=False),
    )
    op.execute("UPDATE event_audit_entries SET action = 'requested' WHERE change_request_id IS NOT NULL")
    known = ", ".join(f"'{action}'" for action in AUDIT_ACTIONS)
    op.create_check_constraint("event_audit_entries_action_known", "event_audit_entries", f"action IN ({known})")

    # AC 3 (D102): an approved significant change flags each affected arrangement for the coordinator to
    # review, and changes nothing on it. An equipment flag points at the line, not its reservation,
    # because releasing a reservation deletes it (D74).
    op.create_table(
        "event_review_flags",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("change_request_id", sa.Uuid(), sa.ForeignKey("event_change_requests.id"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("venue_booking_id", sa.Uuid(), sa.ForeignKey("venue_bookings.id"), nullable=True),
        sa.Column("equipment_request_line_id", sa.Uuid(), sa.ForeignKey("equipment_request_lines.id"), nullable=True),
        sa.Column("fields", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("raised_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cleared_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN ('venue_booking', 'equipment_reservation', 'registrations')",
            name="event_review_flags_kind_known",
        ),
        sa.CheckConstraint(
            "(venue_booking_id IS NOT NULL) = (kind = 'venue_booking')"
            " AND (equipment_request_line_id IS NOT NULL) = (kind = 'equipment_reservation')",
            name="event_review_flags_target_matches_kind",
        ),
        sa.CheckConstraint("cardinality(fields) > 0", name="event_review_flags_fields_not_empty"),
        sa.CheckConstraint(
            "(cleared_at IS NULL) = (cleared_by_user_id IS NULL)", name="event_review_flags_clearance_consistent"
        ),
        sa.CheckConstraint(
            "cleared_note IS NULL OR (cleared_at IS NOT NULL AND btrim(cleared_note) <> '')",
            name="event_review_flags_note_only_when_cleared",
        ),
    )
    op.create_index("ix_event_review_flags_event_id", "event_review_flags", ["event_id"])
    # One open flag per item: a later change adds its fields to the open one (D102).
    op.create_index(
        "event_review_flags_one_open_per_booking",
        "event_review_flags",
        ["venue_booking_id"],
        unique=True,
        postgresql_where=sa.text("cleared_at IS NULL AND venue_booking_id IS NOT NULL"),
    )
    op.create_index(
        "event_review_flags_one_open_per_line",
        "event_review_flags",
        ["equipment_request_line_id"],
        unique=True,
        postgresql_where=sa.text("cleared_at IS NULL AND equipment_request_line_id IS NOT NULL"),
    )
    op.create_index(
        "event_review_flags_one_open_registrations",
        "event_review_flags",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("cleared_at IS NULL AND kind = 'registrations'"),
    )
    op.execute("ALTER TABLE event_review_flags ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM event_review_flags)")):
        raise RuntimeError("Refusing lossy downgrade: review flags would be discarded.")
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM event_change_requests WHERE status <> 'pending_approval')")):
        raise RuntimeError("Refusing lossy downgrade: change request decisions would be discarded.")
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM event_audit_entries WHERE action NOT IN ('saved', 'requested'))")):
        raise RuntimeError("Refusing lossy downgrade: history of decided changes would be discarded.")
    op.drop_table("event_review_flags")
    op.drop_constraint("event_audit_entries_action_known", "event_audit_entries", type_="check")
    op.drop_column("event_audit_entries", "action")
    op.drop_index("ix_event_change_requests_pending", table_name="event_change_requests")
    for name in (
        "event_change_requests_decider_not_requester",
        "event_change_requests_rejection_reason_not_blank",
        "event_change_requests_rejection_reason_only_when_rejected",
        "event_change_requests_decision_consistent",
    ):
        op.drop_constraint(name, "event_change_requests", type_="check")
    op.drop_column("event_change_requests", "rejection_reason")
    op.drop_column("event_change_requests", "decided_by_user_id")
    op.drop_column("event_change_requests", "decided_at")
