"""let a Safety Officer request changes to an event's arrangements, with the areas affected

Revision ID: 20261113_1200_us30b_changes
Revises: 20261112_1200_us9_cancellations
Create Date: 2026-11-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261113_1200_us30b_changes"
down_revision: Union[str, None] = "20261112_1200_us9_cancellations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # US30b (SCRUM-100): a review can now ask for changes instead of rejecting. The areas the Safety Officer
    # ticked (AC 1) are kept on the review, and the comments are required as for a rejection.
    op.add_column("safety_reviews", sa.Column("areas", postgresql.JSONB(), nullable=True))
    op.drop_constraint("safety_reviews_outcome_known", "safety_reviews", type_="check")
    op.create_check_constraint(
        "safety_reviews_outcome_known", "safety_reviews", "outcome IN ('approved', 'rejected', 'changes_requested')"
    )
    op.create_check_constraint(
        "safety_reviews_changes_have_comments_and_areas",
        "safety_reviews",
        "outcome <> 'changes_requested' OR (comments IS NOT NULL AND btrim(comments) <> '' "
        "AND areas IS NOT NULL AND jsonb_array_length(areas) > 0)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM safety_reviews WHERE outcome = 'changes_requested')")):
        raise RuntimeError("Refusing lossy downgrade: requests for changes would be discarded.")
    op.drop_constraint("safety_reviews_changes_have_comments_and_areas", "safety_reviews", type_="check")
    op.drop_constraint("safety_reviews_outcome_known", "safety_reviews", type_="check")
    op.create_check_constraint("safety_reviews_outcome_known", "safety_reviews", "outcome IN ('approved', 'rejected')")
    op.drop_column("safety_reviews", "areas")
