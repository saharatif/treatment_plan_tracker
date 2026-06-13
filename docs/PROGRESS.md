# Progress Tracker — 10 Orbs to Better

This file tracks implementation status against the [Build Plan](DESIGN.md#9-build-plan) (Modules
1–4 / build phases 1–9). Update it as work lands — it's the quickest way to see what's actually
built vs. only designed.

**Status legend:** ✅ Done · 🔄 In progress · ⬜ Not started

---

## Phase 0 — Design

| Item | Status | Notes |
|------|--------|-------|
| High-level design (`DESIGN.md`) | ✅ | Architecture, data model, six stages, checkpoint state machine, security, API surface, build plan |
| Full implementation guide (`Orbs_Implementation_Guide.md`) | ✅ | DDL, seed data, appendices (orb catalog + billing codes) |
| Module breakdowns (`../agents/01-04`) | ✅ | Per-module implementation steps |
| Orb catalog seed (30 entries / 8 categories) | ✅ | Defined in `../agents/01-foundations-and-storage.md` Step 4 |
| Billing codes seed (ICD-10-CM / CPT / HCPCS) | ✅ | Defined in `../agents/01-foundations-and-storage.md` Step 4 |
| Sample clinical PDF (`backend/scripts/treatment_plan_generator.py`) | ✅ | Generates `Marcus_Elliot_Treatment_Plan_v2.pdf`, used as a pipeline input fixture |

---

## Module 1 — Foundations & Storage

*Doc: [agents/01-foundations-and-storage.md](../agents/01-foundations-and-storage.md)*

| Item | Status | Notes |
|------|--------|-------|
| Postgres schemas (`vault`, `app`, `billing`) created | ✅ | `backend/alembic/versions/20260612_0001_foundations_storage.py` |
| `pgcrypto` extension + vault encryption | ✅ | `init/01-extensions.sql` + `app/services/vault.py` (`pgp_sym_encrypt`/`pgp_sym_decrypt`, access log) |
| `app.orbs` catalog table + seed (30 rows) | ✅ | `app/models.py` (`Orb`) + `app/seed_data.py` (`ORB_CATALOG`) + `app/seed.py` |
| `billing.billing_codes` table + seed | ✅ | `app/models.py` (`BillingCode`) + `app/seed_data.py` (ICD-10/CPT/HCPCS) + `app/seed.py` |
| ID generators (`patient_id`, `plan_id`, `token`, `orb_ref`) | ✅ | `app/ids.py` + collision-checked wrappers in `storage.py`/`vault.py` (BUG-005/006, both fixed) |
| `store_plan()` / `enroll()` | ✅ | `app/services/storage.py`, `app/services/enrollment.py` (incl. `match_catalog_orb`) |
| Alembic migrations set up | ✅ | `backend/alembic/` (env.py + initial revision) |
| Unit tests | ✅ | `backend/tests/test_ids.py`, `test_enrollment_matching.py`, `test_unique_ids.py` — 9/9 passing |

## Module 2 — Ingestion & Billing

*Doc: [agents/02-ingestion-and-billing.md](../agents/02-ingestion-and-billing.md)*

| Item | Status | Notes |
|------|--------|-------|
| OCR service (`services/ocr.py`) | ⬜ | Mistral OCR (paid) / Tesseract (free) |
| Parser service (`services/parser.py`) | ⬜ | GPT-4o (paid) / Ollama+Llama3.1 (free) |
| Validation gate (`services/validation.py`) | ⬜ | |
| Billing quotation (`services/billing.py`) | ⬜ | |
| `POST /api/ingest` | ⬜ | |
| `POST /api/plans/{plan_id}/confirm-billing` | ⬜ | |
| `GET /api/quotations` | ⬜ | |

## Module 3 — Live Tracking & Checkpoints

*Doc: [agents/03-tracking-and-checkpoints.md](../agents/03-tracking-and-checkpoints.md)*

| Item | Status | Notes |
|------|--------|-------|
| `complete_orb()` / orb status updates | ⬜ | |
| Dashboard + at-risk queries | ⬜ | |
| `PlanStatus` enum + state machine | ⬜ | |
| `evaluate_plan_checkpoints()` | ⬜ | |
| APScheduler daily 08:00 cron | ⬜ | |
| `GET /api/dashboard`, `/api/at-risk` | ⬜ | |

## Module 4 — Frontend, Closure & Auth

*Doc: [agents/04-frontend-closure-and-auth.md](../agents/04-frontend-closure-and-auth.md)*

| Item | Status | Notes |
|------|--------|-------|
| `close_plan()` + completion report (PDF) | ⬜ | |
| `auth.py` (JWT issuance/validation) | ⬜ | |
| React app scaffold (Vite + Tailwind/shadcn) | ⬜ | `frontend/` currently empty (renamed from `FE/`) |
| Dashboard page | ⬜ | |
| Patient detail page | ⬜ | |
| Upload page | ⬜ | |

---

## MVP Cut Line

Per [DESIGN.md §9](DESIGN.md#9-build-plan), the smallest demoable version is **Modules 1–3 plus
the frontend portion of Module 4** (build phases 1–7): ingest a PDF, see orbs on the dashboard,
mark them complete, and watch the daily checkpoint move a plan into grace/extended/completed.
Closure reporting and full auth can follow.

**Current MVP progress: ~2 / 7 phases complete** — Module 1 (phases 1-2: schemas, vault
encryption, ID generators, `store_plan`/`enroll`, seed data) is implemented and unit-tested.
BUG-004, BUG-005, and BUG-006 from Team Lead review are all closed/fixed (9/9 tests passing).
Module 2 can begin.

---

## Repository State

```
treatment_plan_tracker/
├── docs/
│   ├── DESIGN.md                      ✅
│   ├── Orbs_Implementation_Guide.md   ✅
│   ├── PROGRESS.md                    ✅ (this file)
│   ├── SECURITY.md                    ✅
│   ├── EVALUATION.md                  ✅
│   ├── OBSERVABILITY.md               ✅
│   ├── CHANGELOG.md                   ✅
│   └── BUGS.md                        ✅
├── agents/                            ✅ (01-04 + README)
├── backend/                           🔄 Module 1 implemented
│   ├── app/                           ✅ models, config, database, ids, services (vault, storage, enrollment), seed data
│   ├── alembic/                       ✅ initial migration (vault/app/billing schemas)
│   ├── tests/                         ✅ ids + enrollment-matching unit tests
│   └── scripts/
│       ├── treatment_plan_generator.py  ✅ sample PDF generator
│       └── docs/                         ✅ sample clinical PDF
├── frontend/                          ⬜ empty — frontend not started
└── team/                              ✅ DEVELOPER.md, TEAM_LEAD.md
```

---

## Next Steps

1. Stand up Postgres + apply Module 1 DDL (schemas, orb catalog, billing codes, ID generators).
2. Implement `store_plan()` / `enroll()` and verify against the sample Marcus Elliot PDF.
3. Build Module 2's OCR → parser → validation → quotation pipeline against the `_processing.pdf`
   variant of the sample document.
4. Stand up the FastAPI app skeleton (`backend/app/`) with routers/services matching
   `DESIGN.md §10`'s target structure.
