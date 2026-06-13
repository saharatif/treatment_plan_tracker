from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.checkpoints import PlanStatus, evaluate_plan_checkpoints


def _plan(**overrides):
    base = {
        "plan_id": "PLN-2026-003",
        "patient_id": "PAT-2026-00847",
        "plan_start": date(2026, 6, 13),
        "duration_days": 14,
        "buffer_days": 3,
        "extension_days": 7,
        "target_date": date(2026, 6, 27),
        "hard_stop": date(2026, 7, 4),
        "next_visit": date(2026, 7, 8),
        "status": "active",
    }
    base.update(overrides)
    return base


def _session_completed_count(count: int) -> AsyncMock:
    count_result = MagicMock()
    count_result.scalar_one.return_value = count
    session = AsyncMock()
    session.execute = AsyncMock(return_value=count_result)
    return session


@pytest.mark.asyncio
async def test_checkpoint_one_alerts_but_keeps_active():
    session = _session_completed_count(4)

    status = await evaluate_plan_checkpoints(_plan(), session, today=date(2026, 6, 24))

    assert status == PlanStatus.ACTIVE
    assert session.execute.call_count == 3


@pytest.mark.asyncio
async def test_checkpoint_two_completed_sets_completed():
    session = _session_completed_count(10)

    status = await evaluate_plan_checkpoints(_plan(), session, today=date(2026, 6, 27))

    assert status == PlanStatus.COMPLETED
    assert session.execute.call_count == 4


@pytest.mark.asyncio
async def test_checkpoint_two_partial_sets_extended():
    session = _session_completed_count(3)

    status = await evaluate_plan_checkpoints(_plan(), session, today=date(2026, 6, 27))

    assert status == PlanStatus.EXTENDED
    assert session.execute.call_count == 4


@pytest.mark.asyncio
async def test_checkpoint_four_closes_and_locks_plan(monkeypatch):
    session = _session_completed_count(7)
    called = {}

    async def fake_report(plan_id, session):
        called["plan_id"] = plan_id

    monkeypatch.setattr("app.services.checkpoints.generate_completion_report", fake_report)

    status = await evaluate_plan_checkpoints(_plan(status="extended"), session, today=date(2026, 7, 4))

    assert status == PlanStatus.CLOSED
    assert called["plan_id"] == "PLN-2026-003"
    assert session.execute.call_count == 6
