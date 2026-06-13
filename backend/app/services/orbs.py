from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

OrbStatus = Literal["pending", "in_progress", "complete", "skipped", "locked"]
MUTABLE_ORB_STATUSES = {"pending", "in_progress", "complete", "skipped"}


async def complete_orb(orb_ref: str, session: AsyncSession, notes: str | None = None) -> None:
    await set_orb_status(orb_ref, "complete", session, notes=notes)


async def set_orb_status(
    orb_ref: str,
    status: OrbStatus,
    session: AsyncSession,
    notes: str | None = None,
) -> None:
    if status not in MUTABLE_ORB_STATUSES:
        raise ValueError(f"Unsupported orb status: {status}")

    row = await _orb_with_plan_status(orb_ref, session)
    if row is None:
        raise ValueError("Orb not found")
    if row["plan_status"] == "closed":
        raise ValueError("Plan is closed - orbs are locked")

    await session.execute(
        text(
            """
            UPDATE app.patient_orbs
            SET status = :status,
                completed_at = CASE WHEN :status = 'complete' THEN NOW() ELSE completed_at END,
                notes = COALESCE(:notes, notes),
                updated_at = NOW()
            WHERE orb_ref = :orb_ref
            """
        ),
        {"orb_ref": orb_ref, "status": status, "notes": notes},
    )


async def _orb_with_plan_status(orb_ref: str, session: AsyncSession) -> dict | None:
    return await get_orb_context(orb_ref, session)


async def get_orb_context(orb_ref: str, session: AsyncSession) -> dict | None:
    result = await session.execute(
        text(
            """
            SELECT po.orb_ref, po.plan_id, po.patient_id, tp.status AS plan_status
            FROM app.patient_orbs po
            JOIN app.treatment_plans tp ON tp.plan_id = po.plan_id
            WHERE po.orb_ref = :orb_ref
            """
        ),
        {"orb_ref": orb_ref},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None
