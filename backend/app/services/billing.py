from datetime import date
from decimal import Decimal
import smtplib
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import BillingCode, QuotationLog


def normalize_billing_code(code: str) -> str:
    return code.split(":")[-1].strip().upper()


def collect_billing_codes(plan: dict[str, Any]) -> list[dict[str, str]]:
    collected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for diagnosis in plan.get("diagnoses", []):
        code = normalize_billing_code(str(diagnosis.get("code", "")))
        if code and (code, "diagnosis") not in seen:
            collected.append({"code": code, "source": "diagnosis"})
            seen.add((code, "diagnosis"))

    for orb in plan.get("orbs", []):
        for raw_code in orb.get("billing_codes", []):
            code = normalize_billing_code(str(raw_code))
            source = f"orb_{orb.get('orb_number')}"
            if code and (code, source) not in seen:
                collected.append({"code": code, "source": source})
                seen.add((code, source))

    return collected


async def build_quotation(plan: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    codes = collect_billing_codes(plan)
    unique_codes = sorted({item["code"] for item in codes})
    rows = []
    if unique_codes:
        result = await session.execute(select(BillingCode).where(BillingCode.code.in_(unique_codes)))
        rows = result.scalars().all()
    found = {row.code: row for row in rows}

    line_items: list[dict[str, Any]] = []
    diagnoses: list[dict[str, Any]] = []
    unmatched: list[dict[str, str]] = []

    for item in codes:
        row = found.get(item["code"])
        if row is None:
            unmatched.append(item)
            continue
        payload = _billing_row_payload(row, source=item["source"])
        if row.is_billable:
            line_items.append(payload)
        else:
            diagnoses.append(payload)

    total = sum((Decimal(str(item["unit_price"] or 0)) for item in line_items), Decimal("0"))
    quote = {
        "quote_id": f"QTE-{date.today():%Y}-{str(plan['plan_id'])[-3:]}",
        "plan_id": plan["plan_id"],
        "patient_id": plan["patient_id"],
        "line_items": line_items,
        "diagnoses": diagnoses,
        "unmatched": unmatched,
        "needs_auth": [item for item in line_items if item["requires_auth"]],
        "total": float(total),
        "plan_snapshot": plan,
    }
    return quote


async def log_quotation(quote: dict[str, Any], session: AsyncSession) -> None:
    stmt = insert(QuotationLog).values(
        quote_id=quote["quote_id"],
        plan_id=quote["plan_id"],
        total=quote["total"],
        sent_to=settings.billing_email or None,
        payload=quote,
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["quote_id"],
            set_={
                "total": stmt.excluded.total,
                "sent_to": stmt.excluded.sent_to,
                "payload": stmt.excluded.payload,
            },
        )
    )


async def email_quotation(quote: dict[str, Any]) -> bool:
    if not settings.smtp_host or not settings.billing_email:
        return False

    message = EmailMessage()
    message["Subject"] = f"New quotation ready for review - {quote['quote_id']}"
    message["From"] = "no-reply@orbs.local"
    message["To"] = settings.billing_email
    secure_url = f"{settings.billing_portal_base_url.rstrip('/')}/quotes/{quote['quote_id']}"
    message.set_content(
        "\n".join(
            [
                "A treatment plan quotation is ready for review.",
                f"Quote ID: {quote['quote_id']}",
                f"Plan ID: {quote['plan_id']}",
                f"Patient token: {quote['patient_id']}",
                f"Estimated total: ${quote['total']:.2f}",
                f"View securely: {secure_url}",
                "",
                "No clinical line items or diagnosis details are included in this email.",
            ]
        )
    )

    with smtplib.SMTP(settings.smtp_host) as smtp:
        smtp.send_message(message)
    return True


async def quote_email_and_log(plan: dict[str, Any], session: AsyncSession) -> dict[str, Any]:
    quote = await build_quotation(plan, session)
    quote["email_sent"] = await email_quotation(quote)
    await log_quotation(quote, session)
    return quote


async def get_quotations(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(
        text(
            """
            SELECT quote_id, plan_id, total, sent_to, sent_at, payload
            FROM billing.quotation_log
            ORDER BY sent_at DESC
            """
        )
    )
    return [
        {
            "quote_id": row.quote_id,
            "plan_id": row.plan_id,
            "total": float(row.total or 0),
            "sent_to": row.sent_to,
            "sent_at": row.sent_at.isoformat() if row.sent_at else None,
            "payload": row.payload,
        }
        for row in result
    ]


def _billing_row_payload(row: BillingCode, source: str) -> dict[str, Any]:
    return {
        "code": row.code,
        "code_system": row.code_system,
        "description": row.description,
        "unit_price": float(row.unit_price or 0),
        "medicare_rate": float(row.medicare_rate or 0),
        "is_billable": row.is_billable,
        "requires_auth": row.requires_auth,
        "source": source,
    }
