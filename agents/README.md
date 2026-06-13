# Agent Modules — 10 Orbs to Better

This folder splits [`Orbs_Implementation_Guide.md`](../docs/Orbs_Implementation_Guide.md) into four self-contained
implementation modules, each scoped for an individual build agent. Together they cover the full
MVP described in the original guide (Build Sequence phases 1–9).

| Module | File | Scope | Guide Build Phases |
|--------|------|-------|---------------------|
| 1 | [01-foundations-and-storage.md](01-foundations-and-storage.md) | DB schemas, vault encryption, ID generators, Plan Creation, Tokenization & Storage, Enrollment | 1–2 |
| 2 | [02-ingestion-and-billing.md](02-ingestion-and-billing.md) | PDF OCR/parsing, validation gate, billing quotation pipeline | 3–4 |
| 3 | [03-tracking-and-checkpoints.md](03-tracking-and-checkpoints.md) | Orb completion, dashboard/at-risk queries, checkpoint state machine, daily cron | 5–6 |
| 4 | [04-frontend-closure-and-auth.md](04-frontend-closure-and-auth.md) | React frontend, plan closure & reporting, JWT auth | 7–9 |

## Shared Reference

### System Architecture

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

### Technology Stack

| Layer | Choice |
|-------|--------|
| API framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| DB driver | asyncpg |
| Migrations | Alembic |
| Scheduler | APScheduler |
| Auth | python-jose (JWT) |
| Validation | Pydantic v2 |
| Encryption | pgcrypto (Postgres ext.) |
| Frontend framework | React 18 + Vite |
| Data fetching | TanStack Query |
| Styling | Tailwind CSS + shadcn/ui |
| Charts | Recharts |
| OCR | Mistral OCR (paid) / Tesseract+docTR (free) |
| Parsing | OpenAI GPT-4o (paid) / Ollama + Llama 3.1 8B (free) |
| Infra | Docker Compose: `frontend`, `backend`, `db` |

### MVP Cut Line

Modules 1–3 plus the frontend portion of Module 4 (phases 1–7) are enough for the smallest demoable
version: ingest a PDF, see orbs on the dashboard, mark them complete, and watch the daily checkpoint
move a plan into grace/extended/completed. Closure reporting and full auth (rest of Module 4) can follow.
