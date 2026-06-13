# Design Document — 10 Orbs to Better

**A treatment-plan tracking system: from PDF ingestion to plan closure.**

This document is the high-level design reference for the project. For full implementation
detail and step-by-step build instructions, see [`Orbs_Implementation_Guide.md`](Orbs_Implementation_Guide.md)
and the per-module breakdowns in [`../agents/`](../agents/).

---

## 1. Problem & Goals

The system tracks structured treatment plans where each plan contains exactly **10 "orbs"** —
discrete tasks a patient must complete within a prescribed window before their next clinical
visit. A plan moves through six stages, beginning as a PDF generated at a doctor visit and
ending in a closed, reported state.

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

- **PII isolation** — patient identity lives only in the encrypted vault; every document,
  email, and dashboard uses tokens.
- **Human-in-the-loop** — ingestion failures and validation gaps route to a review queue,
  never auto-save.
- **Audit everything** — every quotation, every status change, every vault access is logged.
- **Fail safe** — unmatched billing codes are flagged, never silently dropped; orbs lock at
  hard stop.

---

## 2. Architecture

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

### Request Flow

```
PDF → OCR → Parse → Quotation → Email Billing
    → Tokenize → Store → Enroll → Track (daily cron) → Close → Report
```

---

## 3. Technology Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| API framework | FastAPI | Async REST API, auto OpenAPI docs |
| ORM | SQLAlchemy 2.0 | Async database models |
| DB driver | asyncpg | PostgreSQL async driver |
| Migrations | Alembic | Schema version control |
| Scheduler | APScheduler | In-process daily checkpoint cron |
| Auth | python-jose (JWT) | Token issuance and validation |
| Validation | Pydantic v2 | Request/response + LLM structured output |
| Encryption | pgcrypto | AES-256 PII encryption (Postgres ext.) |
| Frontend | React 18 + Vite | Component UI, dev/build tooling |
| Data fetching | TanStack Query | Polling, caching, auto-refetch |
| Styling | Tailwind CSS + shadcn/ui | Cards, badges, progress bars |
| Charts | Recharts | Completion trends |
| OCR | Mistral OCR (paid) / Tesseract+docTR (free) | Free stack sufficient for clean digital PDFs |
| Parsing | OpenAI GPT-4o (paid) / Ollama + Llama 3.1 8B (free) | Structured JSON extraction |
| Infra | Docker Compose | Three services: `frontend`, `backend`, `db` |

---

## 4. Data Model

Three PostgreSQL schemas keep concerns separated:

- **`vault`** — `patient_vault` (encrypted PII via `pgp_sym_encrypt`, token mapping, access log).
  Fully isolated from treatment data.
- **`app`** — `treatment_plans`, `diagnoses`, `orbs` (a 30-entry catalog across 8 categories —
  Lab, Medicine, Vitamins, Exercise, Monitoring, Diet, Referral, Review), `patient_orbs`
  (per-patient tracking rows, 10 per plan, each linked to a catalog entry via
  `catalog_orb_id`), `alert_log`. No PII — references patients only by token/`patient_id`.
- **`billing`** — `billing_codes` (full ICD-10-CM / CPT / HCPCS reference with pricing),
  `quotation_log` (full quote snapshots, token only).

Full DDL is in [`Orbs_Implementation_Guide.md §4`](Orbs_Implementation_Guide.md#4-data-model)
and [`../agents/01-foundations-and-storage.md`](../agents/01-foundations-and-storage.md).

---

## 5. The Six Stages

| Stage | Summary |
|-------|---------|
| **1. Plan Creation** | Doctor visit generates two PDFs: a full-PII `_clinical.pdf` (locked storage, clinician-only) and a redacted `_processing.pdf` (IDs only) that enters the pipeline. |
| **2. Ingestion** | Processing PDF → OCR (Mistral/Tesseract) → markdown → LLM parser (GPT-4o/Ollama) → structured JSON → validation gate (must have exactly 10 orbs numbered 1–10, required fields present, else routes to human review). |
| **2.5 Billing Quotation** | Collect diagnosis + orb billing codes → price against `billing.billing_codes` → build quote (line items, unmatched codes flagged, prior-auth items surfaced) → email token-only quote to billing → log to `billing.quotation_log`. Plan may pause in `pending_enrollment` until billing confirms. |
| **3. Tokenization & Storage** | Generate `patient_id` and `token`; encrypt PII into `vault.patient_vault`; store plan + diagnoses in `app` schema with no PII. |
| **4. Enrollment** | Compute timeline (target date, hard stop, checkpoints from `duration`/`buffer`/`extension`); create 10 `pending` rows in `app.patient_orbs`; notify patient. |
| **5. Live Tracking** | Patients/clinicians mark orbs complete (`complete_orb`, locked once plan is `closed`). Dashboard and at-risk queries drive the clinic UI. Daily cron evaluates checkpoints. |
| **6. Closure** | At hard stop, plan closes regardless of completion: incomplete orbs locked, completion report (PDF) generated, patient + clinic notified. Report reviewed at next visit, which starts a new plan (back to Stage 1). |

---

## 6. Checkpoint State Machine

A single daily cron (`08:00`) evaluates every active plan.

```
duration            = 14 days   (doctor-prescribed)
buffer              = 3 days    (early-warning window)
extension_duration  = 7 days    (grace period, always added)
hard_stop           = duration + extension = day 21
completion_threshold = 8 of 10 orbs
```

| Checkpoint | Day | Condition | Resulting State |
|-----------|-----|-----------|------------------|
| 1 | `duration - buffer` (11) | `< 8` orbs | stays `ACTIVE`, warning alerts |
| 2 | `duration` (14) | `== 10` | `COMPLETED` |
| 2 | `duration` (14) | `8–9` | `IN_GRACE` (+7 days) |
| 2 | `duration` (14) | `< 8` | `EXTENDED` (+7 days + outreach) |
| 3 | `hard_stop - buffer` (18) | `< 10` | unchanged, final warning + escalation |
| 4 | `hard_stop` (21) | any | `CLOSED`, orbs locked, report generated |

States: `ACTIVE → {IN_GRACE, EXTENDED, COMPLETED} → CLOSED`. Full state diagram and Python
reference implementation in
[`../agents/03-tracking-and-checkpoints.md`](../agents/03-tracking-and-checkpoints.md).

### Open Design Questions

1. **IN_GRACE vs EXTENDED** — currently distinct (8–9 = light touch, <8 = outreach call). Could
   merge into one `EXTENDED` state if the outreach distinction isn't operationally useful.
2. **Grace-week completion scope** — can the patient complete *any* orb during the grace week,
   or only the orbs flagged incomplete at day 14? Current default: any orb.

---

## 7. Security & Compliance

- **PII tokenization** — patient identity lives only in `vault.patient_vault`, encrypted with
  `pgcrypto` under a customer-managed KMS key. Every other table, document, email, and
  dashboard uses the token (`PAT-2025-00847`). Vault reads are logged.
- **Two-document strategy** — clinical PDF (full PII, locked/BAA-covered storage) vs.
  processing PDF (redacted, enters OCR/LLM pipeline).
- **HIPAA controls** — encryption at rest (pgcrypto AES-256) and in transit (TLS 1.3), JWT +
  role-based access, audit trails (`alert_log`, `quotation_log`, vault `access_log`), minimum
  necessary access (tokens everywhere, PII fetched on demand), BAA required from any AI vendor
  touching PHI (the redacted processing PDF avoids sending PHI to the LLM entirely).
- **Billing channel safety** — quotation emails contain token only; unmatched billing codes
  flagged, never dropped; prior-authorization items surfaced early.

---

## 8. API Surface

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

## 9. Build Plan

Implementation is split into four modules (each independently buildable, with the listed
dependencies):

| Module | Doc | Covers | Depends on |
|--------|-----|--------|------------|
| 1 | [agents/01-foundations-and-storage.md](../agents/01-foundations-and-storage.md) | DB schemas, vault encryption, ID generators, Plan Creation, Tokenization & Storage, Enrollment | — |
| 2 | [agents/02-ingestion-and-billing.md](../agents/02-ingestion-and-billing.md) | OCR/parsing, validation gate, billing quotation pipeline | Module 1 |
| 3 | [agents/03-tracking-and-checkpoints.md](../agents/03-tracking-and-checkpoints.md) | Orb completion, dashboard/at-risk queries, checkpoint state machine, daily cron | Module 1; calls Module 4 |
| 4 | [agents/04-frontend-closure-and-auth.md](../agents/04-frontend-closure-and-auth.md) | React frontend, plan closure & reporting, JWT auth | Modules 1–3 |

**MVP cut line:** Modules 1–3 plus the frontend portion of Module 4 (build phases 1–7) are
sufficient for the smallest demoable version — ingest a PDF, see orbs on the dashboard, mark
them complete, and watch the daily checkpoint move a plan into grace/extended/completed.
Closure reporting and full auth can follow.

---

## 10. Repository Structure (target)

```
orbs-mvp/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── auth.py
│   │   ├── scheduler.py
│   │   ├── routers/        # ingest, dashboard, patients, orbs, billing
│   │   └── services/        # ocr, parser, validation, billing, vault, checkpoints, enrollment, reports
│   ├── tests/
│   └── scripts/
│       ├── treatment_plan_generator.py  # sample clinical PDF generator
│       └── docs/                         # generated sample PDFs (golden fixtures)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/                 # pages: Dashboard, PatientDetail, Upload; components: OrbRow, StatusBadge, MetricCard, AlertPanel
```

> Module 1 (foundations & storage) is implemented under `backend/`. The sample PDF generator
> (formerly `BE/treatment_plan_generator.py`) now lives at `backend/scripts/treatment_plan_generator.py`,
> producing `backend/scripts/docs/Marcus_Elliot_Treatment_Plan_v2.pdf`. The placeholder `FE/`
> directory has been renamed to `frontend/`, to be populated as Module 4 is implemented.

---

## Appendix — Orb Catalog & Billing Codes

`app.orbs` is seeded with a **30-entry catalog across 8 categories** (Lab, Medicine, Vitamins,
Exercise, Monitoring, Diet, Referral, Review). Each plan still contains exactly **10 orbs**
(`app.patient_orbs.orb_number` 1–10), each linked to a catalog entry via `catalog_orb_id`.
`billing.billing_codes` is seeded with the full ICD-10-CM / CPT / HCPCS reference set used to
price those catalog entries and any plan-specific codes.

Full catalog and billing code tables:
[`Orbs_Implementation_Guide.md` — Appendix A & B](Orbs_Implementation_Guide.md#appendix-a--orb-catalog-apporbs)
and [`../agents/01-foundations-and-storage.md` — Step 4](../agents/01-foundations-and-storage.md#step-4--seed-data).
