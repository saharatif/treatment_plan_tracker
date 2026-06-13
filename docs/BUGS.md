# Bug Tracker

Per [`../team/TEAM_LEAD.md`](../team/TEAM_LEAD.md), security and correctness findings are logged here
by severity. Each entry: **Status**, **Severity**, **Component**, **Description**, **Fix**.

**Status legend:** 🟢 Fixed · 🟡 Open · 🔴 Open (blocking)

---

## BUG-001 — Orbs 5 & 6 silently dropped from PDF output

- **Status:** 🟢 Fixed (2026-06-12)
- **Severity:** High (data loss in clinical document)
- **Component:** `backend/scripts/treatment_plan_generator.py`
- **Description:** The page-2 orb-rendering loop estimated each orb's height with a fixed
  formula (`14+13+13+13+len(orb["interventions"])*12+24`) that under-counted the actual height
  of wrapped text. The loop's `if y - needed < 55: break` guard fired after only 4 orbs,
  silently dropping Orbs 5 and 6 from the rendered PDF with no error or warning.
- **Fix:** Rewrote height calculation to use `pdfmetrics.stringWidth`-based `wrap_h`, matching
  the exact wrapping logic used at render time. Verified all 10 orbs now render across pages
  2-4.

---

## BUG-002 — Hardcoded total page count caused incorrect page footers

- **Status:** 🟢 Fixed (2026-06-12)
- **Severity:** Medium (cosmetic, but visible on a clinical document)
- **Component:** `backend/scripts/treatment_plan_generator.py`
- **Description:** `TOTAL` was hardcoded to `3` while the document actually rendered 4 pages
  (and, after fixing BUG-001, 5 pages). Pages 3 and 4 both displayed "Page 3 of 3", an
  inconsistent/incorrect footer.
- **Fix:** Added `compute_total_pages()`, a dry-run pagination pass using the same height
  functions as the real render, executed before `build()` begins drawing. `TOTAL` is now
  derived dynamically (currently 5) and every page footer is consistent.

---

## BUG-003 — PDF output path broken / not relative to script location

- **Status:** 🟢 Fixed (2026-06-12)
- **Severity:** Low
- **Component:** `backend/scripts/treatment_plan_generator.py`
- **Description:** The output path for the generated PDF was not reliably resolved relative to
  the script's location, causing the file to be written to an unexpected location depending on
  the working directory the script was invoked from.
- **Fix:** `OUT` is now computed as
  `os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "Marcus_Elliot_Treatment_Plan_v2.pdf")`,
  always resolving to `backend/scripts/docs/` regardless of invocation directory.

---

## BUG-004 — Unverified ICD-10 codes (Z01.01 / Z01.89) added to billing seed data

- **Status:** 🟢 Closed — resolved 2026-06-12 (decision: keep both codes)
- **Severity:** Low
- **Component:** `../agents/01-foundations-and-storage.md` (Step 4 seed data),
  `Orbs_Implementation_Guide.md` (Appendix B)
- **Description:** When expanding `billing.billing_codes`, two ICD-10-CM codes — `Z01.01`
  ("Encounter for examination of eyes and vision with abnormal findings") and `Z01.89`
  ("Encounter for other specified special examinations") — were added even though they were
  not part of the user-provided billing code list. They were added because the new `REF-01`
  catalog entry ("Book Specialist Referrals") references them.
- **Open question:** Confirm whether these two codes should remain in the seed set, be
  replaced with codes from the original provided list, or whether `REF-01`'s `billing_codes`
  array should be changed to reference different (already-provided) codes instead.
- **Owner:** Needs a decision from the user/Developer before Module 1 implementation seeds
  `billing.billing_codes`.
- **Update (2026-06-12):** `app/seed_data.py` has already shipped with `Z01.01`/`Z01.89`
  included as part of Module 1.
- **Resolution (2026-06-13):** Decision made to keep both codes — `REF-01` ("Book Specialist
  Referrals") continues to reference `Z01.01`/`Z01.89` in `app.seed_data.ORB_CATALOG` and
  `ICD10_CODES`. No code changes required; `../agents/01-foundations-and-storage.md` and
  `Orbs_Implementation_Guide.md` Appendix B already document these codes as part of the
  catalog.

---

## BUG-005 — `store_plan()`/`upsert_patient_vault()` can silently overwrite a different patient on ID collision

- **Status:** 🟢 Fixed (2026-06-12)
- **Severity:** High (cross-patient data corruption)
- **Component:** `backend/app/ids.py`, `backend/app/services/storage.py`,
  `backend/app/services/vault.py`
- **Description:** `generate_patient_id()` returns `PAT-{year}-{5 random digits}` (100,000
  possible values per year) and `generate_plan_id()` returns `PLN-{year}-{3 random digits}`
  (1,000 possible values per year), both via `secrets.randbelow()` with **no uniqueness check**.
  - `upsert_patient_vault()` runs `INSERT ... ON CONFLICT (patient_id) DO UPDATE SET token =
    EXCLUDED.token, name_encrypted = EXCLUDED.name_encrypted, ...` — if a newly generated
    `patient_id` happens to collide with an existing patient, this **overwrites that other
    patient's encrypted PII** with the new patient's data.
  - `store_plan()`'s `INSERT INTO app.treatment_plans ... ON CONFLICT (plan_id) DO UPDATE SET
    patient_id = EXCLUDED.patient_id, ...` has the same issue for `plan_id` collisions — a
    second patient's plan could silently overwrite a first patient's plan row.
  - At even modest scale (a few hundred patients/plans per year), birthday-paradox collision
    probability is non-trivial, and the failure mode is *silent data corruption*, not an error.
- **Fix direction:** Either (a) generate the ID, then `SELECT ... FOR UPDATE` / check existence
  in a loop until a free ID is found before the `INSERT`, or (b) make IDs derived from a DB
  sequence (`nextval`) instead of random digits, reserving `ON CONFLICT DO UPDATE` only for the
  true "re-ingest the same plan" case (e.g. keyed on an idempotency token from the ingestion
  pipeline, not on a freshly-generated random ID).
- **Why this matters for HIPAA:** [SECURITY.md §1](SECURITY.md#1-pii--phi-handling) requires
  strict PII isolation per patient — an ID collision that overwrites another patient's vault
  entry is a reportable data-integrity/PHI-exposure issue.
- **Fix applied:** Added `generate_unique_patient_id()` / `generate_unique_plan_id()` in
  `app/services/storage.py` — each generates a candidate ID and checks
  `vault.patient_vault`/`app.treatment_plans` for an existing row before accepting it, retrying
  up to `MAX_UNIQUE_ID_ATTEMPTS` (20) times and raising `RuntimeError` if no free ID is found.
  `store_plan()` now only falls back to these generators when the caller doesn't supply
  `patient_id`/`plan_id` — explicit re-ingestion (caller-supplied IDs) still uses
  `ON CONFLICT DO UPDATE` as an intentional upsert. Covered by
  `backend/tests/test_unique_ids.py` (collision retry + exhaustion).
- **Residual risk:** A check-then-insert race is still theoretically possible under concurrent
  requests generating the same ID in the same instant; acceptable for MVP scale. A follow-up
  could catch the unique-constraint `IntegrityError` on insert and retry, or move to
  DB-sequence-backed IDs.

---

## BUG-006 — `generate_token()` can produce duplicate tokens for patients with the same name + DOB

- **Status:** 🟢 Fixed (2026-06-12)
- **Severity:** Medium
- **Component:** `backend/app/ids.py` (`generate_token`), `backend/app/services/vault.py`
- **Description:** `generate_token(name, dob)` is `"tok_" + sha256(f"{name.lower().strip()}:{dob}")[:12]`
  — fully deterministic from name + DOB. Two distinct patients who happen to share both a name
  and date of birth (not impossible — common names, family members) will be assigned the
  **same token**. Since `vault.patient_vault.token` has a `UNIQUE` constraint, the second such
  patient's `upsert_patient_vault()` call will raise an `IntegrityError` on `ON CONFLICT
  (patient_id) DO UPDATE SET token = EXCLUDED.token` (conflicting on the `token` unique index,
  which isn't the `ON CONFLICT` target) — an unhandled 500 at ingestion time for a legitimate
  patient.
- **Fix direction:** Make the token non-deterministic (e.g. `secrets.token_hex` or a UUID) and
  store it once at vault-row creation; do not derive it from PII at all. This also slightly
  improves privacy — a deterministic hash of name+DOB is a (weak) re-identification vector if
  the token namespace is ever exposed.
- **Fix applied:** `generate_token()` no longer takes `name`/`dob` — it returns
  `"tok_" + secrets.token_hex(8)` (20 chars, 64 bits of entropy). Added
  `generate_unique_token()` in `app/services/vault.py` which retries against
  `vault.patient_vault.token` like the ID generators above. `upsert_patient_vault()` now uses
  `RETURNING token` so existing patients keep their original token on re-ingest (the
  `ON CONFLICT DO UPDATE` clause no longer touches `token`). Updated
  `backend/tests/test_ids.py` (token is now unique per call, not deterministic) and added
  retry coverage in `backend/tests/test_unique_ids.py`.

---

## BUG-007 — `email_quotation()` SMTP client has no port/auth/TLS support

- **Status:** 🟡 Open
- **Severity:** Medium (Module 2 billing emails will fail against any real SMTP provider)
- **Component:** `backend/app/services/billing.py` (`email_quotation`), `backend/app/config.py`
- **Description:** `email_quotation()` connects via `smtplib.SMTP(settings.smtp_host)` with no
  port, no authentication, and no TLS/STARTTLS. `config.py` only defines `smtp_host` — there are
  no `smtp_port`, `smtp_user`, `smtp_password`, or `smtp_use_tls` settings. This works against an
  unauthenticated dev relay (e.g. Mailpit/MailHog on port 1025) but will fail against any real
  provider (Postfix, AWS SES, SendGrid, Brevo, etc.), which require port 587/465 + STARTTLS/SSL +
  login credentials.
- **Fix direction:** Add `smtp_port` (default `587`), `smtp_user`, `smtp_password`, and
  `smtp_use_tls` (default `true`) to `config.py`/`.env(.example)`, and update `email_quotation()`
  to connect via `smtplib.SMTP(host, port)` + `starttls()` + `login(user, password)` when
  credentials are configured — falling back to the current unauthenticated/no-TLS path for local
  dev relays (Mailpit) where `smtp_user`/`smtp_password` are blank.
- **Owner:** Developer, alongside Module 2 billing work.

---

## Notes for reviewers

- This file is reviewed during the Team Lead's weekly sign-off
  ([team/TEAM_LEAD.md](../team/TEAM_LEAD.md)).
- New findings during Module 1+ implementation review should be appended here with the next
  sequential `BUG-NNN` ID, severity, affected component, description, and fix/status.
- Security-specific findings should also cross-reference the relevant checklist item in
  [SECURITY.md §9](SECURITY.md#9-pre-merge-security-checklist).
