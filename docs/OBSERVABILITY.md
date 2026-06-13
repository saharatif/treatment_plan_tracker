# Observability — 10 Orbs to Better

This document defines how the running system is monitored: logs, audit trails, metrics, and
alerting. It complements [`SECURITY.md`](SECURITY.md) (what must *not* be logged) and
[`EVALUATION.md`](EVALUATION.md) (pre-release correctness checks).

---

## 1. Structured Logging

All services emit structured (JSON) logs, per `../team/DEVELOPER.md`'s "consistent structured
logging" guidance. Minimum fields on every log line:

| Field | Example | Notes |
|-------|---------|-------|
| `timestamp` | ISO 8601 UTC | |
| `level` | `info` / `warn` / `error` | |
| `service` | `ingest`, `parser`, `billing`, `checkpoints`, `vault`, `api` | |
| `request_id` | UUID | Propagated through OCR → parser → validation → billing for a single ingest |
| `patient_token` | `PAT-2025-00847` | **Token only — never name/DOB** (see SECURITY.md §1) |
| `plan_id` | `PLN-2025-003` | Where applicable |

**Never log:** raw OCR/PDF text, LLM prompts/responses containing PHI, API keys, JWTs, DB
connection strings, SMTP credentials. Redact at the logging boundary, not ad hoc per call site.

---

## 2. Audit Trails (application-level, persisted)

These are the system's permanent record of sensitive operations — distinct from transient
service logs above. All three are referenced in [DESIGN.md §7](DESIGN.md#7-security--compliance).

| Table | Written by | What it captures |
|-------|-----------|-------------------|
| `vault.patient_vault.access_log` | `vault.py` accessor | Every read of encrypted PII: who, when, which token, which field |
| `app.alert_log` | `evaluate_plan_checkpoints()` | Checkpoint transitions, warning/escalation alerts, with plan_id + day |
| `billing.quotation_log` | `build_quotation()` | Full quote snapshot (JSONB), token only |

These tables should be queryable for ops/compliance review (e.g. "show all vault accesses for
token PAT-2025-00847 in the last 30 days") and are append-only — see SECURITY.md §4.

---

## 3. Key Operational Metrics

| Area | Metric | Why it matters |
|------|--------|-----------------|
| **Ingestion** | `ingest.requests` (count, success/fail) | Pipeline throughput and failure rate |
| | `ingest.validation_failures` (rate) | Spike indicates OCR/parser drift or a malformed-input pattern; failed plans go to review queue |
| | `ocr.latency`, `ocr.errors` (per provider: Mistral/Tesseract) | External API health; informs free vs. paid fallback decisions |
| | `parser.latency`, `parser.errors` (per provider: GPT-4o/Ollama) | Same as above |
| | `parser.catalog_match_rate` | % of extracted orbs successfully matched to `app.orbs` via `match_catalog_orb()` — low rate suggests prompt/catalog drift (see EVALUATION.md §1.2) |
| **Billing** | `billing.quotations_sent` (count) | |
| | `billing.unmatched_codes` (count/rate) | Per SECURITY.md §5, unmatched codes are flagged not dropped — a rising rate signals a `billing_codes` gap |
| | `billing.needs_auth_count` | Volume of prior-auth items needing follow-up |
| | `billing.email_failures` | SMTP delivery failures — quotes stuck without notifying billing |
| **Tracking / Checkpoints** | `checkpoint.cron_run` (success/fail, duration) | The daily 08:00 job is the system's heartbeat for plan state — a missed run delays every transition |
| | `checkpoint.transitions` (count by from→to state) | Volume of `ACTIVE→IN_GRACE`, `→EXTENDED`, `→COMPLETED`, `→CLOSED` |
| | `dashboard.at_risk_count` | Trend of patients <5 orbs / ≤7 days remaining |
| **API** | `api.request_count`, `api.latency`, `api.error_rate` (per route) | Standard FastAPI service health |
| | `api.auth_failures` (401/403 rate) | Spike may indicate expired tokens, misconfigured roles, or probing |
| **Database** | `db.connection_pool_usage`, `db.query_latency` | asyncpg pool exhaustion is a common FastAPI failure mode |

---

## 4. Health Checks

| Check | Endpoint / mechanism | Failure response |
|-------|----------------------|-------------------|
| API liveness | `GET /health` (to add to `backend/app/main.py`) | Container restart |
| DB connectivity | `/health` checks a trivial `SELECT 1` against Postgres | Alert — system can't store/read plans |
| Scheduler heartbeat | `/health` (or separate `/health/scheduler`) reports last successful checkpoint cron run timestamp | Alert if >25h since last run (daily 08:00 job) |
| AI provider reachability | Optional `/health/dependencies` pings Mistral/OpenAI (or confirms local Ollama/Tesseract availability) | Degrade to free-tier fallback, alert |

---

## 5. Alerting

| Condition | Severity | Action |
|-----------|----------|--------|
| Daily checkpoint cron fails or doesn't run | High | Page on-call — plan state stalls system-wide |
| `ingest.validation_failures` rate exceeds baseline | Medium | Review queue backing up; check OCR/parser provider status |
| `billing.email_failures` > 0 | Medium | Billing not notified of pending quotes — check SMTP config |
| `billing.unmatched_codes` rate increase | Medium | Possible `billing.billing_codes` gap or OCR drift |
| `api.auth_failures` spike | Medium | Possible credential issue or probing |
| OCR/LLM provider error rate spike | Low–Medium | Confirm free-tier fallback (Tesseract/Ollama) is viable |
| `vault.access_log` write failure | High | Audit trail gap — treat as a compliance incident |

---

## 6. Dashboards (suggested layout)

1. **Pipeline health** — ingest request volume, validation pass/fail rate, OCR/parser latency
   and error rate (paid vs. free provider).
2. **Billing** — quotations sent, unmatched codes, needs-auth volume, email delivery success.
3. **Plan lifecycle** — count of plans per `PlanStatus` (`ACTIVE`, `IN_GRACE`, `EXTENDED`,
   `COMPLETED`, `CLOSED`), checkpoint cron run history, at-risk trend.
4. **API/infra** — request rate, latency percentiles, error rate by route, DB pool usage.

---

## 7. Open Items

- Choose a logging/metrics stack (e.g. structured JSON logs to stdout + a collector; Prometheus
  for metrics) — not yet decided, add here once chosen.
- `GET /health` and `/health/scheduler` endpoints don't exist yet — add when Module 3's
  scheduler (`../agents/03-tracking-and-checkpoints.md`) is implemented.
- Define alert routing (who gets paged for High severity) once the team has an on-call rotation.
