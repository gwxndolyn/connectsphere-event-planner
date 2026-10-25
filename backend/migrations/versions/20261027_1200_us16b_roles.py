"""users hold a list of roles; add venue_staff and safety_officer

Revision ID: 20261027_1200_us16b_roles
Revises: 20261026_1200_us10d_history
Create Date: 2026-10-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261027_1200_us16b_roles"
down_revision: Union[str, None] = "20261026_1200_us10d_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The existing values in their current order, then US16b's two. 'operations_manager' stays, unused (D49).
USER_ROLES = (
    "organiser",
    "coordinator",
    "coordinator_lead",
    "operations_manager",
    "attendee",
    "tech_support",
    "venue_staff",
    "safety_officer",
)


def upgrade() -> None:
    # The type is rebuilt rather than given two values with ADD VALUE: a value added that way can't be
    # used until the transaction commits, and the backfill below needs 'venue_staff' (D49).
    values = ", ".join(f"'{value}'" for value in USER_ROLES)
    op.execute(f"CREATE TYPE user_role_us16b AS ENUM ({values})")
    op.execute("ALTER TABLE users ADD COLUMN roles user_role_us16b[]")
    # Each user keeps their one role as a list of one; D19's stand-in becomes the real Venue Staff role.
    op.execute(
        """
        UPDATE users SET roles = ARRAY[
            (CASE role WHEN 'operations_manager' THEN 'venue_staff' ELSE role::text END)::user_role_us16b
        ]
        """
    )
    op.drop_column("users", "role")
    op.execute("DROP TYPE user_role")
    op.execute("ALTER TYPE user_role_us16b RENAME TO user_role")
    op.execute("ALTER TABLE users ALTER COLUMN roles SET NOT NULL, ALTER COLUMN roles SET DEFAULT '{attendee}'")

    # A CHECK can't hold a subquery, so "no role twice" is a function. Immutable, so a CHECK may call it.
    op.execute(
        """
        CREATE FUNCTION array_has_no_repeats(anyarray) RETURNS boolean
        LANGUAGE sql IMMUTABLE SET search_path = ''
        AS $$ SELECT count(*) = count(DISTINCT item) FROM unnest($1) AS item $$
        """
    )
    op.create_check_constraint("users_roles_not_empty", "users", "cardinality(roles) > 0")
    op.create_check_constraint("users_roles_no_repeats", "users", "array_has_no_repeats(roles)")


def downgrade() -> None:
    bind = op.get_bind()
    lossy = bind.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM users WHERE cardinality(roles) <> 1 OR 'safety_officer' = ANY(roles))")
    )
    if lossy:
        raise RuntimeError(
            "Refusing lossy downgrade: a user holds more than one role, or safety_officer, which one role can't keep."
        )
    op.execute("ALTER TABLE users ADD COLUMN role user_role")
    op.execute(
        "UPDATE users SET role = CASE roles[1] WHEN 'venue_staff' THEN 'operations_manager' ELSE roles[1] END"
    )
    op.execute("ALTER TABLE users ALTER COLUMN role SET NOT NULL, ALTER COLUMN role SET DEFAULT 'attendee'")
    op.drop_constraint("users_roles_no_repeats", "users", type_="check")
    op.drop_constraint("users_roles_not_empty", "users", type_="check")
    op.drop_column("users", "roles")
    op.execute("DROP FUNCTION array_has_no_repeats(anyarray)")
    # Postgres can't drop an enum value, so 'venue_staff' and 'safety_officer' stay in user_role, unused.
