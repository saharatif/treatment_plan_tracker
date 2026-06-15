from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.enrollment import _coerce_date, enroll


def test_coerce_date_parses_iso_string():
    assert _coerce_date("2025-06-14") == date(2025, 6, 14)


def test_coerce_date_passes_through_date():
    assert _coerce_date(date(2025, 6, 14)) == date(2025, 6, 14)


def test_coerce_date_handles_missing_value():
    assert _coerce_date(None) is None
    assert _coerce_date("") is None


@pytest.mark.asyncio
async def test_enroll_coerces_string_target_date_before_insert(monkeypatch):
    plan_result = MagicMock()
    plan_result.mappings.return_value.one_or_none.return_value = {"target_date": date(2025, 6, 20)}

    session = AsyncMock()
    session.execute = AsyncMock(return_value=plan_result)

    monkeypatch.setattr("app.services.enrollment.match_catalog_orb", AsyncMock(return_value=None))

    parsed_orbs = [{"orb_number": 1, "target_date": "2025-06-14", "notes": "n"}]

    await enroll("PLN-2026-003", "PAT-2026-00847", parsed_orbs, session)

    insert_call = session.execute.call_args_list[1]
    params = insert_call[0][1]
    assert params["target_date"] == date(2025, 6, 14)
