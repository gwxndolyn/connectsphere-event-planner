"""link users to their Supabase Auth account

Revision ID: 20261015_1200_us16a_auth_link
Revises: 20261013_1200_us20_venues
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261015_1200_us16a_auth_link"
down_revision: Union[str, None] = "20261013_1200_us20_venues"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The Supabase user id (the token's `sub`). Null until the person first logs in or signs up, so
    # seeded users keep working. On users (§9): every attendee has a users row with the same id, so
    # one link covers every role.
    op.add_column("users", sa.Column("auth_user_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint("users_auth_user_id_key", "users", ["auth_user_id"])
    # Sign-up asks for a name (US16a AC 6); seeded users have none.
    op.add_column("users", sa.Column("full_name", sa.Text(), nullable=True))
    # users already has row level security on (migration 5733a3c705f7); new columns inherit it.


def downgrade() -> None:
    bind = op.get_bind()
    account_data_exists = bind.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM users WHERE auth_user_id IS NOT NULL OR full_name IS NOT NULL)")
    )
    if account_data_exists:
        raise RuntimeError("Refusing lossy downgrade: linked Supabase accounts or users' names would be discarded.")

    op.drop_column("users", "full_name")
    op.drop_constraint("users_auth_user_id_key", "users", type_="unique")
    op.drop_column("users", "auth_user_id")
