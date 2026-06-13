import json
import os
import shutil
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_roles
from app.database import get_session
from app.services.billing import quote_email_and_log
from app.services.ocr import extract_pdf_text
from app.services.parser import extract_orbs_from_text
from app.services.storage import store_plan
from app.services.validation import validate_parsed_plan

router = APIRouter(prefix="/api", tags=["ingestion"])

REVIEW_QUEUE: dict[str, dict[str, Any]] = {}


@router.post("/ingest", dependencies=[Depends(require_roles("clinician", "coordinator"))])
async def ingest_processing_pdf(
    file: UploadFile = File(...),
    pii_json: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    pdf_path = await _save_upload(file)
    try:
        ocr_text = await extract_pdf_text(pdf_path)
        parsed_plan = await extract_orbs_from_text(ocr_text)
    finally:
        os.unlink(pdf_path)

    is_valid, errors = validate_parsed_plan(parsed_plan)
    if not is_valid:
        review_id = _enqueue_review(file.filename or "processing.pdf", parsed_plan, errors)
        return {
            "status": "review_required",
            "review_id": review_id,
            "errors": errors,
        }

    parsed_plan["status"] = "pending_enrollment"
    pii = _parse_optional_json(pii_json)
    patient_id = await store_plan(parsed_plan, pii, session)
    parsed_plan["patient_id"] = patient_id
    quote = await quote_email_and_log(parsed_plan, session)
    await session.commit()

    return {
        "status": "pending_enrollment",
        "plan_id": parsed_plan["plan_id"],
        "patient_id": patient_id,
        "quote": quote,
    }


async def _save_upload(file: UploadFile) -> str:
    suffix = ".pdf"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        return tmp.name


def _parse_optional_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="pii_json must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="pii_json must be a JSON object")
    return parsed


def _enqueue_review(filename: str, parsed_plan: dict[str, Any], errors: list[str]) -> str:
    review_id = f"REVQ-{uuid4().hex[:12]}"
    REVIEW_QUEUE[review_id] = {
        "review_id": review_id,
        "filename": filename,
        "parsed_plan": parsed_plan,
        "errors": errors,
    }
    return review_id
