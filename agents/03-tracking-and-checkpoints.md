# Module 3 — Live Tracking & Checkpoint State Machine

**Build phases covered:** 5 (Tracking API), 6 (Checkpoints)

**Goal:** Let patients complete orbs, expose dashboard/at-risk queries for the clinic, and run
a daily cron that evaluates each active plan against the checkpoint state machine — firing
alerts and transitioning plan status.

**Depends on:** Module 1 (`app.treatment_plans`, `app.patient_orbs`, `app.alert_log` schemas,
enrollment output). Calls into Module 4's `close_plan()` at checkpoint 4.

---

## 1. Implementation Steps

### Step 1 — Repository pieces for this module

```
backend/app/
├── routers/
│   ├── orbs.py
│   └── dashboard.py
├── services/
│   └── checkpoints.py    # state machine
└── scheduler.py           # APScheduler 08:00 cron
```

### Step 2 — Stage 5: Mark an orb complete (`services`/`routers/orbs.py`)

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

Also implement a sibling endpoint to set other statuses (`in_progress`, `skipped`) with the
same closed-plan guard.

### Step 3 — Dashboard query (`routers/dashboard.py`)

All active plans with completion counts + status:

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

### Step 4 — At-risk query (drives the alert panel)

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

### Step 5 — Endpoints for this module

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/dashboard` | All active plans with completion counts + status |
| `GET` | `/api/patients/{patient_id}` | Single plan detail with per-orb status |
| `POST` | `/api/orbs/{orb_ref}/complete` | Mark an orb complete |
| `POST` | `/api/orbs/{orb_ref}/status` | Set orb status (in_progress, skipped) |
| `GET` | `/api/at-risk` | Patients <5 orbs and ≤7 days remaining |

**Output of Stage 5:** live progress visible on dashboard; checkpoints fire alerts and
transition state (Step 6 onward).

---

## 2. The Checkpoint State Machine

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

### Step 6 — Implement `services/checkpoints.py`

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

`alert_patient` / `alert_clinic` should write to `app.alert_log` (recipient, checkpoint,
message, sent_at) in addition to sending the notification.

`close_plan()` is implemented in Module 4 (Stage 6 — Closure); this module only needs to call it.

### Step 7 — `scheduler.py`: daily 08:00 cron

Use APScheduler to run `evaluate_plan_checkpoints(plan, db)` for every plan where
`status NOT IN ('closed')`, once per day at 08:00.

### Step 8 — Open design questions (configurable)

Build these as config flags rather than hardcoding, so they can be revisited without code changes:

1. **IN_GRACE vs EXTENDED** — currently distinct (8–9 = light touch, <8 = outreach call). Could
   merge into one EXTENDED state if the outreach distinction is not operationally useful.
2. **Grace-week completion scope** — should the patient be able to complete *any* orb during the
   grace week, or only the specific orbs flagged incomplete at day 14? Current default: any orb.

---

## 3. Deliverable

- `complete_orb` and orb-status endpoints enforce the closed-plan lock.
- `/api/dashboard`, `/api/patients/{patient_id}`, `/api/at-risk` return live data matching the
  queries above.
- Daily cron evaluates every active plan, writes to `app.alert_log`, and correctly transitions
  `active → in_grace/extended/completed`, calling Module 4's `close_plan()` at hard stop.
