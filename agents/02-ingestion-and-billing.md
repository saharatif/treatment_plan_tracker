# Module 2 — Ingestion & Billing

**Build phases covered:** 3 (Ingestion), 4 (Billing)

**Goal:** Turn an uploaded "processing" PDF into validated structured orb data, then price its
billing codes, email a quotation to billing, and log it — before anything is persisted by
Module 1's `store_plan()`/`enroll()`.

**Depends on:** Module 1 (`store_plan`, `enroll`, the `app.orbs` catalog (30 entries / 8
categories), `billing.billing_codes` seed data covering the full ICD-10-CM / CPT / HCPCS
reference set, ID generators).

---

## 1. AI Layer

This project's chosen stack is **Mistral OCR + OpenAI GPT-4o** (the "paid" row below). See
[`../docs/HIPAA.md` §3](../docs/HIPAA.md#3-ai-vendor--business-associate-agreements-164308b) for
the BAA implications of that choice — both vendors touch the redacted `_processing.pdf` and must
be covered by a BAA before any real PHI is ingested.

| Need | Paid (production, **chosen**) | Free (prototype / offline dev) |
|------|-------------------------------|---------------------------------|
| OCR | Mistral OCR | Tesseract / docTR |
| Parsing | OpenAI GPT-4o | Ollama + Llama 3.1 8B |

> For the system's own clean, digital-text PDFs the free stack is sufficient. Paid APIs become
> necessary only for scanned or handwritten real-world documents, but Mistral OCR + OpenAI
> GPT-4o is the stack this project runs against.

Configure both via `config.py` env vars (`MISTRAL_API_KEY`, `OPENAI_API_KEY`) so the free
variant can be swapped in without code changes (see Step 8).

---

## 2. Implementation Steps

### Step 1 — Repository pieces for this module

```
backend/app/
├── routers/
│   ├── ingest.py
│   └── billing.py
└── services/
    ├── ocr.py            # Mistral / Tesseract
    ├── parser.py         # GPT-4o / Ollama orb extraction
    ├── validation.py      # validation gate
    └── billing.py         # quotation build + email
```

### Step 2 — Stage 2: OCR extraction (`services/ocr.py`)

```python
async def extract_pdf_text(pdf_path: str, mistral_key: str) -> str:
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()
    resp = await client.post(
        "https://api.mistral.ai/v1/ocr",
        headers={"Authorization": f"Bearer {mistral_key}"},
        json={"model": "mistral-ocr-latest",
              "document": {"type": "document_url",
                           "document_url": f"data:application/pdf;base64,{pdf_b64}"}},
        timeout=60)
    return "\n".join(p["markdown"] for p in resp.json()["pages"])
```

The free variant (Tesseract / docTR) should expose the same `extract_pdf_text(pdf_path) -> str`
signature so `ingest.py` doesn't need branching logic beyond config.

### Step 3 — LLM parsing (`services/parser.py`)

Structured JSON output extraction of the 10 orbs, patient IDs, diagnoses, and plan dates:

```python
async def extract_orbs_from_text(ocr_text: str) -> dict:
    resp = await openai.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": ORB_PARSER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract orbs:\n\n{ocr_text}"}
        ])
    return json.loads(resp.choices[0].message.content)
```

Write `ORB_PARSER_SYSTEM_PROMPT` so it requests exactly the JSON shape `validate_parsed_plan`
(Step 4) expects: `plan_id`, `patient_id`, `plan_start`, `provider`, `next_visit`, `diagnoses`,
and `orbs` (list of 10, each with `orb_number`, `title`, `category`, `target_date`, billing codes).
Include the `app.orbs` catalog (Module 1, Step 4) as few-shot examples in the prompt — it gives
the parser concrete title/category/code combinations per category, which improves both
extraction accuracy and `match_catalog_orb()`'s downstream matching during enrollment.

For the free variant, point this at a local Ollama server (`http://localhost:11434`) running
`llama3.1:8b`, with the same `response_format`-style JSON contract.

### Step 4 — Validation gate (`services/validation.py`)

A parsed plan must pass all checks or route to a **human review queue** — never auto-saved.

```python
def validate_parsed_plan(plan: dict) -> tuple[bool, list[str]]:
    errors = []
    if len(plan.get("orbs", [])) != 10:
        errors.append(f"Expected 10 orbs, found {len(plan.get('orbs', []))}")
    numbers = sorted(o["orb_number"] for o in plan.get("orbs", []))
    if numbers != list(range(1, 11)):
        errors.append(f"Orb numbers not 1-10: {numbers}")
    for field in ("plan_id", "patient_id", "plan_start"):
        if not plan.get(field):
            errors.append(f"Missing required field: {field}")
    return (len(errors) == 0, errors)
```

> **Rule:** if validation fails, the plan goes to a review queue. It is never auto-saved.

**Output of Stage 2:** validated structured plan (patient IDs, diagnoses, 10 orbs with codes).

### Step 5 — Stage 2.5: Billing quotation (`services/billing.py`)

Before any data is stored, billing codes are priced and a quotation is emailed to the billing
department: **collect codes → price them → build quote → email → log.**

```python
async def build_quotation(plan: dict, db) -> dict:
    codes = collect_billing_codes(plan)              # diagnoses + orb codes
    rows  = await db.fetch(
        "SELECT * FROM billing.billing_codes WHERE code = ANY($1)",
        [c["code"] for c in codes])
    found = {r["code"]: dict(r) for r in rows}

    line_items, diagnoses, unmatched = [], [], []
    for c in codes:
        if c["code"] not in found:
            unmatched.append(c)                      # flag, never drop
        elif found[c["code"]]["is_billable"]:
            line_items.append(found[c["code"]] | {"source": c["source"]})
        else:
            diagnoses.append(found[c["code"]])

    return {
        "quote_id":   f"QTE-{date.today():%Y}-{plan['plan_id'][-3:]}",
        "plan_id":    plan["plan_id"],
        "patient_id": plan["patient_id"],            # token only — no PII
        "line_items": line_items,
        "diagnoses":  diagnoses,
        "unmatched":  unmatched,
        "needs_auth": [i for i in line_items if i["requires_auth"]],
        "total":      float(sum(i["unit_price"] for i in line_items)),
    }
```

**Email contains the token only** — never patient name or DOB (email is the least secure
channel). Billing staff resolve identity via vault lookup (Module 1's `vault.py`) with access
logging.

**Example quote email:**

```
Subject: Quotation QTE-2025-003 — Plan PLN-2025-003 — $330.00

  83036   CPT     HbA1c Test                       $  45.00
  80053   CPT     Comprehensive Metabolic Panel    $  62.00
  99214   CPT     Office Visit, Moderate           $ 185.00
  A4253   HCPCS   Blood Glucose Test Strips        $  38.00
  ----------------------------------------------------------
  ESTIMATED TOTAL                                  $ 330.00
```

Persist the quote to `billing.quotation_log` (full payload as JSONB) and send via the SMTP
mailer configured in `config.py` (`SMTP_HOST`).

**Output:** quotation emailed + logged to `billing.quotation_log`. Plan may pause in
`pending_enrollment` until billing confirms.

### Step 6 — Routers

- **`POST /api/ingest`** — orchestrates: upload processing PDF → `ocr.py` → `parser.py` →
  `validation.py` (route to review queue on failure) → `billing.build_quotation` →
  Module 1's `store_plan` → set plan status to `pending_enrollment`.
- **`POST /api/plans/{plan_id}/confirm-billing`** — billing confirms quote → triggers
  Module 1's `enroll()`, transitioning the plan to `active`.
- **`GET /api/quotations`** — billing view over `billing.quotation_log`.

### Step 7 — Billing channel safety (carry into implementation)

- Quotation emails contain the **token only**, never name/DOB — email is the least secure hop.
- Unmatched billing codes are **flagged**, never dropped (could indicate OCR error or table gap).
- Prior-authorization items (`needs_auth`) are surfaced early — the top cause of late claim
  denials.

### Step 8 — Fully free AI variant (optional, for local dev)

```bash
# Swap Mistral OCR for Tesseract
apt-get install tesseract-ocr
pip install pytesseract pdf2image

# Swap GPT-4o for local Ollama
ollama pull llama3.1:8b
# parser.py points to http://localhost:11434
```

---

## 3. Deliverable

- `POST /api/ingest` accepts a processing PDF and returns either a stored, `pending_enrollment`
  plan with a quotation emailed/logged, or a review-queue entry with validation errors.
- `billing.quotation_log` contains the full quote snapshot; unmatched/needs-auth codes are
  visible in the response.
- `POST /api/plans/{plan_id}/confirm-billing` hands off to Module 1's enrollment, making the
  plan ready for Module 3 (tracking).
