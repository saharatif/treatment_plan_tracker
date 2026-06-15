"""SQLAlchemy ORM models for the orbs, app, billing, and vault schemas.

These map directly to the tables created by the Alembic migrations under
backend/alembic/versions/. Most query logic in app/services uses raw SQL via
`text()`; these classes are primarily used for inserts/upserts (e.g. seeding,
billing quote storage).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PatientVault(Base):
    """Encrypted PII storage, keyed by patient_id. Fields are pgp_sym_encrypt'd
    BYTEA blobs (see app/services/vault.py) - never store plaintext PII here."""

    __tablename__ = "patient_vault"
    __table_args__ = {"schema": "vault"}

    patient_id: Mapped[str] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True, nullable=False)
    name_encrypted: Mapped[bytes | None] = mapped_column(BYTEA)
    dob_encrypted: Mapped[bytes | None] = mapped_column(BYTEA)
    address_encrypted: Mapped[bytes | None] = mapped_column(BYTEA)
    phone_encrypted: Mapped[bytes | None] = mapped_column(BYTEA)
    email_encrypted: Mapped[bytes | None] = mapped_column(BYTEA)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    access_log: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")


class TreatmentPlan(Base):
    """A patient's 10-Orbs plan. target_date/hard_stop define the checkpoint
    schedule evaluated by app/services/checkpoints.py."""

    __tablename__ = "treatment_plans"
    __table_args__ = {"schema": "app"}

    plan_id: Mapped[str] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(nullable=False)
    provider: Mapped[str | None]
    plan_start: Mapped[date] = mapped_column(Date, nullable=False)
    duration_days: Mapped[int] = mapped_column(default=14, nullable=False)
    buffer_days: Mapped[int] = mapped_column(default=3, nullable=False)
    extension_days: Mapped[int] = mapped_column(default=7, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    hard_stop: Mapped[date] = mapped_column(Date, nullable=False)
    next_visit: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Diagnosis(Base):
    __tablename__ = "diagnoses"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("app.treatment_plans.plan_id"))
    code: Mapped[str | None]
    description: Mapped[str | None] = mapped_column(Text)
    code_system: Mapped[str | None]


class Orb(Base):
    """Catalog of reusable orb templates (e.g. LAB-01, MED-02), seeded from
    app/seed_data.py:ORB_CATALOG. Patient-specific instances live in PatientOrb."""

    __tablename__ = "orbs"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_code: Mapped[str] = mapped_column(unique=True, nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    billing_codes: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class PatientOrb(Base):
    """One of the 10 orbs assigned to a patient's plan. orb_ref is the
    human-readable primary key (see app/ids.py:generate_orb_ref)."""

    __tablename__ = "patient_orbs"
    __table_args__ = (
        UniqueConstraint("plan_id", "orb_number", name="uq_patient_orbs_plan_number"),
        {"schema": "app"},
    )

    orb_ref: Mapped[str] = mapped_column(primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("app.treatment_plans.plan_id"))
    patient_id: Mapped[str] = mapped_column(nullable=False)
    orb_number: Mapped[int] = mapped_column(nullable=False)
    catalog_orb_id: Mapped[int | None] = mapped_column(ForeignKey("app.orbs.id"))
    status: Mapped[str] = mapped_column(default="pending", nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertLog(Base):
    """Audit trail of patient/clinic notifications sent by checkpoint evaluation."""

    __tablename__ = "alert_log"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str | None]
    recipient: Mapped[str | None]
    checkpoint: Mapped[str | None]
    message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingCode(Base):
    """Reference table of ICD-10/CPT/HCPCS codes with pricing, seeded from
    app/seed_data.py. is_billable distinguishes diagnosis codes (False) from
    procedure/service codes (True) used in quotations."""

    __tablename__ = "billing_codes"
    __table_args__ = {"schema": "billing"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    code_system: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    medicare_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuotationLog(Base):
    """Record of every billing quote generated for a plan (see
    app/services/billing.py:build_quotation), including the full plan
    snapshot used by confirm-billing to enroll orbs."""

    __tablename__ = "quotation_log"
    __table_args__ = {"schema": "billing"}

    quote_id: Mapped[str] = mapped_column(primary_key=True)
    plan_id: Mapped[str | None]
    total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sent_to: Mapped[str | None]
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
