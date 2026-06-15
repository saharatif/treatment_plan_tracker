"""Extracts structured treatment-plan data (10 orbs + diagnoses) from OCR text.

Three backends are supported, tried in order of preference based on config:
OpenAI / Ollama (LLM-based, given ORB_PARSER_SYSTEM_PROMPT), or a regex-based
local fallback (extract_orbs_local) for clean synthetic PDFs when no AI
provider is configured.
"""

import json
import re
from datetime import date
from typing import Any

import httpx

from app.config import settings
from app.seed_data import ICD10_CODES, ORB_CATALOG

CATALOG_EXAMPLES = "\n".join(
    f"- {code}: {title} | {category} | codes: {', '.join(codes) or 'none'}"
    for code, title, category, codes in ORB_CATALOG
)

ORB_PARSER_SYSTEM_PROMPT = f"""
You extract structured treatment-plan data from redacted processing PDFs.
Return only valid JSON with this exact shape:
{{
  "plan_id": "PLN-2026-003",
  "patient_id": "PAT-2026-00847",
  "provider": "Dr. Example",
  "plan_start": "YYYY-MM-DD",
  "next_visit": "YYYY-MM-DD or null",
  "diagnoses": [{{"code": "E11.9", "description": "...", "code_system": "ICD-10"}}],
  "orbs": [
    {{
      "orb_number": 1,
      "title": "Blood Work - Baseline Labs",
      "category": "Lab",
      "target_date": "YYYY-MM-DD or null",
      "billing_codes": ["83036", "80053"],
      "catalog_code": "LAB-01 or null"
    }}
  ]
}}
Rules:
- Extract exactly 10 orbs numbered 1 through 10.
- Use ISO dates.
- Billing codes must be bare codes without prefixes, e.g. "83036", "E11.9", "A4253".
- Use null for unknown optional values.
- Never invent patient names, DOBs, addresses, phone numbers, or emails.

Catalog examples:
{CATALOG_EXAMPLES}
""".strip()


async def extract_orbs_from_text(ocr_text: str) -> dict[str, Any]:
    provider = settings.ai_parser_provider.lower()
    if provider == "openai" and settings.openai_api_key:
        return await extract_orbs_openai(ocr_text)
    if provider == "ollama":
        return await extract_orbs_ollama(ocr_text)
    # No AI provider configured (or OpenAI selected without a key) - fall back to
    # regex extraction, which only works for the synthetic PDF format.
    return extract_orbs_local(ocr_text)


async def extract_orbs_openai(ocr_text: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": "gpt-4o",
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": ORB_PARSER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract orbs:\n\n{ocr_text}"},
                ],
            },
        )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


async def extract_orbs_ollama(ocr_text: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": "llama3.1:8b",
                "format": "json",
                "stream": False,
                "messages": [
                    {"role": "system", "content": ORB_PARSER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Extract orbs:\n\n{ocr_text}"},
                ],
            },
        )
    response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


def extract_orbs_local(ocr_text: str) -> dict[str, Any]:
    """Best-effort parser for clean synthetic PDFs while cloud AI is not configured."""
    plan = {
        "plan_id": _first_match(r"Plan ID:\s*(PLN-\d{4}-\d{3,})", ocr_text),
        "patient_id": _first_match(r"Patient ID:\s*(PAT-\d{4}-\d{5,})", ocr_text),
        "provider": _first_match(r"(?:Provider|Clinician|Physician):\s*([^\n]+)", ocr_text),
        "plan_start": _first_iso_or_us_date(ocr_text),
        "next_visit": _date_after_label("Next appointment", ocr_text) or _date_after_label("Next visit", ocr_text),
        "diagnoses": _extract_diagnoses(ocr_text),
        "orbs": _extract_orbs(ocr_text),
    }
    return plan


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _first_iso_or_us_date(text: str) -> str | None:
    return _normalize_date(_first_match(r"\b(\d{4}-\d{2}-\d{2})\b", text) or _first_match(r"\b([A-Z][a-z]+ \d{1,2}, \d{4})\b", text))


def _date_after_label(label: str, text: str) -> str | None:
    match = re.search(rf"{label}:\s*([A-Z][a-z]+ \d{{1,2}}, \d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})", text, re.IGNORECASE)
    return _normalize_date(match.group(1)) if match else None


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    try:
        from datetime import datetime

        return datetime.strptime(value, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def _extract_diagnoses(text: str) -> list[dict[str, str]]:
    # Only codes present in our known ICD-10 catalog are kept, which both filters out
    # false-positive matches and excludes non-ICD codes (CPT/HCPCS) the regex might
    # also match.
    known_icd10 = {code for code, _ in ICD10_CODES}
    codes = sorted(set(re.findall(r"\b([A-Z]\d{2}(?:\.\d+)?(?:[A-Z])?)\b", text)) & known_icd10)
    return [
        {"code": code, "description": "", "code_system": "ICD-10"}
        for code in codes
        if not code.startswith(("CPT", "HCPCS"))
    ]


def _extract_orbs(text: str) -> list[dict[str, Any]]:
    # Splitting on "Orb N" headers turns the document into alternating
    # [pre-text, number, body, number, body, ...] chunks - odd indices are the
    # captured orb numbers, the following even index is that orb's body text.
    chunks = re.split(r"\bOrb\s+(\d{1,2})\b", text, flags=re.IGNORECASE)
    orbs: list[dict[str, Any]] = []
    for index in range(1, len(chunks), 2):
        number = int(chunks[index])
        body = chunks[index + 1]
        if not 1 <= number <= 10:
            continue
        title = _extract_title(body)
        catalog_code = _first_match(r"\b((?:LAB|MED|VIT|EXR|MON|DIE|REF|REV)-\d{2})\b", body)
        orbs.append(
            {
                "orb_number": number,
                "title": title,
                "category": _category_for_catalog_code(catalog_code),
                "target_date": _date_after_label("Target Date", body),
                "billing_codes": _extract_codes(body),
                "catalog_code": catalog_code,
            }
        )
    return sorted(orbs, key=lambda orb: orb["orb_number"])


def _extract_title(body: str) -> str:
    for line in body.splitlines():
        clean = line.strip(" :-")
        if clean and not clean.lower().startswith(("target date", "catalog", "code")):
            return clean
    return "Untitled Orb"


def _category_for_catalog_code(catalog_code: str | None) -> str | None:
    if not catalog_code:
        return None
    for code, _, category, _ in ORB_CATALOG:
        if code == catalog_code:
            return category
    return None


def _extract_codes(text: str) -> list[str]:
    # Codes are only picked up when explicitly labeled "CPT:"/"HCPCS:"/"ICD-10:" in the
    # source text, so this won't match codes mentioned in free-form notes.
    cpt_hcpcs = re.findall(r"\b(?:CPT|HCPCS):\s*([A-Z]?\d{4,5}(?:,\s*[A-Z]?\d{4,5})*)", text, flags=re.IGNORECASE)
    codes: set[str] = set()
    for group in cpt_hcpcs:
        codes.update(code.strip().upper() for code in group.split(","))
    icd_groups = re.findall(
        r"\bICD-10:\s*([A-Z]\d{2}(?:\.\d+)?(?:[A-Z])?(?:,\s*[A-Z]\d{2}(?:\.\d+)?(?:[A-Z])?)*)",
        text,
        flags=re.IGNORECASE,
    )
    for group in icd_groups:
        codes.update(code.strip().upper() for code in group.split(","))
    return sorted(codes)
