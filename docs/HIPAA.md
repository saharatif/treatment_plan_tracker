# HIPAA Compliance Checklist — 10 Orbs to Better

A working compliance checklist for the treatment-plan tracking system.

> **Disclaimer.** This is an engineering reference, not legal advice. HIPAA compliance is ~40% technical and ~60% organizational process. Before any real patient data enters the system, have a compliance officer or healthcare attorney review the deployment. Citations reference the HIPAA Security Rule (45 CFR Part 164).

---

## How to Use This Document

```
Phase 1 (Prototype):  Use SYNTHETIC data only.
                      HIPAA does not apply to fabricated patients.
                      Build and demo the full system freely.

Phase 2 (Pre-production): Close every technical gap below.

Phase 3 (Production):  Close every organizational gap +
                      sign all BAAs before the first real
                      patient record is ingested.
```

The single most important rule for the MVP: **never put real PHI into the prototype.** Use synthetic patients (e.g. "Marcus Elliot") for all development and demos.

---

## Quick Status Summary

| Area | Status | Notes |
|------|--------|-------|
| PII tokenization | Built | Vault pattern in place |
| Encryption at rest | Built | pgcrypto AES-256 |
| Encryption in transit | Built | TLS 1.3 |
| Audit logging | Built | access_log, alert_log, quotation_log |
| Access control | Built | JWT + role-based endpoints |
| BAA with AI vendor | **Gap** | Required — project uses Mistral OCR + OpenAI GPT-4o (cloud); both vendors need a signed BAA before real PHI enters the pipeline |
| PHI in email | **Gap** | Codes/dates in quotation email must move to secure link |
| Session timeout | **Gap** | Auto-logoff not yet implemented |
| Administrative safeguards | **Gap** | Officer, training, risk assessment, incident plan |
| Physical safeguards | **Gap** | Depends on hosting choice |

---

## 1. What Counts as PHI Here

HIPAA defines **18 identifiers**. Any of these, combined with health information, is Protected Health Information (PHI). The system touches several even after tokenization:

| # | Identifier | Present in system? |
|---|-----------|--------------------|
| 1 | Name | Vault only (encrypted) |
| 2 | Geographic data smaller than state | Vault only (address) |
| 3 | **Dates** (birth, admission, service) | **Yes — plan dates, visit dates** |
| 4 | Phone numbers | Vault only |
| 6 | Email addresses | Vault only |
| 7 | **Medical record numbers** | **Yes — plan_id, patient_id** |
| 8 | Health plan beneficiary numbers | Possibly (billing) |
| 18 | Any other unique identifying code | **Yes — tokens are re-linkable** |

### Critical distinction

```
De-identified (Safe Harbor, §164.514):
  ALL 18 identifiers removed → NOT PHI → HIPAA does not apply

Pseudonymized (this system's vault pattern):
  PII swapped for a re-linkable token → STILL PHI
  → HIPAA fully applies

The token PAT-2025-00847 re-links to the patient via the vault.
That re-linkability means tokenized data is still legally PHI.
Tokenization is good practice — but it does NOT remove HIPAA obligations.
```

---

## 2. Technical Safeguards (§164.312)

### 2.1 Access Control — §164.312(a)(1)

- [x] Unique system access via JWT
- [ ] **Unique user identification** — every user has their own account; no shared logins — §164.312(a)(2)(i)
- [ ] **Automatic logoff** — session timeout after inactivity — §164.312(a)(2)(iii)
- [x] Role-based endpoint authorization (clinician / billing / admin)
- [ ] Emergency access procedure documented — §164.312(a)(2)(ii)

### 2.2 Audit Controls — §164.312(b)

- [x] `alert_log` — every checkpoint alert recorded
- [x] `quotation_log` — every quotation recorded
- [x] Vault `access_log` — who read PHI, when
- [ ] **Log every PHI read/write**, not just vault access — include who viewed a patient detail page
- [ ] Logs are tamper-resistant (append-only or write-once storage)
- [ ] Log retention policy defined (HIPAA: 6 years for related documentation)

### 2.3 Integrity — §164.312(c)(1)

- [ ] Mechanism to detect improper PHI alteration (checksums, row versioning, or DB audit triggers)
- [ ] Backups verified and restorable

### 2.4 Transmission Security — §164.312(e)(1)

- [x] TLS 1.3 on all API traffic
- [ ] **No PHI in plain email** — see Section 4
- [ ] Internal service-to-service traffic also encrypted

### 2.5 Encryption — §164.312(a)(2)(iv)

- [x] AES-256 at rest via pgcrypto on vault columns
- [ ] Customer-managed KMS key (not hardcoded in env for production)
- [ ] Key rotation policy defined
- [ ] Encrypted database backups

---

## 3. AI Vendor & Business Associate Agreements (§164.308(b))

This is the highest-priority gap.

```
The redacted processing PDF still contains PHI:
  - Service dates (identifier #3)
  - Plan / record numbers (identifier #7)
  - Diagnoses and treatment details

Sending it to any third-party AI = disclosing PHI to a
Business Associate = a signed BAA is REQUIRED.
```

### Checklist

- [ ] BAA signed with OCR vendor — **Mistral** (chosen for this project, see
  [`agents/02-ingestion-and-billing.md` §1](../agents/02-ingestion-and-billing.md#1-ai-layer))
  **OR** OCR runs locally (Tesseract / docTR)
- [ ] BAA signed with LLM vendor — **OpenAI** (chosen for this project) **OR** LLM runs
  locally (Ollama)
- [ ] BAA signed with cloud host (AWS / Azure / GCP all offer BAAs)
- [ ] BAA signed with email provider (if email carries any PHI)
- [ ] BAA inventory maintained — list of every vendor touching PHI

### Project decision: Mistral OCR + OpenAI GPT-4o

```
This project's chosen AI stack is Mistral OCR (text extraction) +
OpenAI GPT-4o (structured parsing) — see agents/02-ingestion-and-billing.md §1.

This is the cloud path, not the fully-local path below, so:
  → BAAs with BOTH Mistral and OpenAI are REQUIRED before any real PHI
    is sent through the pipeline.
  → Until both BAAs are signed, continue using synthetic data only
    (the Marcus Elliot fixture).

The redacted _processing.pdf remains the primary control — it limits
what PHI these vendors ever see (no name, no DOB, no contact info;
only dates, record numbers, and clinical content). Both vendors must
still be added to the BAA inventory above.
```

### Fully-local alternative (fallback if a BAA can't be secured)

```
  OCR     → Tesseract / docTR  (runs on your server)
  Parsing → Ollama + Llama 3.1 (runs on your server)

Result: NO PHI leaves your infrastructure
        → NO BAA needed for the AI layer
        → removes the single hardest compliance obstacle

Documented in agents/02-ingestion-and-billing.md Step 8 as a fallback
if the Mistral/OpenAI BAAs cannot be obtained before production.
```

---

## 4. Email & Billing Channel

```
Current design risk:
  Quotation email contains diagnoses, procedure codes, dates.
  Standard SMTP is frequently not end-to-end encrypted.
  Codes + dates + medical context = PHI in transit.
  → potential §164.312(e) violation
```

### Checklist

- [ ] Quotation email body contains **no clinical codes, no dates, no diagnoses**
- [ ] Email sends only: `quote_id` + secure login link
- [ ] Billing staff click through to the app to view the full quotation
- [ ] App-to-billing view is access-logged
- [ ] If email must carry PHI, it is encrypted (enforced TLS or secure portal)

### Recommended change

```
BEFORE (current):
  Subject: Quotation QTE-2025-003 — $330.00
  Body: full line items, diagnoses, dates...

AFTER (compliant):
  Subject: New quotation ready for review — QTE-2025-003
  Body: A treatment plan quotation is ready.
        View securely: https://app.../quotes/QTE-2025-003
        (No clinical detail in the email itself.)
```

---

## 5. Administrative Safeguards (§164.308)

These are organizational, not code. No codebase provides them — they must be put in place by the organization.

- [ ] **Security Officer designated** — a named person responsible for HIPAA — §164.308(a)(2)
- [ ] **Risk assessment** conducted and documented — §164.308(a)(1)(ii)(A)
- [ ] **Risk management plan** — how identified risks are mitigated — §164.308(a)(1)(ii)(B)
- [ ] **Workforce training** on PHI handling — §164.308(a)(5)
- [ ] **Sanction policy** for workforce violations — §164.308(a)(1)(ii)(C)
- [ ] **Incident response plan** — detect, respond to, document breaches — §164.308(a)(6)
- [ ] **Contingency plan** — data backup, disaster recovery, emergency mode — §164.308(a)(7)
- [ ] **Access authorization procedure** — how access is granted/revoked — §164.308(a)(4)
- [ ] **Periodic evaluation** of safeguards — §164.308(a)(8)

---

## 6. Physical Safeguards (§164.310)

- [ ] Hosting is a HIPAA-eligible environment (AWS/Azure/GCP HIPAA-eligible services, under BAA)
- [ ] Facility access controls documented (handled by compliant cloud provider)
- [ ] Workstation use policy — who can access the app and from where — §164.310(b)
- [ ] Device and media disposal policy — secure wipe of any storage holding PHI — §164.310(d)(1)

---

## 7. Breach Notification Rule (§164.400–414)

- [ ] Breach detection process exists (tied to audit logs)
- [ ] Breach notification procedure documented:
  - Notify affected individuals within 60 days
  - Notify HHS
  - Notify media if breach affects 500+ individuals
- [ ] Breach risk assessment template ready

---

## 8. Minimum Necessary Principle (§164.502(b))

The system already follows this well — maintain it.

- [x] Tokens used everywhere instead of PII
- [x] PII fetched from vault only when genuinely needed
- [ ] Each role sees only the PHI it needs (billing sees codes, not full clinical notes; etc.)
- [ ] Dashboard shows tokens, never names

---

## 9. Prototype-to-Production Gate

A hard checklist before the **first real patient record** enters the system.

```
DO NOT ingest real PHI until ALL of these are true:

  □ All BAAs signed (AI, cloud, email) OR AI runs fully local
  □ Email carries no PHI (secure-link pattern live)
  □ Session timeout + per-user accounts implemented
  □ Customer-managed KMS key (no hardcoded secrets)
  □ Audit logging covers every PHI read/write
  □ Risk assessment documented
  □ Security officer designated
  □ Incident response plan written
  □ Workforce trained
  □ Hosting is HIPAA-eligible and under BAA
  □ Backups encrypted and restore-tested
```

Until every box is checked: **synthetic data only.**

---

## 10. Summary

```
Does the project contradict HIPAA?
  No. The architecture is privacy-first and compatible.

Is it compliant as currently built?
  Not yet. Three technical gaps and the organizational
  safeguards must close first:

  1. BAA with Mistral (OCR) and OpenAI (parsing) — the project's chosen
     AI vendors — or fall back to fully local (Ollama/Tesseract)
  2. Remove PHI from email (secure-link pattern)
  3. Add administrative + physical safeguards

Recommended path:
  Build and demo the entire MVP with synthetic data.
  HIPAA does not apply to fabricated patients, so the
  full system can be developed freely. Close the BAA and
  organizational gaps before any real record is ingested.
```

---

## Appendix — Quick Reference: Cited Sections

| Section | Topic |
|---------|-------|
| §164.308 | Administrative safeguards |
| §164.310 | Physical safeguards |
| §164.312 | Technical safeguards |
| §164.312(a) | Access control |
| §164.312(b) | Audit controls |
| §164.312(c) | Integrity |
| §164.312(e) | Transmission security |
| §164.502(b) | Minimum necessary |
| §164.514 | De-identification (Safe Harbor) |
| §164.400–414 | Breach notification |

---

*End of HIPAA compliance checklist.*
