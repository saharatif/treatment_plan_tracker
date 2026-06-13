from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_roles
from app.database import get_session
from app.services.billing import get_quotations
from app.services.enrollment import enroll

router = APIRouter(prefix="/api", tags=["billing"])


@router.post(
    "/plans/{plan_id}/confirm-billing",
    dependencies=[Depends(require_roles("billing", "clinician", "coordinator"))],
)
async def confirm_billing(plan_id: str, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    quote = await _latest_quote_for_plan(plan_id, session)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quotation not found for plan")

    plan_snapshot = quote.get("plan_snapshot") or {}
    parsed_orbs = plan_snapshot.get("orbs", [])
    patient_id = plan_snapshot.get("patient_id")
    if not patient_id or len(parsed_orbs) != 10:
        raise HTTPException(status_code=409, detail="Quotation payload is missing enrollment data")

    await enroll(plan_id, patient_id, parsed_orbs, session)
    await session.execute(
        text("UPDATE app.treatment_plans SET status = 'active' WHERE plan_id = :plan_id"),
        {"plan_id": plan_id},
    )
    await session.commit()
    return {"status": "active", "plan_id": plan_id}


@router.get("/quotations", dependencies=[Depends(require_roles("billing", "clinician", "coordinator"))])
async def list_quotations(session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await get_quotations(session)


async def _latest_quote_for_plan(plan_id: str, session: AsyncSession) -> dict | None:
    result = await session.execute(
        text(
            """
            SELECT payload
            FROM billing.quotation_log
            WHERE plan_id = :plan_id
            ORDER BY sent_at DESC
            LIMIT 1
            """
        ),
        {"plan_id": plan_id},
    )
    row = result.mappings().one_or_none()
    return row["payload"] if row else None
