from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import reports


def _result(row_or_rows):
    result = MagicMock()
    if isinstance(row_or_rows, list):
        result.mappings.return_value = row_or_rows
    else:
        mappings = MagicMock()
        mappings.one_or_none.return_value = row_or_rows
        result.mappings.return_value = mappings
    return result


@pytest.mark.asyncio
async def test_generate_completion_report_writes_pdf(tmp_path, monkeypatch):
    plan = {
        "plan_id": "PLN-2026-003",
        "patient_id": "PAT-2026-00847",
        "provider": "Dr. Nair",
        "plan_start": date(2026, 6, 13),
        "target_date": date(2026, 6, 27),
        "hard_stop": date(2026, 7, 4),
        "next_visit": date(2026, 7, 8),
        "status": "closed",
    }
    orbs = [
        {
            "orb_number": 1,
            "orb_ref": "ORB-PAT00847-001",
            "status": "complete",
            "target_date": date(2026, 6, 13),
            "completed_at": datetime.now(timezone.utc),
            "notes": "glucose 120 exercise adherence 90%",
            "catalog_code": "LAB-01",
            "title": "Blood Work",
            "category": "Lab",
        }
    ]
    alerts = [
        {
            "recipient": "clinic",
            "checkpoint": "checkpoint_4",
            "message": "Closed",
            "sent_at": datetime.now(timezone.utc),
        }
    ]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_result(plan), _result(orbs), _result(alerts)])
    monkeypatch.setattr(reports.settings, "report_output_dir", str(tmp_path))

    path = await reports.generate_completion_report("PLN-2026-003", session)

    assert path.exists()
    assert path.suffix == ".pdf"
    assert path.read_bytes().startswith(b"%PDF")
