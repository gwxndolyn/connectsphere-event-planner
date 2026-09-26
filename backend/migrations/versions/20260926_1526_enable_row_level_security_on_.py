"""enable row level security on application tables

Revision ID: 5733a3c705f7
Revises: 69572c138625
Create Date: 2026-09-26 15:26:45.028314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5733a3c705f7'
down_revision: Union[str, None] = '69572c138625'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every table Sprint 1 owns. Deliberately no policies: with RLS on and nothing granted,
# Supabase's anon and authenticated roles can read nothing, which is what we want while
# the API is the only legitimate way in. The backend connects as the tables' owner, and an
# owner bypasses RLS, so nothing in the app changes.
TABLES = (
    "events",
    "attendees",
    "registrations",
    "attendance_log",
    "event_registration_fields",
    "registration_answers",
)


def upgrade() -> None:
    """Close the gap left by Supabase's Data API.

    The Data API is switched off in Project Settings today, and that toggle is the only
    thing standing between the project's public key and every row in these tables. Turning
    RLS on means flipping that switch back can't quietly expose attendees' registrations.
    Policies come later, with Supabase Auth (§9), when the browser needs its own access.
    """
    for table in TABLES:
        op.execute(f"alter table {table} enable row level security")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"alter table {table} disable row level security")
