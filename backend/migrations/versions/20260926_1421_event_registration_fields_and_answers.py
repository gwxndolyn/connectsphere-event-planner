"""event registration fields and answers

Revision ID: 69572c138625
Revises: dcc645f2c595
Create Date: 2026-09-26 14:21:47.918454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '69572c138625'
down_revision: Union[str, None] = 'dcc645f2c595'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REGISTRATION_FIELD_TYPES = ("text", "email", "select", "number")


def upgrade() -> None:
    op.create_table(
        "event_registration_fields",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("field_type", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            f"field_type in {REGISTRATION_FIELD_TYPES}", name="event_registration_fields_type_valid"
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "field_key"),
    )

    op.create_table(
        "registration_answers",
        sa.Column("registration_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("registration_id", "field_key"),
    )


def downgrade() -> None:
    op.drop_table("registration_answers")
    op.drop_table("event_registration_fields")
