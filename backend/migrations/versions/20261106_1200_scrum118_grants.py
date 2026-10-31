"""close the app's version table, booking-reference function and sequences to Supabase's API roles

Revision ID: 20261106_1200_scrum118_grants
Revises: 20261105_1200_us24_bookings_api
Create Date: 2026-11-06

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20261106_1200_scrum118_grants"
down_revision: Union[str, None] = "20261105_1200_us24_bookings_api"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEQUENCES = "attendance_log_id_seq, event_request_reference_seq, venue_booking_reference_seq"

# SCRUM-118: a second layer behind Supabase's Data API being off (25 Oct, SCRUM-117), so turning it back
# on, or a new Supabase project, doesn't reopen these. Alembic and the backend connect as the owner,
# which bypasses RLS and keeps every privilege. anon and authenticated exist only on Supabase, so
# they're revoked only where they exist; local Docker and CI have neither.
HARDEN = f"""
DO $$
BEGIN
    -- The one table without RLS: anon could read, change or truncate it and break the next migration.
    ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY;
    -- US13's function burns booking references when called; it also needs a fixed search_path.
    ALTER FUNCTION next_venue_booking_reference() SET search_path = public;
    REVOKE EXECUTE ON FUNCTION next_venue_booking_reference() FROM PUBLIC;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE EXECUTE ON FUNCTION next_venue_booking_reference() FROM anon;
        REVOKE USAGE, SELECT ON SEQUENCE {SEQUENCES} FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE EXECUTE ON FUNCTION next_venue_booking_reference() FROM authenticated;
        REVOKE USAGE, SELECT ON SEQUENCE {SEQUENCES} FROM authenticated;
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(HARDEN)


def downgrade() -> None:
    # Back to Postgres's own defaults. anon and authenticated aren't granted anything again: their old
    # grants came from Supabase's defaults, and giving them back would reopen what this closed.
    op.execute("GRANT EXECUTE ON FUNCTION next_venue_booking_reference() TO PUBLIC")
    op.execute("ALTER FUNCTION next_venue_booking_reference() RESET search_path")
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
