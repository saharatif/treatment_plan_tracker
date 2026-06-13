from datetime import date
from typing import Any


REQUIRED_PLAN_FIELDS = ("plan_id", "patient_id", "plan_start")


def validate_parsed_plan(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    orbs = plan.get("orbs", [])

    if len(orbs) != 10:
        errors.append(f"Expected 10 orbs, found {len(orbs)}")

    numbers = sorted(orb.get("orb_number") for orb in orbs if "orb_number" in orb)
    if numbers != list(range(1, 11)):
        errors.append(f"Orb numbers not 1-10: {numbers}")

    for field in REQUIRED_PLAN_FIELDS:
        if not plan.get(field):
            errors.append(f"Missing required field: {field}")

    for field in ("plan_start", "next_visit"):
        if plan.get(field) and not _is_iso_date(plan[field]):
            errors.append(f"Invalid date for {field}: {plan[field]}")

    for orb in orbs:
        if not orb.get("title"):
            errors.append(f"Orb {orb.get('orb_number', '?')} missing title")
        if orb.get("target_date") and not _is_iso_date(orb["target_date"]):
            errors.append(f"Orb {orb.get('orb_number', '?')} has invalid target_date: {orb['target_date']}")
        if not isinstance(orb.get("billing_codes", []), list):
            errors.append(f"Orb {orb.get('orb_number', '?')} billing_codes must be a list")

    return (len(errors) == 0, errors)


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True
