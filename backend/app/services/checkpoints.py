"""Daily checkpoint evaluation for treatment plans.

Each plan has 4 checkpoints derived from plan_start/duration_days/buffer_days/
extension_days: an early-warning nudge, the target-date outcome (complete,
grace period, or extension), a final-warning nudge, and the hard stop that
closes the plan and generates its completion report. Run once per plan per
day via app/scheduler.py.
"""

from datetime import date, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reports import generate_completion_report


class PlanStatus(str, Enum):
    ACTIVE = "active"
    IN_GRACE = "in_grace"
    EXTENDED = "extended"
    COMPLETED = "completed"
    CLOSED = "closed"


async def count_completed_orbs(plan_id: str, session: AsyncSession) -> int:
    result = await session.execute(
        text(
            """
            SELECT COUNT(*) FILTER (WHERE status = 'complete') AS completed
            FROM app.patient_orbs
            WHERE plan_id = :plan_id
            """
        ),
        {"plan_id": plan_id},
    )
    return int(result.scalar_one() or 0)


async def set_plan_status(plan_id: str, status: PlanStatus, session: AsyncSession) -> None:
    await session.execute(
        text("UPDATE app.treatment_plans SET status = :status WHERE plan_id = :plan_id"),
        {"plan_id": plan_id, "status": status.value},
    )


async def alert_patient(plan: dict[str, Any], checkpoint: str, message: str, session: AsyncSession) -> None:
    await _write_alert(plan["plan_id"], "patient", checkpoint, message, session)


async def alert_clinic(plan: dict[str, Any], checkpoint: str, message: str, session: AsyncSession) -> None:
    await _write_alert(plan["plan_id"], "clinic", checkpoint, message, session)


async def close_plan(plan_id: str, session: AsyncSession) -> None:
    completed = await count_completed_orbs(plan_id, session)
    plan = {"plan_id": plan_id}
    await set_plan_status(plan_id, PlanStatus.CLOSED, session)
    # Freeze any orb that wasn't completed by the hard stop - "locked" orbs can no
    # longer be edited via the patient/clinician status endpoints.
    await session.execute(
        text(
            """
            UPDATE app.patient_orbs
            SET status = CASE WHEN status = 'complete' THEN status ELSE 'locked' END,
                updated_at = NOW()
            WHERE plan_id = :plan_id
            """
        ),
        {"plan_id": plan_id},
    )
    await alert_patient(plan, "checkpoint_4", "Plan period ended. Your visit is mandatory.", session)
    await alert_clinic(plan, "checkpoint_4", f"Plan closed. Final: {completed}/10 - flag for doctor review.", session)
    await generate_completion_report(plan_id, session)


async def evaluate_plan_checkpoints(
    plan: dict[str, Any],
    session: AsyncSession,
    today: date | None = None,
) -> PlanStatus | None:
    today = today or date.today()
    plan_id = plan["plan_id"]
    target_date = plan.get("target_date") or plan["plan_start"] + timedelta(days=plan["duration_days"])
    hard_stop = plan.get("hard_stop") or target_date + timedelta(days=plan["extension_days"])
    buffer_days = int(plan.get("buffer_days", 3))
    completed = await count_completed_orbs(plan_id, session)
    current_status = PlanStatus(plan.get("status", PlanStatus.ACTIVE))

    # Checkpoint 1: early warning a few days before target_date if the patient is
    # falling behind (< 8/10 orbs done).
    if today == target_date - timedelta(days=buffer_days) and completed < 8:
        await alert_patient(plan, "checkpoint_1", f"3 days left - {completed}/10 done.", session)
        await alert_clinic(
            plan,
            "checkpoint_1",
            f"Completion jeopardized ({completed}/10). Next visit: {plan.get('next_visit')}",
            session,
        )
        return current_status

    # Checkpoint 2: target_date outcome - either fully complete, eligible for a grace
    # period (>=8/10), or extended for stragglers.
    if today == target_date:
        if completed == 10:
            await set_plan_status(plan_id, PlanStatus.COMPLETED, session)
            await alert_patient(plan, "checkpoint_2", "All 10 orbs complete.", session)
            await alert_clinic(plan, "checkpoint_2", "Patient completed on time.", session)
            return PlanStatus.COMPLETED
        if completed >= 8:
            await set_plan_status(plan_id, PlanStatus.IN_GRACE, session)
            await alert_patient(plan, "checkpoint_2", f"{completed}/10 - finish within 7 days.", session)
            await alert_clinic(plan, "checkpoint_2", f"Grace period active ({completed}/10).", session)
            return PlanStatus.IN_GRACE
        await set_plan_status(plan_id, PlanStatus.EXTENDED, session)
        await alert_patient(plan, "checkpoint_2", "Extension activated - 7 more days.", session)
        await alert_clinic(plan, "checkpoint_2", f"Behind ({completed}/10). Consider outreach.", session)
        return PlanStatus.EXTENDED

    # Checkpoint 3: final warning a few days before the hard stop if still incomplete.
    if today == hard_stop - timedelta(days=buffer_days) and completed < 10:
        await alert_patient(plan, "checkpoint_3", f"Final 3 days - hard deadline {hard_stop:%b %d}.", session)
        await alert_clinic(plan, "checkpoint_3", f"Still incomplete ({completed}/10). Escalate.", session)
        return current_status

    # Checkpoint 4: hard stop reached - close the plan regardless of completion.
    if today >= hard_stop and current_status != PlanStatus.CLOSED:
        await close_plan(plan_id, session)
        return PlanStatus.CLOSED

    return None


async def evaluate_all_open_plans(session: AsyncSession, today: date | None = None) -> int:
    # Entry point for the daily scheduler job - evaluates every plan that isn't
    # already closed and commits all resulting status changes/alerts at once.
    result = await session.execute(
        text(
            """
            SELECT plan_id, patient_id, provider, plan_start, duration_days, buffer_days,
                   extension_days, target_date, hard_stop, next_visit, status
            FROM app.treatment_plans
            WHERE status != 'closed'
            """
        )
    )
    count = 0
    for row in result.mappings():
        await evaluate_plan_checkpoints(dict(row), session, today=today)
        count += 1
    await session.commit()
    return count


async def _write_alert(
    plan_id: str,
    recipient: str,
    checkpoint: str,
    message: str,
    session: AsyncSession,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO app.alert_log (plan_id, recipient, checkpoint, message)
            VALUES (:plan_id, :recipient, :checkpoint, :message)
            """
        ),
        {
            "plan_id": plan_id,
            "recipient": recipient,
            "checkpoint": checkpoint,
            "message": message,
        },
    )
