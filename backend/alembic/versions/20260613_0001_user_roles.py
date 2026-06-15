"""user roles for supabase auth

Revision ID: 20260613_0001
Revises: 20260612_0001
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260613_0001"
down_revision: str | None = "20260612_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("supabase_user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255)),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("patient_id", sa.String(length=20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("user_roles", schema="app")
