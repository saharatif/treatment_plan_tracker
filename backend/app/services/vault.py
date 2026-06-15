"""Encrypted patient PII vault.

PII is encrypted at rest with Postgres's pgp_sym_encrypt/decrypt using
KMS_KEY, and is keyed by patient_id but addressable via an opaque `token`
(app/ids.py:generate_token) that never embeds or derives from PII. Every read
appends an entry to access_log for auditability.
"""

from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.ids import MAX_UNIQUE_ID_ATTEMPTS, generate_token


PII_FIELDS = ("name", "dob", "address", "phone", "email")


def require_kms_key() -> str:
    if not settings.kms_key:
        raise RuntimeError("KMS_KEY is required for vault encryption")
    return settings.kms_key


async def _token_exists(session: AsyncSession, token: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM vault.patient_vault WHERE token = :token"),
        {"token": token},
    )
    return result.first() is not None


async def generate_unique_token(session: AsyncSession) -> str:
    # generate_token() is random hex, so collisions are vanishingly unlikely but still
    # checked and retried for safety.
    for _ in range(MAX_UNIQUE_ID_ATTEMPTS):
        candidate = generate_token()
        if not await _token_exists(session, candidate):
            return candidate
    raise RuntimeError("Could not generate a unique patient token")


async def upsert_patient_vault(session: AsyncSession, patient_id: str, pii: dict[str, Any]) -> str:
    kms_key = require_kms_key()
    token = await generate_unique_token(session)
    result = await session.execute(
        text(
            """
            INSERT INTO vault.patient_vault (
                patient_id, token, name_encrypted, dob_encrypted,
                address_encrypted, phone_encrypted, email_encrypted
            )
            VALUES (
                :patient_id, :token,
                pgp_sym_encrypt(:name, :kms_key),
                pgp_sym_encrypt(:dob, :kms_key),
                pgp_sym_encrypt(:address, :kms_key),
                pgp_sym_encrypt(:phone, :kms_key),
                pgp_sym_encrypt(:email, :kms_key)
            )
            ON CONFLICT (patient_id) DO UPDATE SET
                name_encrypted = EXCLUDED.name_encrypted,
                dob_encrypted = EXCLUDED.dob_encrypted,
                address_encrypted = EXCLUDED.address_encrypted,
                phone_encrypted = EXCLUDED.phone_encrypted,
                email_encrypted = EXCLUDED.email_encrypted
            RETURNING token
            """
        ),
        {
            "patient_id": patient_id,
            "token": token,
            "kms_key": kms_key,
            "name": pii.get("name", ""),
            "dob": str(pii.get("dob", "")),
            "address": pii.get("address", ""),
            "phone": pii.get("phone", ""),
            "email": pii.get("email", ""),
        },
    )
    # On insert this is the freshly generated token; on conflict (existing patient_id) it's
    # the patient's existing token, which is intentionally left unchanged.
    return result.scalar_one()


async def read_patient_pii(session: AsyncSession, patient_id: str, accessed_by: str) -> dict[str, str] | None:
    # Decryption happens in Postgres (pgp_sym_decrypt) so plaintext PII never needs to
    # be reconstructed application-side from raw bytes.
    kms_key = require_kms_key()
    result = await session.execute(
        text(
            """
            SELECT
                pgp_sym_decrypt(name_encrypted, :kms_key) AS name,
                pgp_sym_decrypt(dob_encrypted, :kms_key) AS dob,
                pgp_sym_decrypt(address_encrypted, :kms_key) AS address,
                pgp_sym_decrypt(phone_encrypted, :kms_key) AS phone,
                pgp_sym_decrypt(email_encrypted, :kms_key) AS email
            FROM vault.patient_vault
            WHERE patient_id = :patient_id
            """
        ),
        {"patient_id": patient_id, "kms_key": kms_key},
    )
    row = result.mappings().one_or_none()
    if row is None:
        return None

    await append_access_log(session, patient_id, accessed_by)
    return {field: row[field] for field in PII_FIELDS}


async def append_access_log(session: AsyncSession, patient_id: str, accessed_by: str) -> None:
    entry = {
        "accessed_by": accessed_by,
        "accessed_at": datetime.now(timezone.utc).isoformat(),
    }
    await session.execute(
        text(
            """
            UPDATE vault.patient_vault
            SET access_log = COALESCE(access_log, '[]'::jsonb) || CAST(:entry AS jsonb)
            WHERE patient_id = :patient_id
            """
        ),
        {"patient_id": patient_id, "entry": json.dumps([entry])},
    )
