"""foundations and storage schemas

Revision ID: 20260612_0001
Revises:
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260612_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS vault")
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    op.execute("CREATE SCHEMA IF NOT EXISTS billing")

    op.create_table(
        "patient_vault",
        sa.Column("patient_id", sa.String(length=20), primary_key=True),
        sa.Column("token", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name_encrypted", postgresql.BYTEA()),
        sa.Column("dob_encrypted", postgresql.BYTEA()),
        sa.Column("address_encrypted", postgresql.BYTEA()),
        sa.Column("phone_encrypted", postgresql.BYTEA()),
        sa.Column("email_encrypted", postgresql.BYTEA()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("access_log", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        schema="vault",
    )

    op.create_table(
        "treatment_plans",
        sa.Column("plan_id", sa.String(length=20), primary_key=True),
        sa.Column("patient_id", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=200)),
        sa.Column("plan_start", sa.Date(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("buffer_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("extension_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("hard_stop", sa.Date(), nullable=False),
        sa.Column("next_visit", sa.Date()),
        sa.Column("status", sa.String(length=20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="app",
    )

    op.create_table(
        "diagnoses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.String(length=20), sa.ForeignKey("app.treatment_plans.plan_id")),
        sa.Column("code", sa.String(length=20)),
        sa.Column("description", sa.Text()),
        sa.Column("code_system", sa.String(length=20)),
        schema="app",
    )

    op.create_table(
        "orbs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("billing_codes", postgresql.ARRAY(sa.String(length=20))),
        schema="app",
    )

    op.create_table(
        "patient_orbs",
        sa.Column("orb_ref", sa.String(length=30), primary_key=True),
        sa.Column("plan_id", sa.String(length=20), sa.ForeignKey("app.treatment_plans.plan_id")),
        sa.Column("patient_id", sa.String(length=20), nullable=False),
        sa.Column("orb_number", sa.Integer(), nullable=False),
        sa.Column("catalog_orb_id", sa.Integer(), sa.ForeignKey("app.orbs.id")),
        sa.Column("status", sa.String(length=20), server_default="pending"),
        sa.Column("target_date", sa.Date()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("plan_id", "orb_number", name="uq_patient_orbs_plan_number"),
        schema="app",
    )

    op.create_table(
        "alert_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.String(length=20)),
        sa.Column("recipient", sa.String(length=20)),
        sa.Column("checkpoint", sa.String(length=20)),
        sa.Column("message", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="app",
    )

    op.create_table(
        "billing_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("code_system", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2)),
        sa.Column("medicare_rate", sa.Numeric(10, 2)),
        sa.Column("is_billable", sa.Boolean(), server_default=sa.true()),
        sa.Column("requires_auth", sa.Boolean(), server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="billing",
    )

    op.create_table(
        "quotation_log",
        sa.Column("quote_id", sa.String(length=20), primary_key=True),
        sa.Column("plan_id", sa.String(length=20)),
        sa.Column("total", sa.Numeric(10, 2)),
        sa.Column("sent_to", sa.String(length=200)),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB()),
        schema="billing",
    )


def downgrade() -> None:
    op.drop_table("quotation_log", schema="billing")
    op.drop_table("billing_codes", schema="billing")
    op.drop_table("alert_log", schema="app")
    op.drop_table("patient_orbs", schema="app")
    op.drop_table("orbs", schema="app")
    op.drop_table("diagnoses", schema="app")
    op.drop_table("treatment_plans", schema="app")
    op.drop_table("patient_vault", schema="vault")
    op.execute("DROP SCHEMA IF EXISTS billing")
    op.execute("DROP SCHEMA IF EXISTS app")
    op.execute("DROP SCHEMA IF EXISTS vault")
