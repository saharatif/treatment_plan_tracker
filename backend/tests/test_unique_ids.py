from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.storage import generate_unique_patient_id, generate_unique_plan_id
from app.services.vault import generate_unique_token


def _session_with_results(*existence_checks: bool) -> AsyncMock:
    """Build a fake AsyncSession whose execute() reports the given existence checks in
    order: True -> row found (ID taken), False -> no row (ID free)."""
    results = []
    for taken in existence_checks:
        result = MagicMock()
        result.first.return_value = ("row",) if taken else None
        results.append(result)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=results)
    return session


@pytest.mark.asyncio
async def test_generate_unique_patient_id_retries_on_collision(monkeypatch):
    session = _session_with_results(True, False)
    monkeypatch.setattr(
        "app.services.storage.generate_patient_id",
        iter(["PAT-2026-00001", "PAT-2026-00002"]).__next__,
    )

    result = await generate_unique_patient_id(session)

    assert result == "PAT-2026-00002"
    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_generate_unique_plan_id_returns_first_free_candidate(monkeypatch):
    session = _session_with_results(False)
    monkeypatch.setattr(
        "app.services.storage.generate_plan_id",
        iter(["PLN-2026-001"]).__next__,
    )

    result = await generate_unique_plan_id(session)

    assert result == "PLN-2026-001"
    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_generate_unique_patient_id_gives_up_after_max_attempts(monkeypatch):
    from app.ids import MAX_UNIQUE_ID_ATTEMPTS

    session = _session_with_results(*([True] * MAX_UNIQUE_ID_ATTEMPTS))
    monkeypatch.setattr(
        "app.services.storage.generate_patient_id",
        lambda: "PAT-2026-00001",
    )

    with pytest.raises(RuntimeError):
        await generate_unique_patient_id(session)


@pytest.mark.asyncio
async def test_generate_unique_token_retries_on_collision(monkeypatch):
    session = _session_with_results(True, False)
    monkeypatch.setattr(
        "app.services.vault.generate_token",
        iter(["tok_aaaaaaaaaaaaaaaa", "tok_bbbbbbbbbbbbbbbb"]).__next__,
    )

    result = await generate_unique_token(session)

    assert result == "tok_bbbbbbbbbbbbbbbb"
    assert session.execute.call_count == 2
