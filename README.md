# treatment_plan_tracker

## Documentation

Project documentation lives in [`docs/`](docs/):

- [DESIGN.md](docs/DESIGN.md) — high-level design reference
- [Orbs_Implementation_Guide.md](docs/Orbs_Implementation_Guide.md) — full implementation guide
- [PROGRESS.md](docs/PROGRESS.md) — build status vs. the module/build plan
- [SECURITY.md](docs/SECURITY.md) — security & HIPAA controls
- [HIPAA.md](docs/HIPAA.md) — HIPAA compliance checklist (technical + organizational gaps, BAA status)
- [EVALUATION.md](docs/EVALUATION.md) — evaluation/test plan
- [OBSERVABILITY.md](docs/OBSERVABILITY.md) — logging, audit trails, metrics
- [CHANGELOG.md](docs/CHANGELOG.md) — change log
- [BUGS.md](docs/BUGS.md) — bug tracker

Per-module implementation breakdowns are in [`agents/`](agents/); team roles/conventions are in
[`team/`](team/).

## Module 1: Foundations & Storage

Backend service code lives in `backend/`. It provides the FastAPI skeleton, PostgreSQL schemas,
Alembic migration, pgcrypto vault helpers, seed data, plan storage, and enrollment services.

Local setup:

```bash
cp .env.example .env
# Fill DB_PASSWORD and KMS_KEY at minimum.
docker compose up -d db backend
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
```

Focused checks:

```bash
uv run --with-requirements backend/requirements.txt pytest backend/tests
cd backend && uv run --with-requirements requirements.txt alembic upgrade head --sql
```

## Module 2: Ingestion & Billing

The ingestion API accepts a redacted processing PDF, extracts text, parses the 10-orb plan,
validates it, builds/logs a quotation, and stores the plan as `pending_enrollment`.

Endpoints:

```bash
POST /api/ingest
POST /api/plans/{plan_id}/confirm-billing
GET  /api/quotations
```

`POST /api/ingest` accepts multipart form data with `file=<processing.pdf>`. For clinical
workflows that also need to create or update vault PII, pass optional `pii_json` as a JSON object;
otherwise ingestion stores only the redacted `patient_id` from the processing PDF.

AI configuration:

```bash
AI_OCR_PROVIDER=mistral       # uses Mistral when MISTRAL_API_KEY is set; otherwise local PDF text
AI_PARSER_PROVIDER=openai     # uses OpenAI when OPENAI_API_KEY is set; use "ollama" for local LLM
OLLAMA_BASE_URL=http://localhost:11434
```

Billing email is intentionally sparse: it includes quote/plan/patient tokens and a portal link,
but not diagnosis or line-item detail.

## Module 3: Tracking & Checkpoints

Tracking endpoints:

```bash
GET  /api/dashboard
GET  /api/patients/{patient_id}
GET  /api/at-risk
POST /api/orbs/{orb_ref}/complete
POST /api/orbs/{orb_ref}/status
```

`POST /api/orbs/{orb_ref}/complete` accepts optional JSON `{"notes": "..."}`.
`POST /api/orbs/{orb_ref}/status` accepts `pending`, `in_progress`, or `skipped`.
Both endpoints reject updates when the parent plan is `closed`.

Checkpoint scheduler flags:

```bash
ENABLE_CHECKPOINT_SCHEDULER=false
CHECKPOINT_CRON_HOUR=8
CHECKPOINT_GRACE_ANY_ORB=true
```

When enabled, the scheduler evaluates every non-closed plan daily. It writes patient/clinic
alerts to `app.alert_log`, transitions plans through `active`, `in_grace`, `extended`,
`completed`, and `closed`, and locks incomplete orbs at hard stop until Module 4 expands closure
reporting.

## Module 4: Frontend, Closure & Auth

Auth:

```bash
POST /api/auth/login
```

Demo users are `clinician`, `coordinator`, `billing`, and `patient`. Set their passwords in
`.env` with `DEMO_CLINICIAN_PASSWORD`, `DEMO_BILLING_PASSWORD`, and `DEMO_PATIENT_PASSWORD`.
All clinical API routes require a bearer token. `/health`, `/docs`, and `/api/auth/login` remain
open.

Reports:

```bash
GET /api/plans/{plan_id}/report
```

At hard stop, `close_plan()` closes the plan, locks incomplete orbs, writes final patient/clinic
alerts, and generates a completion PDF containing orb outcomes, alert history, and derived
adherence metrics from notes.

Frontend:

```bash
cd frontend
npm install
npm run build
```

Docker Compose now includes the frontend at `http://localhost:3000`. The React app includes login,
clinic dashboard, at-risk panel, patient detail/orb controls, upload, quotation confirmation, and
completion report download.

Local dev uses [Mailpit](https://github.com/axllent/mailpit) as the SMTP relay (`SMTP_HOST=mailpit`
in `docker-compose.yml`) — no real email is sent. View caught quotation emails at
http://localhost:8025. Note: `email_quotation()` currently has no port/auth/TLS support
(BUG-007), so it only works against an unauthenticated relay like Mailpit until that's fixed.
