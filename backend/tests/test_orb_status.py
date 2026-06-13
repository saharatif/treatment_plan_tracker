from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.orbs import complete_orb, set_orb_status


def _session_with_plan_status(status: str | None) -> AsyncMock:
    result = MagicMock()
    if status is None:
        result.mappings.return_value.one_or_none.return_value = None
    else:
        result.mappings.return_value.one_or_none.return_value = {
            "orb_ref": "ORB-PAT00847-001",
            "plan_id": "PLN-2026-003",
            "plan_status": status,
        }
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_complete_orb_updates_open_plan():
    session = _session_with_plan_status("active")

    await complete_orb("ORB-PAT00847-001", session, notes="done")

    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_set_orb_status_rejects_closed_plan():
    session = _session_with_plan_status("closed")

    with pytest.raises(ValueError, match="closed"):
        await set_orb_status("ORB-PAT00847-001", "skipped", session)

    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_set_orb_status_rejects_missing_orb():
    session = _session_with_plan_status(None)

    with pytest.raises(ValueError, match="not found"):
        await set_orb_status("ORB-PAT00847-001", "in_progress", session)
