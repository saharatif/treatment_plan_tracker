"""Endpoints for updating an individual orb's status (complete/in_progress/skipped).

Clinicians and coordinators can update any orb; patients may only update
orbs on their own plan (enforced in _authorize_orb_mutation).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User, get_current_user
from app.database import get_session
from app.services.orbs import complete_orb, get_orb_context, set_orb_status

router = APIRouter(prefix="/api/orbs", tags=["orbs"])


class OrbStatusRequest(BaseModel):
    status: Literal["pending", "in_progress", "skipped"]
    notes: str | None = None


class CompleteOrbRequest(BaseModel):
    notes: str | None = None


@router.post("/{orb_ref}/complete")
async def mark_complete(
    orb_ref: str,
    payload: CompleteOrbRequest | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    try:
        await _authorize_orb_mutation(orb_ref, user, session)
        await complete_orb(orb_ref, session, notes=payload.notes if payload else None)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409 if "closed" in str(exc) else 404, detail=str(exc)) from exc
    return {"orb_ref": orb_ref, "status": "complete"}


@router.post("/{orb_ref}/status")
async def update_status(
    orb_ref: str,
    payload: OrbStatusRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    try:
        await _authorize_orb_mutation(orb_ref, user, session)
        await set_orb_status(orb_ref, payload.status, session, notes=payload.notes)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409 if "closed" in str(exc) else 404, detail=str(exc)) from exc
    return {"orb_ref": orb_ref, "status": payload.status}


async def _authorize_orb_mutation(orb_ref: str, user: User, session: AsyncSession) -> None:
    if user.role in {"clinician", "coordinator"}:
        return
    if user.role != "patient":
        raise HTTPException(status_code=403, detail="Insufficient role")
    # Patient role: look up which patient owns this orb and confirm it matches
    # the patient_id on the caller's token.
    context = await get_orb_context(orb_ref, session)
    if context is None:
        raise ValueError("Orb not found")
    if context["patient_id"] != user.patient_id:
        raise HTTPException(status_code=403, detail="Patient token scope mismatch")
