from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ids import MAX_UNIQUE_ID_ATTEMPTS, generate_patient_id, generate_plan_id
from app.services.vault import upsert_patient_vault


def _as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


async def _patient_id_exists(session: AsyncSession, patient_id: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM vault.patient_vault WHERE patient_id = :patient_id"),
        {"patient_id": patient_id},
    )
    return result.first() is not None


async def _plan_id_exists(session: AsyncSession, plan_id: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM app.treatment_plans WHERE plan_id = :plan_id"),
        {"plan_id": plan_id},
    )
    return result.first() is not None


async def generate_unique_patient_id(session: AsyncSession) -> str:
    for _ in range(MAX_UNIQUE_ID_ATTEMPTS):
        candidate = generate_patient_id()
        if not await _patient_id_exists(session, candidate):
            return candidate
    raise RuntimeError("Could not generate a unique patient_id")


async def generate_unique_plan_id(session: AsyncSession) -> str:
    for _ in range(MAX_UNIQUE_ID_ATTEMPTS):
        candidate = generate_plan_id()
        if not await _plan_id_exists(session, candidate):
            return candidate
    raise RuntimeError("Could not generate a unique plan_id")


async def store_plan(plan: dict[str, Any], pii: dict[str, Any] | None, session: AsyncSession) -> str:
    patient_id = plan.get("patient_id") or await generate_unique_patient_id(session)
    plan_id = plan.get("plan_id") or await generate_unique_plan_id(session)
    plan_start = _as_date(plan["plan_start"])
    duration_days = int(plan.get("duration_days", 14))
    buffer_days = int(plan.get("buffer_days", 3))
    extension_days = int(plan.get("extension_days", 7))
    target_date = _as_date(plan.get("target_date", plan_start + timedelta(days=duration_days)))
    hard_stop = _as_date(plan.get("hard_stop", target_date + timedelta(days=extension_days)))
    next_visit = plan.get("next_visit")
    if next_visit:
        next_visit = _as_date(next_visit)

    if pii:
        await upsert_patient_vault(session, patient_id, pii)
    status = plan.get("status", "active")
    await session.execute(
        text(
            """
            INSERT INTO app.treatment_plans (
                plan_id, patient_id, provider, plan_start, duration_days, buffer_days,
                extension_days, target_date, hard_stop, next_visit, status
            )
            VALUES (
                :plan_id, :patient_id, :provider, :plan_start, :duration_days, :buffer_days,
                :extension_days, :target_date, :hard_stop, :next_visit, :status
            )
            ON CONFLICT (plan_id) DO UPDATE SET
                patient_id = EXCLUDED.patient_id,
                provider = EXCLUDED.provider,
                plan_start = EXCLUDED.plan_start,
                duration_days = EXCLUDED.duration_days,
                buffer_days = EXCLUDED.buffer_days,
                extension_days = EXCLUDED.extension_days,
                target_date = EXCLUDED.target_date,
                hard_stop = EXCLUDED.hard_stop,
                next_visit = EXCLUDED.next_visit,
                status = EXCLUDED.status
            """
        ),
        {
            "plan_id": plan_id,
            "patient_id": patient_id,
            "provider": plan.get("provider"),
            "plan_start": plan_start,
            "duration_days": duration_days,
            "buffer_days": buffer_days,
            "extension_days": extension_days,
            "target_date": target_date,
            "hard_stop": hard_stop,
            "next_visit": next_visit,
            "status": status,
        },
    )

    for diagnosis in plan.get("diagnoses", []):
        await session.execute(
            text(
                """
                INSERT INTO app.diagnoses (plan_id, code, description, code_system)
                VALUES (:plan_id, :code, :description, :code_system)
                """
            ),
            {
                "plan_id": plan_id,
                "code": diagnosis.get("code"),
                "description": diagnosis.get("description"),
                "code_system": diagnosis.get("code_system", "ICD-10"),
            },
        )

    return patient_id
