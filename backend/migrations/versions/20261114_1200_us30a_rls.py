"""turn on row level security for safety_reviews, which US30a's migration left off

Revision ID: 20261114_1200_us30a_rls
Revises: 20261113_1200_us30b_changes
Create Date: 2026-11-14

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20261114_1200_us30a_rls"
down_revision: Union[str, None] = "20261113_1200_us30b_changes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SCRUM-99 (US30a) created safety_reviews without RLS, the only public table so; every other one has it on, with
    # no policies, so Supabase's anon and authenticated roles can't read or write it (claude_instructions §1a).
    op.execute("ALTER TABLE safety_reviews ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE safety_reviews DISABLE ROW LEVEL SECURITY")
