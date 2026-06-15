"""Turns the 10 AI-parsed orbs from a confirmed quotation into patient_orbs rows.

Each parsed orb is fuzzy-matched against the orb catalog (title similarity +
category + billing code overlap + exact catalog_code match) so that orbs the
AI parser didn't tag with a catalog_code can still be linked for reporting.
"""

from datetime import date
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ids import generate_orb_ref
from app.models import Orb


def normalize_codes(codes: list[str] | None) -> set[str]:
    return {code.split(":")[-1].strip().upper() for code in codes or [] if code.strip()}


def title_score(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def score_catalog_match(parsed_orb: dict[str, Any], catalog_orb: Orb) -> float:
    # Weighted scoring: title similarity is the baseline signal, category match and
    # shared billing codes add confidence, and an exact catalog_code (when the AI
    # parser identified one) is treated as a near-certain match.
    score = title_score(str(parsed_orb.get("title", "")), catalog_orb.title)
    if parsed_orb.get("category") and parsed_orb["category"].lower() == catalog_orb.category.lower():
        score += 0.25
    parsed_codes = normalize_codes(parsed_orb.get("billing_codes"))
    catalog_codes = normalize_codes(catalog_orb.billing_codes)
    if parsed_codes and parsed_codes & catalog_codes:
        score += 0.45
    if parsed_orb.get("catalog_code") == catalog_orb.catalog_code:
        score += 1.0
    return score


async def match_catalog_orb(parsed_orb: dict[str, Any], session: AsyncSession) -> int | None:
    result = await session.execute(select(Orb))
    candidates = result.scalars().all()
    if not candidates:
        return None

    # 0.72 threshold: title similarity alone (max 1.0) usually isn't enough, so this
    # requires either a near-exact title or a partial title match plus category/code
    # corroboration. Below this, the orb is left unmatched for manual catalog review.
    best = max(candidates, key=lambda candidate: score_catalog_match(parsed_orb, candidate))
    return best.id if score_catalog_match(parsed_orb, best) >= 0.72 else None


async def notify_patient(session: AsyncSession, plan_id: str, message: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO app.alert_log (plan_id, recipient, checkpoint, message)
            VALUES (:plan_id, 'patient', 'enrollment', :message)
            """
        ),
        {"plan_id": plan_id, "message": message},
    )


async def enroll(plan_id: str, patient_id: str, parsed_orbs: list[dict[str, Any]], session: AsyncSession) -> None:
    result = await session.execute(
        text("SELECT target_date FROM app.treatment_plans WHERE plan_id = :plan_id"),
        {"plan_id": plan_id},
    )
    plan = result.mappings().one_or_none()
    if plan is None:
        raise ValueError(f"Plan not found: {plan_id}")

    for orb in parsed_orbs:
        orb_number = int(orb["orb_number"])
        catalog_orb_id = await match_catalog_orb(orb, session)
        # ON CONFLICT lets enrollment be re-run safely (e.g. if confirm-billing is
        # retried) without creating duplicate orb rows for the same plan/orb_number.
        await session.execute(
            text(
                """
                INSERT INTO app.patient_orbs (
                    orb_ref, plan_id, patient_id, orb_number, catalog_orb_id, status, target_date, notes
                )
                VALUES (
                    :orb_ref, :plan_id, :patient_id, :orb_number, :catalog_orb_id,
                    'pending', :target_date, :notes
                )
                ON CONFLICT (plan_id, orb_number) DO UPDATE SET
                    catalog_orb_id = EXCLUDED.catalog_orb_id,
                    status = EXCLUDED.status,
                    target_date = EXCLUDED.target_date,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                """
            ),
            {
                "orb_ref": generate_orb_ref(patient_id, orb_number),
                "plan_id": plan_id,
                "patient_id": patient_id,
                "orb_number": orb_number,
                "catalog_orb_id": catalog_orb_id,
                "target_date": _coerce_date(orb.get("target_date")) or plan["target_date"],
                # Flag unmatched orbs in their notes so staff know to manually map them
                # to a catalog entry.
                "notes": "Catalog review required" if catalog_orb_id is None else orb.get("notes"),
            },
        )

    await notify_patient(session, plan_id, "Your 10 Orbs to Better plan starts today.")


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return None
