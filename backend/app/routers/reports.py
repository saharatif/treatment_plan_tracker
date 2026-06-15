"""Serves the per-plan completion report PDF, generating it on first request
if it doesn't already exist on disk (see app/services/reports.py)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_roles
from app.database import get_session
from app.services.reports import get_or_create_completion_report

router = APIRouter(prefix="/api", tags=["reports"])


@router.get(
    "/plans/{plan_id}/report",
    dependencies=[Depends(require_roles("clinician", "coordinator", "billing"))],
)
async def completion_report(plan_id: str, session: AsyncSession = Depends(get_session)) -> FileResponse:
    try:
        report_path = await get_or_create_completion_report(plan_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=report_path.name,
    )
