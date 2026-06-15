"""Read-only endpoints for the clinic dashboard, patient detail view, and
at-risk patient list. All plan_status / OVERDUE / IN GRACE / ON TRACK labels
are computed in SQL from target_date and hard_stop relative to CURRENT_DATE."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User, get_current_user, require_roles
from app.database import get_session

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", dependencies=[Depends(require_roles("clinician", "coordinator", "billing"))])
async def dashboard(session: AsyncSession = Depends(get_session)) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT
                tp.patient_id, tp.plan_id, tp.status,
                COUNT(*) FILTER (WHERE po.status = 'complete') AS completed,
                tp.target_date - CURRENT_DATE AS days_remaining,
                CASE
                  WHEN CURRENT_DATE > tp.hard_stop THEN 'OVERDUE'
                  WHEN CURRENT_DATE > tp.target_date THEN 'IN GRACE'
                  ELSE 'ON TRACK'
                END AS plan_status
            FROM app.treatment_plans tp
            JOIN app.patient_orbs po ON po.plan_id = tp.plan_id
            WHERE tp.status != 'closed'
            GROUP BY tp.patient_id, tp.plan_id, tp.status, tp.target_date, tp.hard_stop
            ORDER BY completed DESC
            """
        )
    )
    return [_mapping_to_dict(row) for row in result.mappings()]


@router.get("/patients/{patient_id}")
async def patient_detail(
    patient_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    # Patients may only view their own plan; staff roles can view any patient.
    if user.role == "patient" and user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Patient token scope mismatch")
    if user.role not in {"clinician", "coordinator", "billing", "patient"}:
        raise HTTPException(status_code=403, detail="Insufficient role")
    plan_result = await session.execute(
        text(
            """
            SELECT plan_id, patient_id, provider, plan_start, target_date, hard_stop,
                   next_visit, status
            FROM app.treatment_plans
            WHERE patient_id = :patient_id
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"patient_id": patient_id},
    )
    plan = plan_result.mappings().one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Patient plan not found")

    orb_result = await session.execute(
        text(
            """
            SELECT po.orb_ref, po.orb_number, po.status, po.target_date, po.completed_at,
                   po.notes, o.catalog_code, o.title, o.category
            FROM app.patient_orbs po
            LEFT JOIN app.orbs o ON o.id = po.catalog_orb_id
            WHERE po.plan_id = :plan_id
            ORDER BY po.orb_number
            """
        ),
        {"plan_id": plan["plan_id"]},
    )
    return {
        "plan": _mapping_to_dict(plan),
        "orbs": [_mapping_to_dict(row) for row in orb_result.mappings()],
    }


@router.get("/at-risk", dependencies=[Depends(require_roles("clinician", "coordinator"))])
async def at_risk(session: AsyncSession = Depends(get_session)) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT tp.patient_id,
                   tp.plan_id,
                   COUNT(*) FILTER (WHERE po.status = 'complete') AS completed,
                   tp.target_date - CURRENT_DATE AS days_left
            FROM app.treatment_plans tp
            JOIN app.patient_orbs po ON po.plan_id = tp.plan_id
            WHERE tp.status = 'active'
            GROUP BY tp.patient_id, tp.plan_id, tp.target_date
            HAVING COUNT(*) FILTER (WHERE po.status = 'complete') < 5
               AND tp.target_date - CURRENT_DATE <= 7
            ORDER BY days_left ASC
            """
        )
    )
    return [_mapping_to_dict(row) for row in result.mappings()]


def _mapping_to_dict(row) -> dict:
    # Converts date/datetime columns to ISO strings so rows are JSON-serializable.
    return {
        key: value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in dict(row).items()
    }
