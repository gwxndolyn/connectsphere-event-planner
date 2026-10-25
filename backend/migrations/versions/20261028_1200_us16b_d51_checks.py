"""no one decides a venue booking or equipment line they requested

Revision ID: 20261028_1200_us16b_d51_checks
Revises: 20261027_1200_us16b_roles
Create Date: 2026-10-28

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20261028_1200_us16b_d51_checks"
down_revision: Union[str, None] = "20261027_1200_us16b_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # D51: whoever decides a record didn't request it. A pending row has no decider, and NULL passes.
    # The event's-current-coordinator half of D51 spans tables, so the services check it.
    op.create_check_constraint(
        "venue_bookings_decider_not_requester", "venue_bookings", "decided_by_user_id <> requested_by_user_id"
    )
    op.create_check_constraint(
        "equipment_request_lines_reviewer_not_requester",
        "equipment_request_lines",
        "reviewed_by_user_id <> requested_by_user_id",
    )


def downgrade() -> None:
    op.drop_constraint("equipment_request_lines_reviewer_not_requester", "equipment_request_lines", type_="check")
    op.drop_constraint("venue_bookings_decider_not_requester", "venue_bookings", type_="check")
