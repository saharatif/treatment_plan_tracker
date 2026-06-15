"""Generates the per-plan completion report PDF (final orb outcomes, derived
adherence metrics, and alert history) using reportlab, and caches it to disk
under settings.report_output_dir."""

from pathlib import Path
import re
from statistics import mean
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


async def generate_completion_report(plan_id: str, session: AsyncSession) -> Path:
    plan = await _fetch_plan(plan_id, session)
    if plan is None:
        raise ValueError(f"Plan not found: {plan_id}")
    orbs = await _fetch_orbs(plan_id, session)
    alerts = await _fetch_alerts(plan_id, session)
    metrics = _derive_metrics(orbs)

    output_dir = Path(settings.report_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{plan_id}_completion_report.pdf"
    _write_pdf(report_path, plan, orbs, alerts, metrics)
    return report_path


async def get_or_create_completion_report(plan_id: str, session: AsyncSession) -> Path:
    # Reports are immutable once generated (a plan is only closed once), so reuse the
    # cached file on disk instead of re-querying and re-rendering.
    report_path = Path(settings.report_output_dir) / f"{plan_id}_completion_report.pdf"
    if report_path.exists():
        return report_path
    return await generate_completion_report(plan_id, session)


async def _fetch_plan(plan_id: str, session: AsyncSession) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT plan_id, patient_id, provider, plan_start, target_date, hard_stop,
                   next_visit, status
            FROM app.treatment_plans
            WHERE plan_id = :plan_id
            """
        ),
        {"plan_id": plan_id},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def _fetch_orbs(plan_id: str, session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT po.orb_number, po.orb_ref, po.status, po.target_date, po.completed_at,
                   po.notes, o.catalog_code, o.title, o.category
            FROM app.patient_orbs po
            LEFT JOIN app.orbs o ON o.id = po.catalog_orb_id
            WHERE po.plan_id = :plan_id
            ORDER BY po.orb_number
            """
        ),
        {"plan_id": plan_id},
    )
    return [dict(row) for row in result.mappings()]


async def _fetch_alerts(plan_id: str, session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT recipient, checkpoint, message, sent_at
            FROM app.alert_log
            WHERE plan_id = :plan_id
            ORDER BY sent_at
            """
        ),
        {"plan_id": plan_id},
    )
    return [dict(row) for row in result.mappings()]


def _derive_metrics(orbs: list[dict[str, Any]]) -> dict[str, Any]:
    # Lightweight regex scan over free-form orb notes to surface adherence signals
    # (e.g. "glucose: 145", "adherence: 90%") in the report without a separate
    # structured-data entry workflow.
    notes = "\n".join(str(orb.get("notes") or "") for orb in orbs)
    glucose_values = [int(value) for value in re.findall(r"glucose[:= ]+(\d{2,3})", notes, re.IGNORECASE)]
    exercise_days = len(re.findall(r"exercise|walk|workout", notes, re.IGNORECASE))
    adherence_mentions = re.findall(r"adherence[:= ]+(\d{1,3})%", notes, re.IGNORECASE)
    # Last mention wins, assuming later notes reflect the most recent self-report.
    adherence = int(adherence_mentions[-1]) if adherence_mentions else None
    return {
        "glucose_average": round(mean(glucose_values), 1) if glucose_values else None,
        "exercise_days": exercise_days,
        "medication_adherence": adherence,
    }


def _write_pdf(
    path: Path,
    plan: dict[str, Any],
    orbs: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> None:
    completed = sum(1 for orb in orbs if orb["status"] == "complete")
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 50

    def line(text: str, size: int = 10, bold: bool = False) -> None:
        # Auto-paginate when nearing the bottom margin, and truncate long lines so
        # they don't run off the page edge.
        nonlocal y
        if y < 60:
            c.showPage()
            y = height - 50
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(50, y, text[:110])
        y -= size + 6

    line("10 Orbs Completion Report", 16, True)
    line(f"Plan: {plan['plan_id']}    Patient Token: {plan['patient_id']}    Status: {plan['status']}", 10)
    line(f"Provider: {plan.get('provider') or 'N/A'}    Next Visit: {plan.get('next_visit') or 'N/A'}", 10)
    line(f"Final Completion: {completed}/10", 12, True)
    y -= 6

    line("Orb Outcomes", 12, True)
    for orb in orbs:
        title = orb.get("title") or orb.get("catalog_code") or orb["orb_ref"]
        line(f"{orb['orb_number']:02d}. {title} - {orb['status']} - {orb.get('notes') or ''}", 9)

    y -= 6
    line("Derived Adherence Metrics", 12, True)
    line(f"Glucose log average: {metrics['glucose_average'] if metrics['glucose_average'] is not None else 'N/A'}")
    line(f"Exercise days noted: {metrics['exercise_days']}")
    line(f"Medication adherence: {metrics['medication_adherence'] if metrics['medication_adherence'] is not None else 'N/A'}")

    y -= 6
    line("Alert History", 12, True)
    if not alerts:
        line("No alerts recorded.")
    for alert in alerts:
        sent_at = alert["sent_at"].isoformat() if hasattr(alert["sent_at"], "isoformat") else alert["sent_at"]
        line(f"{sent_at} [{alert['recipient']}/{alert['checkpoint']}]: {alert['message']}", 8)

    c.setTitle(f"{plan['plan_id']} Completion Report")
    c.save()
