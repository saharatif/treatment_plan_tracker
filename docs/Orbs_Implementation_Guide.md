# 10 Orbs to Better — Implementation Guide

**A treatment-plan tracking system: from PDF ingestion to plan closure.**

Version 1.0 · MVP Architecture · Open-Source Stack

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Data Model](#4-data-model)
5. [The Six Stages](#5-the-six-stages)
   - [Stage 1 — Plan Creation](#stage-1--plan-creation)
   - [Stage 2 — Ingestion](#stage-2--ingestion)
   - [Stage 2.5 — Billing Quotation](#stage-25--billing-quotation)
   - [Stage 3 — Tokenization & Storage](#stage-3--tokenization--storage)
   - [Stage 4 — Enrollment](#stage-4--enrollment)
   - [Stage 5 — Live Tracking](#stage-5--live-tracking)
   - [Stage 6 — Closure](#stage-6--closure)
6. [The Checkpoint State Machine](#6-the-checkpoint-state-machine)
7. [Security & Compliance](#7-security--compliance)
8. [API Reference](#8-api-reference)
9. [Repository Structure](#9-repository-structure)
10. [Deployment](#10-deployment)
11. [Build Sequence](#11-build-sequence)

---

## 1. Overview

The system tracks structured treatment plans where each plan contains exactly **10 "orbs"** — discrete tasks a patient must complete within a prescribed window before their next clinical visit. A plan moves through six stages, beginning as a PDF generated at a doctor visit and ending in a closed, reported state.

### Core Concepts

| Term | Meaning |
|------|---------|
| **Orb** | A single trackable treatment task (e.g. "complete blood work", "begin Metformin"). Each plan has 10. |
| **Plan** | A two-week (configurable) program of 10 orbs with a target date and a hard-stop date. |
| **Checkpoint** | A scheduled evaluation point that fires alerts and changes plan state based on orb completion. |
| **Vault** | An encrypted store holding patient PII, separated from all treatment data. |
| **Token** | A non-identifying reference (`PAT-2025-00847`) used everywhere instead of PII. |
| **Quotation** | A billing estimate generated from the plan's procedure codes, emailed to the billing department. |

### Design Principles

- **PII isolation** — patient identity lives only in the encrypted vault; every document, email, and dashboard uses tokens.
- **Human-in-the-loop** — ingestion failures and validation gaps route to a review queue, never auto-save.
- **Audit everything** — every quotation, every status change, every vault access is logged.
- **Fail safe** — unmatched billing codes are flagged, never silently dropped; orbs lock at hard stop.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────┐
│  FRONTEND — React + Vite SPA                             │
│  TanStack Query polls /api/dashboard every 30s           │
│  Clinic dashboard · Patient detail · PDF upload          │
└────────────────────────┬─────────────────────────────────┘
                         │ REST + JWT
┌────────────────────────▼─────────────────────────────────┐
│  BACKEND — FastAPI (single container)                    │
│                                                          │
│  Routers:    /patients  /orbs  /dashboard  /ingest       │
│  Services:   ocr · parser · billing · checkpoints · vault│
│  Scheduler:  APScheduler — daily 08:00 checkpoint cron   │
│  Mailer:     SMTP client — billing quotation emails      │
└──────┬──────────────────────────────────┬────────────────┘
       │                                  │
┌──────▼──────────────────┐    ┌──────────▼──────────────────┐
│  PostgreSQL 16          │    │  External AI APIs            │
│                         │    │                              │
│  schema: app            │    │  Mistral OCR   (or Tesseract)│
│  schema: billing        │    │  OpenAI GPT-4o (or Ollama)   │
│  schema: vault (pgcrypto)│   │                              │
└─────────────────────────┘    └──────────────────────────────┘
```

### Request Flow Summary

```
PDF → OCR → Parse → Quotation → Email Billing
    → Tokenize → Store → Enroll → Track (daily cron) → Close → Report
```

---

## 3. Technology Stack

### Backend

| Component | Choice | Purpose |
|-----------|--------|---------|
| API framework | **FastAPI** | Async REST API, auto OpenAPI docs |
| ORM | **SQLAlchemy 2.0** | Async database models |
| DB driver | **asyncpg** | PostgreSQL async driver |
| Migrations | **Alembic** | Schema version control |
| Scheduler | **APScheduler** | In-process daily checkpoint cron |
| Auth | **python-jose** | JWT token issuance and validation |
| Validation | **Pydantic v2** | Request/response + LLM structured output |
| Encryption | **pgcrypto** (Postgres ext.) | AES-256 PII encryption |

### Frontend

| Component | Choice | Purpose |
|-----------|--------|---------|
| Framework | **React 18** | Component UI |
| Build tool | **Vite** | Dev server + production build |
| Data fetching | **TanStack Query** | Polling, caching, auto-refetch |
| Styling | **Tailwind CSS** | Utility-first styling |
| Components | **shadcn/ui** | Cards, badges, progress bars |
| Charts | **Recharts** | Completion trends (later) |

### AI Layer

| Need | Paid (production) | Free (prototype) |
|------|-------------------|------------------|
| OCR | Mistral OCR | Tesseract / docTR |
| Parsing | OpenAI GPT-4o | Ollama + Llama 3.1 8B |

> For the system's own clean, digital-text PDFs the free stack is sufficient. Paid APIs become necessary only for scanned or handwritten real-world documents.

### Infrastructure

- **Docker Compose** — three services: `frontend`, `backend`, `db`
- Runs on any small VPS or cloud free tier
- All components are MIT/BSD/Apache licensed

---

## 4. Data Model

Three PostgreSQL schemas keep concerns separated.

### Schema: `vault` (encrypted PII — isolated)

```sql
CREATE SCHEMA vault;

CREATE TABLE vault.patient_vault (
    patient_id        VARCHAR(20) PRIMARY KEY,   -- PAT-2025-00847
    token             VARCHAR(50) UNIQUE,         -- tok_mje_8f3a2c
    name_encrypted    BYTEA,                      -- pgp_sym_encrypt
    dob_encrypted     BYTEA,
    address_encrypted BYTEA,
    phone_encrypted   BYTEA,
    email_encrypted   BYTEA,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    access_log        JSONB DEFAULT '[]'          -- who read it, when
);
```

### Schema: `app` (treatment data — no PII)

```sql
CREATE SCHEMA app;

CREATE TABLE app.treatment_plans (
    plan_id        VARCHAR(20) PRIMARY KEY,       -- PLN-2025-003
    patient_id     VARCHAR(20) NOT NULL,          -- FK to vault (token only)
    provider       VARCHAR(200),
    plan_start     DATE NOT NULL,
    duration_days  INT  NOT NULL DEFAULT 14,
    buffer_days    INT  NOT NULL DEFAULT 3,
    extension_days INT  NOT NULL DEFAULT 7,
    target_date    DATE NOT NULL,                 -- start + duration
    hard_stop      DATE NOT NULL,                 -- target + extension
    next_visit     DATE,
    status         VARCHAR(20) DEFAULT 'active',  -- state machine
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE app.diagnoses (
    id           SERIAL PRIMARY KEY,
    plan_id      VARCHAR(20) REFERENCES app.treatment_plans(plan_id),
    code         VARCHAR(20),                      -- E11.9
    description  TEXT,
    code_system  VARCHAR(20)                       -- ICD-10
);

CREATE TABLE app.orbs (
    id            SERIAL PRIMARY KEY,
    catalog_code  VARCHAR(20) UNIQUE NOT NULL,      -- e.g. LAB-01, MED-03
    title         VARCHAR(200) NOT NULL,
    category      VARCHAR(100) NOT NULL,            -- Lab, Medicine, Vitamins, Exercise,
                                                      -- Monitoring, Diet, Referral, Review
    description   TEXT,
    billing_codes VARCHAR(20)[]                      -- associated CPT/ICD-10/HCPCS codes
);

CREATE TABLE app.patient_orbs (
    orb_ref        VARCHAR(30) PRIMARY KEY,         -- ORB-PAT00847-001
    plan_id        VARCHAR(20) REFERENCES app.treatment_plans(plan_id),
    patient_id     VARCHAR(20) NOT NULL,
    orb_number     INT NOT NULL,                    -- 1..10, this plan's slot position
    catalog_orb_id INT REFERENCES app.orbs(id),     -- which catalog orb fills this slot
    status         VARCHAR(20) DEFAULT 'pending',   -- pending|in_progress|complete|skipped|locked
    target_date    DATE,
    completed_at   TIMESTAMPTZ,
    notes          TEXT,
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (plan_id, orb_number)
);

CREATE TABLE app.alert_log (
    id           SERIAL PRIMARY KEY,
    plan_id      VARCHAR(20),
    recipient    VARCHAR(20),                      -- 'patient' | 'clinic'
    checkpoint   VARCHAR(20),                      -- checkpoint_1 ... 4
    message      TEXT,
    sent_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Schema: `billing`

```sql
CREATE SCHEMA billing;

CREATE TABLE billing.billing_codes (
    id            SERIAL PRIMARY KEY,
    code          VARCHAR(20) UNIQUE NOT NULL,
    code_system   VARCHAR(20) NOT NULL,            -- CPT|ICD-10|HCPCS
    description   TEXT NOT NULL,
    unit_price    NUMERIC(10,2),
    medicare_rate NUMERIC(10,2),
    is_billable   BOOLEAN DEFAULT TRUE,            -- ICD-10 = FALSE
    requires_auth BOOLEAN DEFAULT FALSE,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE billing.quotation_log (
    quote_id     VARCHAR(20) PRIMARY KEY,          -- QTE-2025-003
    plan_id      VARCHAR(20),
    total        NUMERIC(10,2),
    sent_to      VARCHAR(200),
    sent_at      TIMESTAMPTZ DEFAULT NOW(),
    payload      JSONB                             -- full quote snapshot
);
```

---

## 5. The Six Stages

### Stage 1 — Plan Creation

A treatment plan PDF is generated at the doctor visit. **Two versions** are produced:

| Version | Contents | Storage |
|---------|----------|---------|
| `PLN-2025-003_clinical.pdf` | Full PII | Locked S3 bucket (Object Lock), clinician access only |
| `PLN-2025-003_processing.pdf` | Redacted — IDs only | Pipeline-safe, standard storage |

The **processing PDF** is the only version that enters the automated pipeline. It carries:

```
Patient ID:  PAT-2025-00847      Plan ID:  PLN-2025-003
Patient Name: [REDACTED]
Each orb header:  Orb 1: Blood Work ... ORB-PAT00847-001
```

**Inputs:** patient PII, diagnoses, the 10 orb definitions, plan dates.
**Output:** two PDFs + initial records ready for ingestion.

---

### Stage 2 — Ingestion

The processing PDF is converted to structured data.

```
PDF → Mistral OCR → markdown text → GPT-4o parser → JSON → validation gate
```

**OCR extraction:**

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

**LLM parsing** (structured JSON output):

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

**Validation gate** — a parsed plan must pass all checks or route to human review:

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

**Output:** validated structured plan (patient IDs, diagnoses, 10 orbs with codes).

---

### Stage 2.5 — Billing Quotation

Before any data is stored, billing codes are priced and a quotation is emailed to the billing department.

**Collect codes → price them → build quote → email → log.**

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

**Email contains the token only** — never patient name or DOB (email is the least secure channel). Billing staff resolve identity via vault lookup with access logging.

**Example quote:**

```
Subject: Quotation QTE-2025-003 — Plan PLN-2025-003 — $330.00

  83036   CPT     HbA1c Test                       $  45.00
  80053   CPT     Comprehensive Metabolic Panel    $  62.00
  99214   CPT     Office Visit, Moderate           $ 185.00
  A4253   HCPCS   Blood Glucose Test Strips        $  38.00
  ----------------------------------------------------------
  ESTIMATED TOTAL                                  $ 330.00
```

**Output:** quotation emailed + logged to `billing.quotation_log`. Plan may pause in `pending_enrollment` until billing confirms.

---

### Stage 3 — Tokenization & Storage

PII is encrypted into the vault; everything else is stored with tokens only.

```python
async def store_plan(plan: dict, pii: dict, db) -> str:
    patient_id = generate_patient_id()              # PAT-2025-00847
    token      = generate_token(pii["name"], pii["dob"])

    # PII → encrypted vault
    await db.execute("""
        INSERT INTO vault.patient_vault
          (patient_id, token, name_encrypted, dob_encrypted, address_encrypted)
        VALUES ($1, $2,
                pgp_sym_encrypt($3, $6),
                pgp_sym_encrypt($4, $6),
                pgp_sym_encrypt($5, $6))
    """, patient_id, token, pii["name"], pii["dob"], pii["address"], KMS_KEY)

    # Plan → app schema (no PII)
    await db.execute("""
        INSERT INTO app.treatment_plans
          (plan_id, patient_id, provider, plan_start,
           duration_days, buffer_days, extension_days,
           target_date, hard_stop, next_visit)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
    """, plan["plan_id"], patient_id, plan["provider"], plan["plan_start"],
         14, 3, 7, plan["target_date"], plan["hard_stop"], plan["next_visit"])

    return patient_id
```

**ID generators:**

```python
def generate_patient_id() -> str:
    return f"PAT-{datetime.now().year}-{secrets.randbelow(99999):05d}"

def generate_orb_ref(patient_id: str, orb_number: int) -> str:
    return f"ORB-PAT{patient_id.split('-')[-1]}-{orb_number:03d}"

def generate_token(name: str, dob: str) -> str:
    raw = f"{name.lower().strip()}:{dob}"
    return "tok_" + hashlib.sha256(raw.encode()).hexdigest()[:12]
```

**Output:** PII in vault, plan + diagnoses in `app`, ready to enroll.

---

### Stage 4 — Enrollment

The timeline is computed and 10 orb tracking rows are created.

```python
async def enroll(plan_id: str, patient_id: str, parsed_orbs: list, db):
    plan = await db.fetchrow(
        "SELECT * FROM app.treatment_plans WHERE plan_id = $1", plan_id)

    for orb in parsed_orbs:
        orb_ref = generate_orb_ref(patient_id, orb["orb_number"])
        catalog_orb_id = await match_catalog_orb(orb, db)   # best match from app.orbs, or NULL
        await db.execute("""
            INSERT INTO app.patient_orbs
              (orb_ref, plan_id, patient_id, orb_number, catalog_orb_id, status, target_date)
            VALUES ($1, $2, $3, $4, $5, 'pending', $6)
        """, orb_ref, plan_id, patient_id, orb["orb_number"], catalog_orb_id, orb["target_date"])

    await notify_patient(plan_id, "Your 10 Orbs to Better plan starts today.")
```

**Computed timeline (14-day example, start June 13):**

| Marker | Day | Date |
|--------|-----|------|
| Plan start | 0 | Jun 13 |
| Checkpoint 1 | 11 | Jun 24 (`duration - buffer`) |
| Target date | 14 | Jun 27 (`duration`) |
| Checkpoint 3 | 18 | Jul 1 (`hard_stop - buffer`) |
| Hard stop | 21 | Jul 4 (`duration + extension`) |
| Next visit | — | Jul 8 |

**Output:** 10 `pending` orbs, status `active`, timeline set.

---

### Stage 5 — Live Tracking

Patients complete orbs; a daily cron evaluates checkpoints.

**Marking an orb complete:**

```python
async def complete_orb(orb_ref: str, db, notes: str = None):
    plan = await db.fetchrow(
        "SELECT plan_id, status FROM app.patient_orbs po "
        "JOIN app.treatment_plans tp USING (plan_id) WHERE orb_ref = $1", orb_ref)

    if plan["status"] == "closed":
        raise ValueError("Plan is closed — orbs are locked")

    await db.execute("""
        UPDATE app.patient_orbs
        SET status='complete', completed_at=NOW(), notes=$2, updated_at=NOW()
        WHERE orb_ref = $1
    """, orb_ref, notes)
```

**Dashboard query (all patients):**

```sql
SELECT
    tp.patient_id, tp.plan_id, tp.status,
    COUNT(*) FILTER (WHERE po.status='complete') AS completed,
    tp.target_date - CURRENT_DATE AS days_remaining,
    CASE
      WHEN CURRENT_DATE > tp.hard_stop  THEN 'OVERDUE'
      WHEN CURRENT_DATE > tp.target_date THEN 'IN GRACE'
      ELSE 'ON TRACK'
    END AS plan_status
FROM app.treatment_plans tp
JOIN app.patient_orbs po USING (plan_id)
GROUP BY tp.patient_id, tp.plan_id, tp.status, tp.target_date, tp.hard_stop
ORDER BY completed DESC;
```

**At-risk query (drives the alert panel):**

```sql
SELECT tp.patient_id,
       COUNT(*) FILTER (WHERE po.status='complete') AS completed,
       tp.target_date - CURRENT_DATE AS days_left
FROM app.treatment_plans tp
JOIN app.patient_orbs po USING (plan_id)
WHERE tp.status = 'active'
GROUP BY tp.patient_id, tp.target_date
HAVING COUNT(*) FILTER (WHERE po.status='complete') < 5
   AND tp.target_date - CURRENT_DATE <= 7;
```

**Output:** live progress visible on dashboard; checkpoints fire alerts and transition state (see Section 6).

---

### Stage 6 — Closure

At the hard stop, the plan closes regardless of completion.

```python
async def close_plan(plan_id: str, db):
    completed = await count_completed_orbs(plan_id, db)

    await db.execute(
        "UPDATE app.treatment_plans SET status='closed' WHERE plan_id=$1", plan_id)
    await db.execute("""
        UPDATE app.patient_orbs SET status='locked'
        WHERE plan_id=$1 AND status != 'complete'
    """, plan_id)

    await generate_completion_report(plan_id, completed, db)
    await notify_patient(plan_id, "Plan period ended. Your visit is mandatory.")
    await notify_clinic(plan_id,
        f"Plan closed. Final: {completed}/10 — flag for doctor review.")
```

**Completion report (PDF) includes:** final orb count, completed vs incomplete orbs, the full alert history, glucose log average, exercise days, medication adherence. It attaches to the patient record and is reviewed at the next visit — which begins a **new plan** (returning to Stage 1).

**Output:** plan `closed`, orbs locked, completion report generated.


---

## 6. The Checkpoint State Machine

A single daily cron (`08:00`) evaluates every active plan. State transitions happen only at defined checkpoints.

### Parameters

```
duration            = 14 days   (doctor-prescribed)
buffer              = 3 days    (early-warning window)
extension_duration  = 7 days    (grace period, always added)
hard_stop           = duration + extension = day 21
completion_threshold = 8 of 10 orbs
```

### State Diagram

```
              ┌──────────┐
   enroll →   │  ACTIVE  │  day 0–13
              └────┬─────┘
                   │
        day 11 ────┤  (checkpoint 1) if <8 orbs → warning alerts
                   │                  (status stays ACTIVE)
                   ▼  day 14 (target_date — checkpoint 2)
        ┌──────────┼──────────────┐
        ▼          ▼              ▼
     10/10       8–9            <8
  ┌──────────┐ ┌──────────┐  ┌──────────┐
  │COMPLETED │ │ IN_GRACE │  │ EXTENDED │
  └────┬─────┘ └────┬─────┘  └────┬─────┘
       │            │ +7 days     │ +7 days + outreach call
       │            └──────┬──────┘
       │       day 18 ─────┤ (checkpoint 3) if <10 → final warning
       │                   │                 + escalate coordinator
       │                   ▼  day 21 (hard_stop — checkpoint 4)
       │            ┌──────────────┐
       │            │   CLOSED     │  orbs locked, report generated
       │            └──────┬───────┘
       └───────────────────┤
                           ▼
              Completion report → next visit → new plan
```

### Checkpoint Rules

| Checkpoint | Day | Condition | Patient Alert | Clinic Alert | State |
|-----------|-----|-----------|---------------|--------------|-------|
| **1** | `duration - buffer` (11) | `< 8` orbs | "3 days left — complete your orbs" | "Completion jeopardized — possible extension" + next appt | stays ACTIVE |
| **2** | `duration` (14) | `== 10` | "Plan complete!" | "Completed — confirm visit" | **COMPLETED** |
| **2** | `duration` (14) | `8–9` | "Almost there — finish within 7 days" | "Grace period activated" | **IN_GRACE** |
| **2** | `duration` (14) | `< 8` | "Extension activated — 7 more days" | "Behind — extension granted, consider outreach" | **EXTENDED** |
| **3** | `hard_stop - buffer` (18) | `< 10` | "Final 3 days — hard deadline" | "Still incomplete — escalate to care coordinator" | unchanged |
| **4** | `hard_stop` (21) | any | "Plan ended — visit mandatory" | "Closed. Final count X/10 — flag for review" | **CLOSED** |

### Implementation

```python
from datetime import date, timedelta
from enum import Enum

class PlanStatus(str, Enum):
    ACTIVE    = "active"
    IN_GRACE  = "in_grace"
    EXTENDED  = "extended"
    COMPLETED = "completed"
    CLOSED    = "closed"

async def evaluate_plan_checkpoints(plan: dict, db):
    """Runs daily at 08:00 via APScheduler for every active plan."""
    today       = date.today()
    start       = plan["plan_start"]
    duration    = plan["duration_days"]
    buffer      = plan["buffer_days"]
    extension   = plan["extension_days"]
    target_date = start + timedelta(days=duration)
    hard_stop   = target_date + timedelta(days=extension)
    completed   = await count_completed_orbs(plan["plan_id"], db)

    # CHECKPOINT 1 — buffer before target
    if today == target_date - timedelta(days=buffer) and completed < 8:
        await alert_patient(plan, f"3 days left — {completed}/10 done.")
        await alert_clinic(plan,
            f"Completion jeopardized ({completed}/10). Next visit: {plan['next_visit']}")

    # CHECKPOINT 2 — target date
    elif today == target_date:
        if completed == 10:
            await set_status(plan, PlanStatus.COMPLETED, db)
            await alert_patient(plan, "All 10 orbs complete.")
            await alert_clinic(plan, "Patient completed on time.")
        elif completed >= 8:
            await set_status(plan, PlanStatus.IN_GRACE, db)
            await alert_patient(plan, f"{completed}/10 — finish within 7 days.")
            await alert_clinic(plan, f"Grace period active ({completed}/10).")
        else:
            await set_status(plan, PlanStatus.EXTENDED, db)
            await alert_patient(plan, "Extension activated — 7 more days.")
            await alert_clinic(plan, f"Behind ({completed}/10). Consider outreach.")

    # CHECKPOINT 3 — buffer before hard stop
    elif today == hard_stop - timedelta(days=buffer) and completed < 10:
        await alert_patient(plan, f"Final 3 days — hard deadline {hard_stop:%b %d}.")
        await alert_clinic(plan, f"Still incomplete ({completed}/10). Escalate.")

    # CHECKPOINT 4 — hard stop
    elif today >= hard_stop and plan["status"] != PlanStatus.CLOSED:
        await close_plan(plan["plan_id"], db)
```

### Open Design Questions

These were flagged during design and remain configurable:

1. **IN_GRACE vs EXTENDED** — currently distinct (8–9 = light touch, <8 = outreach call). Could merge into one EXTENDED state if the outreach distinction is not operationally useful.
2. **Grace-week completion scope** — should the patient be able to complete *any* orb during the grace week, or only the specific orbs flagged incomplete at day 14? Current default: any orb.

---

## 7. Security & Compliance

### PII Tokenization (core pattern)

- Patient identity lives **only** in `vault.patient_vault`, encrypted with `pgcrypto` (`pgp_sym_encrypt`) under a customer-managed KMS key.
- Every other table, document, email, and dashboard uses the **token** (`PAT-2025-00847`).
- Vault reads are logged to `access_log` — who accessed which record, when.

### Two-Document Strategy

| Document | PII | Where it goes |
|----------|-----|---------------|
| Clinical PDF | Yes | Locked storage, clinician-only, BAA-covered |
| Processing PDF | No (redacted) | OCR/LLM pipeline, standard storage |

### HIPAA Alignment

| Control | Implementation |
|---------|----------------|
| Encryption at rest | `pgcrypto` AES-256 on vault columns |
| Encryption in transit | TLS 1.3 on all API traffic |
| Access controls | JWT auth + role-based endpoints |
| Audit trail | `alert_log`, `quotation_log`, vault `access_log` |
| Minimum necessary | Tokens everywhere; PII fetched only on demand |
| BAA requirement | Required from any AI vendor touching PHI (OpenAI/Anthropic enterprise, AWS). The redacted processing PDF avoids sending PHI to the LLM entirely. |

### Billing Channel Safety

- Quotation emails contain the **token only**, never name/DOB — email is the least secure hop.
- Unmatched billing codes are **flagged**, never dropped (could indicate OCR error or table gap).
- Prior-authorization items are surfaced early (the top cause of late claim denials).

---

## 8. API Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/ingest` | Upload processing PDF → OCR → parse → quote → store |
| `GET` | `/api/dashboard` | All active plans with completion counts + status |
| `GET` | `/api/patients/{patient_id}` | Single plan detail with per-orb status |
| `POST` | `/api/orbs/{orb_ref}/complete` | Mark an orb complete |
| `POST` | `/api/orbs/{orb_ref}/status` | Set orb status (in_progress, skipped) |
| `GET` | `/api/at-risk` | Patients <5 orbs and ≤7 days remaining |
| `GET` | `/api/plans/{plan_id}/report` | Generate/fetch completion report |
| `POST` | `/api/plans/{plan_id}/confirm-billing` | Billing confirms quote → triggers enrollment |
| `GET` | `/api/quotations` | Quotation log (billing view) |

All endpoints require a JWT bearer token. FastAPI serves interactive docs at `/docs`.

---

## 9. Repository Structure

```
orbs-mvp/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                  # migrations
│   └── app/
│       ├── main.py               # FastAPI app + CORS + routers
│       ├── config.py             # env settings (Pydantic Settings)
│       ├── database.py           # async engine + session
│       ├── models.py             # SQLAlchemy models (3 schemas)
│       ├── schemas.py            # Pydantic request/response
│       ├── auth.py               # JWT issue/validate
│       ├── scheduler.py          # APScheduler 08:00 cron
│       ├── routers/
│       │   ├── ingest.py
│       │   ├── dashboard.py
│       │   ├── patients.py
│       │   ├── orbs.py
│       │   └── billing.py
│       └── services/
│           ├── ocr.py            # Mistral / Tesseract
│           ├── parser.py         # GPT-4o / Ollama orb extraction
│           ├── validation.py     # validation gate
│           ├── billing.py        # quotation build + email
│           ├── vault.py          # PII encrypt/decrypt + access log
│           ├── checkpoints.py    # state machine
│           ├── enrollment.py     # timeline + orb row creation
│           └── reports.py        # completion report PDF
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/
        │   └── client.ts         # TanStack Query hooks
        ├── pages/
        │   ├── Dashboard.tsx      # clinic dashboard
        │   ├── PatientDetail.tsx  # per-orb history
        │   └── Upload.tsx         # PDF ingest UI
        └── components/
            ├── OrbRow.tsx         # the 10-dot progress row
            ├── StatusBadge.tsx
            ├── MetricCard.tsx
            └── AlertPanel.tsx
```

---

## 10. Deployment

### docker-compose.yml

```yaml
version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: orbs
      POSTGRES_USER: orbs
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init:/docker-entrypoint-initdb.d   # CREATE EXTENSION pgcrypto
    ports: ["5432:5432"]

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://orbs:${DB_PASSWORD}@db/orbs
      KMS_KEY: ${KMS_KEY}
      MISTRAL_API_KEY: ${MISTRAL_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      SMTP_HOST: ${SMTP_HOST}
      JWT_SECRET: ${JWT_SECRET}
    depends_on: [db]
    ports: ["8000:8000"]

  frontend:
    build: ./frontend
    depends_on: [backend]
    ports: ["3000:80"]

volumes:
  pgdata:
```

### First-run commands

```bash
# 1. Enable pgcrypto (init script)
echo "CREATE EXTENSION IF NOT EXISTS pgcrypto;" > init/01-extensions.sql

# 2. Start everything
docker compose up -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. Seed the orb catalog (8 categories) + billing codes (ICD-10/CPT/HCPCS)
docker compose exec backend python -m app.seed

# App:  http://localhost:3000
# API docs: http://localhost:8000/docs
```

### Fully Free AI Variant

```bash
# Swap Mistral OCR for Tesseract
apt-get install tesseract-ocr
pip install pytesseract pdf2image

# Swap GPT-4o for local Ollama
ollama pull llama3.1:8b
# parser.py points to http://localhost:11434
```

---

## 11. Build Sequence

A suggested order to reach a working MVP:

| Phase | Deliverable | Components |
|-------|-------------|------------|
| **1. Foundations** | DB up, schemas migrated, seed data | PostgreSQL, Alembic, models, seed |
| **2. Storage core** | Vault + plan storage working | `vault.py`, `enrollment.py`, ID generators |
| **3. Ingestion** | PDF → structured orbs | `ocr.py`, `parser.py`, `validation.py` |
| **4. Billing** | Quotation emailed + logged | `billing.py`, billing_codes seed |
| **5. Tracking API** | Complete orbs, dashboard query | `orbs.py`, `dashboard.py`, `at-risk` |
| **6. Checkpoints** | Daily cron + state machine | `checkpoints.py`, `scheduler.py`, `alert_log` |
| **7. Frontend** | Clinic dashboard live | React, TanStack Query, OrbRow, AlertPanel |
| **8. Closure** | Lock + completion report | `reports.py`, close_plan |
| **9. Auth + polish** | JWT, patient detail, billing tab | `auth.py`, PatientDetail, role gating |

### MVP Cut Line

For the **smallest demoable version**, phases 1–7 are sufficient: ingest a PDF, see orbs on the dashboard, mark them complete, watch the daily checkpoint move a plan into grace/extended/completed. Closure reporting and full auth can follow.

---

## Appendix A — Orb Catalog (`app.orbs`)

The system seeds a 30-entry orb catalog spanning 8 categories. Each treatment plan still
contains exactly **10 orbs** (`app.patient_orbs.orb_number` 1–10); each slot is linked via
`catalog_orb_id` to the catalog entry it represents.

| Catalog Code | Title | Category | Billing Codes |
|--------------|-------|----------|---------------|
| LAB-01 | Blood Work — Baseline Labs | Lab | CPT 83036, 80053 |
| LAB-02 | Complete Blood Count (CBC) | Lab | CPT 85025 |
| LAB-03 | Thyroid Function Panel | Lab | CPT 84443 |
| LAB-04 | Fasting Blood Glucose Check | Lab | CPT 82947 |
| LAB-05 | Chest X-Ray — Diagnostic Imaging | Lab | CPT 71046 |
| MED-01 | Begin Metformin 500mg | Medicine | ICD-10 E11.9 |
| MED-02 | Begin Lisinopril 10mg | Medicine | ICD-10 I10 |
| MED-03 | Begin Albuterol Inhaler | Medicine | ICD-10 J44.1 |
| MED-04 | Begin SSRI for Depression | Medicine | ICD-10 F32.9 |
| VIT-01 | Daily Multivitamin Protocol | Vitamins | — |
| VIT-02 | Vitamin D Supplementation | Vitamins | — |
| VIT-03 | Iron Supplementation | Vitamins | ICD-10 K92.1 |
| EXR-01 | First 20-Minute Walk | Exercise | — |
| EXR-02 | 7-Day Exercise Streak | Exercise | — |
| EXR-03 | Physical Therapy — Therapeutic Exercises | Exercise | CPT 97110 |
| EXR-04 | Physical Therapy — Manual Therapy | Exercise | CPT 97140 |
| MON-01 | Blood Sugar Logging — 7 Days | Monitoring | HCPCS A4253 |
| MON-02 | Blood Pressure Logging — 7 Days | Monitoring | ICD-10 I10 |
| MON-03 | CPAP Compliance Tracking | Monitoring | HCPCS E0601 |
| MON-04 | Weight & Symptom Journal | Monitoring | — |
| DIE-01 | Nutrition Overhaul — 7 Days | Diet | — |
| DIE-02 | Low-Sodium Diet Plan | Diet | ICD-10 I10, I25.10 |
| DIE-03 | Diabetic Meal Planning | Diet | ICD-10 E11.9 |
| REF-01 | Book Specialist Referrals | Referral | ICD-10 Z01.01, Z01.89 |
| REF-02 | Cardiology Referral | Referral | ICD-10 I25.10 |
| REF-03 | Orthopedic Referral — Knee | Referral | ICD-10 M17.11 |
| REF-04 | Behavioral Health Referral | Referral | ICD-10 F41.1 |
| REV-01 | Final Check-In — Office Visit | Review | CPT 99214 |
| REV-02 | Follow-Up Visit — Low Complexity | Review | CPT 99213 |
| REV-03 | Annual Wellness Visit | Review | HCPCS G0439 |

---

## Appendix B — Billing Codes Reference (`billing.billing_codes`)

### ICD-10-CM — Diagnosis Codes (`is_billable = FALSE`)

| Code | Description |
|------|-------------|
| E11.9 | Type 2 diabetes mellitus, no complications |
| E11.65 | Type 2 diabetes with hyperglycemia |
| I10 | Essential (primary) hypertension |
| I25.10 | Atherosclerotic heart disease, unspecified |
| J06.9 | Acute upper respiratory infection, unspecified |
| J18.9 | Pneumonia, unspecified organism |
| J44.1 | COPD with acute exacerbation |
| F32.9 | Major depressive disorder, single episode |
| F41.1 | Generalized anxiety disorder |
| M54.5 | Low back pain |
| M17.11 | Primary osteoarthritis, right knee |
| N39.0 | Urinary tract infection |
| K21.0 | GERD with esophagitis |
| K92.1 | Melena (blood in stool) |
| Z23 | Encounter for immunization |
| Z00.00 | General adult medical exam, no abnormal findings |
| Z12.31 | Encounter for colorectal cancer screening |
| Z23.4 | Encounter for flu vaccination |
| R05.9 | Cough, unspecified |
| R51.9 | Headache, unspecified |
| R07.9 | Chest pain, unspecified |
| R55 | Syncope and collapse (fainting) |
| S72.001A | Femur fracture, initial encounter |
| T14.90 | Injury, unspecified |
| Z87.891 | Personal history of nicotine dependence |
| Z01.01 | Encounter for general exam with abnormal findings, eye |
| Z01.89 | Encounter for other specified special examinations |

### CPT — Procedure Codes (`is_billable = TRUE`)

| Code | Description | Unit Price | Medicare Rate | Requires Auth |
|------|-------------|-----------:|--------------:|:---:|
| 99213 | Office visit, established patient, low complexity | 75.00 | 60.00 | No |
| 99214 | Office visit, established patient, moderate complexity | 115.00 | 92.00 | No |
| 99203 | Office visit, new patient, low complexity | 100.00 | 80.00 | No |
| 99204 | Office visit, new patient, moderate complexity | 160.00 | 128.00 | No |
| 99395 | Preventive visit, established patient, 18–39 years | 150.00 | 120.00 | No |
| 99396 | Preventive visit, established patient, 40–64 years | 165.00 | 132.00 | No |
| 93000 | Electrocardiogram (ECG/EKG), routine | 25.00 | 20.00 | No |
| 71046 | Chest X-ray, 2 views | 40.00 | 32.00 | No |
| 80053 | Comprehensive metabolic panel (blood test) | 62.00 | 50.00 | No |
| 85025 | Complete blood count (CBC) with differential | 35.00 | 28.00 | No |
| 83036 | Hemoglobin A1c test (diabetes monitoring) | 45.00 | 36.00 | No |
| 84443 | Thyroid stimulating hormone (TSH) test | 40.00 | 32.00 | No |
| 82947 | Blood glucose test | 15.00 | 12.00 | No |
| 36415 | Routine venipuncture (blood draw) | 8.00 | 6.50 | No |
| 90837 | Psychotherapy, 60 minutes | 150.00 | 120.00 | No |
| 90834 | Psychotherapy, 45 minutes | 110.00 | 88.00 | No |
| 97110 | Therapeutic exercises (physical therapy) | 45.00 | 36.00 | No |
| 97140 | Manual therapy (physical therapy) | 40.00 | 32.00 | No |
| 27447 | Total knee replacement | 1500.00 | 1200.00 | Yes |
| 43239 | Upper GI endoscopy with biopsy | 450.00 | 360.00 | Yes |
| 45378 | Colonoscopy, diagnostic | 500.00 | 400.00 | Yes |
| 70553 | MRI brain with contrast | 1200.00 | 960.00 | Yes |
| 73721 | MRI joint of lower extremity | 900.00 | 720.00 | Yes |
| 99291 | Critical care, first 30–74 minutes | 250.00 | 200.00 | No |
| 99232 | Subsequent hospital care, moderate complexity | 110.00 | 88.00 | No |

### HCPCS Level II — Equipment and Supplies (`is_billable = TRUE`)

| Code | Description | Unit Price | Medicare Rate | Requires Auth |
|------|-------------|-----------:|--------------:|:---:|
| A4253 | Blood glucose test strips, per 50 | 38.00 | 30.00 | No |
| E0601 | CPAP device (sleep apnea) | 700.00 | 560.00 | Yes |
| J0171 | Adrenalin epinephrine injection | 15.00 | 12.00 | No |
| J1040 | Methylprednisolone injection, 80mg | 20.00 | 16.00 | No |
| L0650 | Lumbar-sacral orthosis (back brace) | 250.00 | 200.00 | Yes |
| G0008 | Administration of influenza vaccine | 25.00 | 20.00 | No |
| G0439 | Annual wellness visit, subsequent | 140.00 | 112.00 | No |
| Q4161 | Skin substitute, per square centimeter | 150.00 | 120.00 | Yes |
| V2020 | Frames, purchases | 80.00 | 64.00 | No |
| V2100 | Sphere single vision, plano to plus/minus 4.00 | 50.00 | 40.00 | No |

---

*End of implementation guide.*
