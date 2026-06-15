"""PDF text extraction for the ingestion pipeline.

Uses Mistral's cloud OCR when configured (AI_OCR_PROVIDER=mistral and a key is
set), otherwise falls back to local text extraction with pypdf - sufficient
for clean, digitally-generated synthetic PDFs used in development.
"""

import base64
from pathlib import Path

import httpx
from pypdf import PdfReader

from app.config import settings


async def extract_pdf_text(pdf_path: str, mistral_key: str | None = None) -> str:
    """Extract text from a processing PDF using the configured OCR path.

    Cloud OCR is used only when the provider is Mistral and a key is present. Otherwise
    clean digital PDFs are parsed locally, which is enough for synthetic development files.
    """
    key = mistral_key if mistral_key is not None else settings.mistral_api_key
    if settings.ai_ocr_provider.lower() == "mistral" and key:
        return await extract_pdf_text_mistral(pdf_path, key)
    return extract_pdf_text_local(pdf_path)


async def extract_pdf_text_mistral(pdf_path: str, mistral_key: str) -> str:
    pdf_b64 = base64.b64encode(Path(pdf_path).read_bytes()).decode()
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.mistral.ai/v1/ocr",
            headers={"Authorization": f"Bearer {mistral_key}"},
            json={
                "model": "mistral-ocr-latest",
                "document": {
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{pdf_b64}",
                },
            },
        )
    response.raise_for_status()
    pages = response.json().get("pages", [])
    return "\n".join(page.get("markdown", "") for page in pages).strip()


def extract_pdf_text_local(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
