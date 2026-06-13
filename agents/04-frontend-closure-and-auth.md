# Module 4 — Frontend, Closure & Auth

**Build phases covered:** 7 (Frontend), 8 (Closure), 9 (Auth + polish)

**Goal:** Build the React clinic dashboard/upload/patient-detail UI, implement plan closure
with completion reporting, and add JWT auth with role-based gating across the API.

**Depends on:** Module 1 (schemas, vault), Module 2 (`/api/ingest`, `/api/quotations`),
Module 3 (`/api/dashboard`, `/api/at-risk`, `/api/orbs/*`, `evaluate_plan_checkpoints`
calls `close_plan` from this module at checkpoint 4).

---

## 1. Implementation Steps

### Step 1 — Repository pieces for this module

```
backend/app/
├── auth.py               # JWT issue/validate
└── services/
    └── reports.py         # completion report PDF

frontend/
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

### Step 2 — Stage 6: Closure (`services/close_plan` + `services/reports.py`)

At the hard stop (checkpoint 4, evaluated by Module 3's cron), the plan closes regardless of
completion.

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

**Completion report (PDF) includes:** final orb count, completed vs incomplete orbs, the full
alert history (from `app.alert_log`), glucose log average, exercise days, medication adherence.
It attaches to the patient record and is reviewed at the next visit — which begins a **new
plan** (returning to Stage 1 / Module 1).

`generate_completion_report` lives in `services/reports.py` and should pull:
- orb completion counts/status from `app.patient_orbs`
- alert history from `app.alert_log`
- adherence metrics (glucose log average, exercise days, medication adherence) from orb
  `notes`/status fields

**Output:** plan `closed`, orbs locked, completion report generated.

### Step 3 — Reporting endpoint

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/plans/{plan_id}/report` | Generate/fetch completion report |

### Step 4 — Auth (`auth.py`)

Implement JWT issuance and validation with `python-jose`:

- Login endpoint issues a JWT (role embedded: clinician, billing, coordinator, etc.).
- Dependency-injected `get_current_user` validates the bearer token on every route.
- Role-based gating: e.g. `/api/quotations` and `/api/patients/{id}` (PII-adjacent) restricted
  to clinic/billing roles; patient-facing orb-completion endpoints scoped to that patient's token.
- All endpoints require a JWT bearer token. FastAPI serves interactive docs at `/docs`.

### Step 5 — Frontend setup

```
React 18 + Vite + Tailwind CSS + shadcn/ui (cards, badges, progress bars) + TanStack Query + Recharts
```

`api/client.ts` — TanStack Query hooks:
- `useDashboard()` — polls `GET /api/dashboard` every 30s.
- `useAtRisk()` — `GET /api/at-risk`.
- `usePatientDetail(patientId)` — `GET /api/patients/{patient_id}`.
- `useCompleteOrb()` / `useSetOrbStatus()` — mutations against `/api/orbs/{orb_ref}/...`,
  invalidating the dashboard query on success.
- `useUploadPlan()` — mutation against `POST /api/ingest`.
- `useQuotations()` — `GET /api/quotations`.
- `useCompletionReport(planId)` — `GET /api/plans/{plan_id}/report`.
- Attach the JWT (Step 4) as a bearer header on every request; redirect to login on 401.

### Step 6 — Pages

- **`Dashboard.tsx`** — clinic dashboard: list of plans with `MetricCard`s, `StatusBadge` per
  plan_status (ON TRACK / IN GRACE / OVERDUE), and the at-risk `AlertPanel`.
- **`PatientDetail.tsx`** — per-orb history using `OrbRow` (10-dot progress), notes, and
  per-orb status controls (complete / in_progress / skipped) wired to Module 3's endpoints.
  Show the billing tab (quotations for this plan) and, once closed, the completion report.
- **`Upload.tsx`** — PDF ingest UI calling `POST /api/ingest` (Module 2), showing validation
  errors (review queue) or the resulting quotation for confirmation
  (`POST /api/plans/{plan_id}/confirm-billing`).

### Step 7 — Components

- **`OrbRow.tsx`** — renders the 10-dot progress row, color-coded by orb status
  (pending/in_progress/complete/skipped/locked).
- **`StatusBadge.tsx`** — small colored badge for plan_status / orb status.
- **`MetricCard.tsx`** — summary stat card (e.g., completed count, days remaining).
- **`AlertPanel.tsx`** — renders the at-risk list and recent `alert_log` entries.

### Step 8 — Frontend Dockerfile + compose wiring

Add `frontend` service to `docker-compose.yml` (already declared in Module 1's compose file,
port `3000:80`, `depends_on: [backend]`). Build with Vite, serve via the Dockerfile's static
server.

---

## 2. Full API Reference (for context — endpoints owned by other modules are marked)

| Method | Endpoint | Purpose | Owner |
|--------|----------|---------|-------|
| `POST` | `/api/ingest` | Upload processing PDF → OCR → parse → quote → store | Module 2 |
| `GET` | `/api/dashboard` | All active plans with completion counts + status | Module 3 |
| `GET` | `/api/patients/{patient_id}` | Single plan detail with per-orb status | Module 3 |
| `POST` | `/api/orbs/{orb_ref}/complete` | Mark an orb complete | Module 3 |
| `POST` | `/api/orbs/{orb_ref}/status` | Set orb status (in_progress, skipped) | Module 3 |
| `GET` | `/api/at-risk` | Patients <5 orbs and ≤7 days remaining | Module 3 |
| `GET` | `/api/plans/{plan_id}/report` | Generate/fetch completion report | **Module 4** |
| `POST` | `/api/plans/{plan_id}/confirm-billing` | Billing confirms quote → triggers enrollment | Module 2 |
| `GET` | `/api/quotations` | Quotation log (billing view) | Module 2 |

All endpoints require a JWT bearer token (**Module 4**, Step 4).

---

## 3. HIPAA / Security touchpoints owned by this module

| Control | Implementation |
|---------|----------------|
| Access controls | JWT auth + role-based endpoints (Step 4) |
| Audit trail | `app.alert_log` surfaced in `AlertPanel`; completion report aggregates it |
| Minimum necessary | Frontend never requests/displays raw PII — tokens (`PAT-2025-00847`) only |

---

## 4. Deliverable

- `close_plan()` locks incomplete orbs, generates the completion PDF report, and notifies
  patient + clinic.
- `/api/plans/{plan_id}/report` returns the generated report.
- JWT auth protects all endpoints with role-based gating.
- React app: Dashboard (live, 30s polling), Upload (ingest + billing confirmation),
  PatientDetail (per-orb tracking + report view) — completing the MVP described in the guide's
  Build Sequence.
