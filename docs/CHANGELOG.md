# Changelog

A running log of changes made to this project's design docs and code. For build-status
tracking see [PROGRESS.md](PROGRESS.md); for known issues see [BUGS.md](BUGS.md).

---

## 2026-06-13 (Team Lead review fixes)

### Module 3/4 review: fixed patient login impersonation and review-queue gap
- **BUG-008 (critical, fixed):** Patient login no longer trusts a client-supplied `patient_id`.
  `LoginRequest.patient_id` renamed to `patient_token`; `authenticate_demo_user` now verifies the
  token against `vault.patient_vault.token` and resolves the real `patient_id` server-side before
  issuing a JWT. See `docs/BUGS.md` BUG-008.
- **BUG-009 (medium, fixed):** Added `GET /api/review-queue` and
  `GET /api/review-queue/{review_id}` so clinicians/coordinators can see and inspect plans that
  failed ingestion validation. Added a "Needs Review" panel to the Upload page. See
  `docs/BUGS.md` BUG-009.
- Test suite: 28/28 passing (`uv run pytest backend/tests -q`).
- **BUG-007 (fixed):** `/api/ingest` was returning 500 once `BILLING_EMAIL` was set, because
  `email_quotation()` connected to `smtplib.SMTP(smtp_host)` on the default port 25 while Mailpit
  listens on 1025 (`ConnectionRefusedError`). Added `SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/
  `SMTP_USE_TLS` config; local dev now uses `SMTP_PORT=1025`, `SMTP_USE_TLS=false` to match
  Mailpit. See `docs/BUGS.md` BUG-007.
- **BUG-010 (fixed):** "Confirm Billing" did nothing because `POST
  /api/plans/{plan_id}/confirm-billing` 500'd — `enroll()` passed an orb's `target_date` (an ISO
  string from the parsed plan JSON) directly to an asyncpg `Date` column parameter, which raised
  `DataError: ... 'str' object has no attribute 'toordinal'`. Added `_coerce_date()` to
  `backend/app/services/enrollment.py` to parse ISO strings to `date` before binding. See
  `docs/BUGS.md` BUG-010.
- Test suite: 32/32 passing.
- **BUG-011 (fixed):** Orb tracker "Start"/"Complete"/"Skip" buttons did nothing —
  `POST /api/orbs/{orb_ref}/status` and `POST /api/orbs/{orb_ref}/complete` 500'd with
  `asyncpg.exceptions.AmbiguousParameterError: inconsistent types deduced for parameter $1,
  DETAIL: text versus character varying`. Caused by reusing the `:status` bind parameter in both
  an assignment and a `CASE WHEN` comparison in `set_orb_status()`. Fixed by giving the `CASE
  WHEN` comparison its own bind parameter (`:status_check`) in
  `backend/app/services/orbs.py`. See `docs/BUGS.md` BUG-011.

## 2026-06-13

### HIPAA compliance checklist added; AI vendor decision recorded
- Added [`HIPAA.md`](HIPAA.md) — a working HIPAA compliance checklist (technical safeguards,
  AI vendor/BAA requirements, email/billing channel risk, administrative/physical safeguards,
  prototype-to-production gate). Linked from the root `README.md` documentation index.
- Confirmed the project's AI stack: **Mistral OCR** for text extraction + **OpenAI GPT-4o** for
  structured parsing (the "paid" row in `agents/02-ingestion-and-billing.md` §1 — not the
  fully-local Tesseract/Ollama fallback). Updated `HIPAA.md` §3 and `SECURITY.md` §6 accordingly:
  BAAs with **both** Mistral and OpenAI are required before any real PHI is ingested; until then,
  development and demos continue with the synthetic Marcus Elliot fixture only.

### BUG-004 resolved
- Closed **BUG-004**: decision made to keep `Z01.01`/`Z01.89` in `app.seed_data.ICD10_CODES` and
  `REF-01`'s `billing_codes`. No code changes required.

### Documentation consolidation
- Moved all root-level project MD files (`DESIGN.md`, `Orbs_Implementation_Guide.md`,
  `PROGRESS.md`, `SECURITY.md`, `EVALUATION.md`, `OBSERVABILITY.md`, `CHANGELOG.md`,
  `BUGS.md`) into a new [`docs/`](.) folder. `agents/` and `team/` were left in place.
- Updated cross-references: links between docs in `docs/` are unchanged (same directory);
  links to `agents/*` and `team/*` now use `../` prefixes; `agents/README.md`'s link to
  `Orbs_Implementation_Guide.md` now points to `../docs/Orbs_Implementation_Guide.md`.
- Added a "Documentation" index section to the root `README.md` linking into `docs/`.

---

## 2026-06-12

### Module 1 review (Team Lead)
- Reviewed the Developer's Module 1 delivery (`backend/` — schemas, vault encryption, ID
  generators, `store_plan`/`enroll`, seed data, Alembic migration, unit tests). 5/5 tests pass.
- Filed **BUG-005** (High) and **BUG-006** (Medium) in [BUGS.md](BUGS.md): random,
  uniqueness-unchecked `patient_id`/`plan_id` generation combined with `ON CONFLICT DO UPDATE`
  can silently overwrite another patient's vault/plan data on collision; deterministic
  name+DOB-derived tokens can collide for patients sharing name and DOB.
- Carried forward **BUG-004** (Open) — `Z01.01`/`Z01.89` have now shipped in
  `backend/app/seed_data.py` as part of Module 1.

### Fixed (BUG-005, BUG-006)
- **`backend/app/ids.py`** — `generate_token()` no longer derives the patient token from
  name/DOB; it now returns `"tok_" + secrets.token_hex(8)` (non-deterministic, 64 bits).
  Added shared `MAX_UNIQUE_ID_ATTEMPTS = 20` constant.
- **`backend/app/services/storage.py`** — added `generate_unique_patient_id()` /
  `generate_unique_plan_id()`, which generate-and-check against `vault.patient_vault` /
  `app.treatment_plans` and retry on collision. `store_plan()` uses these whenever the caller
  doesn't supply `patient_id`/`plan_id`, preventing `ON CONFLICT DO UPDATE` from silently
  overwriting another patient's row on a random-ID collision.
- **`backend/app/services/vault.py`** — added `generate_unique_token()` (same retry pattern
  against `vault.patient_vault.token`). `upsert_patient_vault()` now uses `RETURNING token` and
  no longer overwrites `token` on conflict, so an existing patient keeps their original token
  on re-ingest.
- **Tests** — `backend/tests/test_ids.py` updated for the new `generate_token()` signature;
  added `backend/tests/test_unique_ids.py` covering collision retries and exhaustion for all
  three generators. Full suite: 9/9 passing.

### Repository restructure
- Merged the placeholder `BE/` directory into `backend/` (which now contains the real Module 1
  implementation): `BE/treatment_plan_generator.py` → `backend/scripts/treatment_plan_generator.py`,
  `BE/docs/` → `backend/scripts/docs/`. Removed the now-empty `BE/` and its empty
  `requirements.txt`.
- Renamed the empty `FE/` placeholder to `frontend/`, matching the target structure in
  [DESIGN.md §10](DESIGN.md#10-repository-structure-target).
- Updated path references in `DESIGN.md`, `PROGRESS.md`, `EVALUATION.md`, and `BUGS.md`
  accordingly.

### Added
- **`PROGRESS.md`** — implementation status tracker against the Module 1-4 build plan
  (DESIGN.md §9), with an MVP cut-line checklist (0/7 phases complete as of this date).
- **`SECURITY.md`** — security policy combining PII/vault/two-document controls
  (DESIGN.md §7) with secrets/logging rules from `../team/DEVELOPER.md` and `../team/TEAM_LEAD.md`,
  plus a pre-merge security checklist.
- **`EVALUATION.md`** — evaluation plan per module (OCR, parser/catalog-matching, validation
  gate, billing quotation, checkpoint state machine, API/frontend), using the Marcus Elliot
  sample PDF as the golden test fixture.
- **`OBSERVABILITY.md`** — logging conventions, audit trail tables (`access_log`, `alert_log`,
  `quotation_log`), operational metrics, health checks, and alerting thresholds.
- **`CHANGELOG.md`**, **`BUGS.md`** — this file and the bug tracker.

### Changed
- **`backend/scripts/treatment_plan_generator.py`** — rewritten to fix pagination and reflect the expanded
  orb catalog:
  - Fixed page-overflow bug where the page-2 orb loop's height estimate under-counted wrapped
    text, silently dropping Orbs 5 and 6 from the rendered PDF.
  - Replaced hardcoded `TOTAL = 3` with `compute_total_pages()`, a dry-run pagination pass using
    the same exact height functions (`pdfmetrics.stringWidth`-based `wrap_h`) as the real
    render — output is now a correct, dynamically-paginated 5-page PDF with consistent
    "Page X of 5" footers.
  - Fixed broken output path — PDF now writes to `backend/scripts/docs/Marcus_Elliot_Treatment_Plan_v2.pdf`
    via a path computed relative to the script location.
  - Each of the 10 orbs is now annotated with its `app.orbs` catalog code (e.g. `LAB-01`).

---

## Earlier (undated, prior session)

### Added
- **`../agents/`** module folder — split `Orbs_Implementation_Guide.md` into 4 implementation
  modules (`01-foundations-and-storage.md`, `02-ingestion-and-billing.md`,
  `03-tracking-and-checkpoints.md`, `04-frontend-closure-and-auth.md`) plus an `../agents/README.md`
  index with shared architecture diagram, tech stack table, and MVP cut line.
- **`DESIGN.md`** — high-level design reference document (problem/goals, architecture, data
  model, six stages, checkpoint state machine, security/compliance, API surface, build plan).

### Changed
- **`app.orbs`** expanded from a smaller seed set to a **30-entry catalog across 8 categories**
  (Lab, Medicine, Vitamins, Exercise, Monitoring, Diet, Referral, Review). Each plan still
  contains exactly 10 orbs (`app.patient_orbs`, `orb_number` 1-10), now linked to a catalog
  entry via a new `catalog_orb_id` foreign key.
- **`billing.billing_codes`** seeded with the full ICD-10-CM (27 codes, including `Z01.01` and
  `Z01.89` added to support the `REF-01` catalog entry), CPT (25 codes), and HCPCS (10 codes)
  reference set, with `unit_price`, `medicare_rate`, `requires_auth`, and `is_billable`.
- Updated `../agents/01-foundations-and-storage.md`, `Orbs_Implementation_Guide.md`, `DESIGN.md`,
  and `../agents/02-ingestion-and-billing.md` to reflect the expanded catalog and billing codes
  (new Appendix A — Orb Catalog, Appendix B — Billing Codes Reference; `enroll()` snippet now
  sets `catalog_orb_id` via `match_catalog_orb()`).
