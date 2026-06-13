# Module 1 — Foundations & Storage Core

**Build phases covered:** 1 (Foundations), 2 (Storage core)

**Goal:** Get the database up with all three schemas migrated and seeded, implement PII
tokenization/vault encryption, and build the plan-creation → tokenization → enrollment pipeline
that every other module depends on.

---

## 1. Data Model

Three PostgreSQL schemas keep concerns separated: `vault` (encrypted PII, isolated),
`app` (treatment data, no PII), and `billing`.

### Schema: `vault` (encrypted PII — isolated)

```sql
CREATE SCHEMA vault;

CREATE TABLE vault.patient_vault (
    patient_id        VARCHAR(20) PRIMARY KEY,   -- PAT-2025-00847
    token             VARCHAR(50) UNIQUE,         -- tok_mje_8f3a2c
    name_encrypted    BYTEA,                      -- pgp_sym_encrypt
    dob_encrypted     BYTEA,
    address_encrypted BYTEA,
    phone_encrypted   BYTEA,
    email_encrypted   BYTEA,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    access_log        JSONB DEFAULT '[]'          -- who read it, when
);
```

### Schema: `app` (treatment data — no PII)

```sql
CREATE SCHEMA app;

CREATE TABLE app.treatment_plans (
    plan_id        VARCHAR(20) PRIMARY KEY,       -- PLN-2025-003
    patient_id     VARCHAR(20) NOT NULL,          -- FK to vault (token only)
    provider       VARCHAR(200),
    plan_start     DATE NOT NULL,
    duration_days  INT  NOT NULL DEFAULT 14,
    buffer_days    INT  NOT NULL DEFAULT 3,
    extension_days INT  NOT NULL DEFAULT 7,
    target_date    DATE NOT NULL,                 -- start + duration
    hard_stop      DATE NOT NULL,                 -- target + extension
    next_visit     DATE,
    status         VARCHAR(20) DEFAULT 'active',  -- state machine
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE app.diagnoses (
    id           SERIAL PRIMARY KEY,
    plan_id      VARCHAR(20) REFERENCES app.treatment_plans(plan_id),
    code         VARCHAR(20),                      -- E11.9
    description  TEXT,
    code_system  VARCHAR(20)                       -- ICD-10
);

CREATE TABLE app.orbs (
    id            SERIAL PRIMARY KEY,
    catalog_code  VARCHAR(20) UNIQUE NOT NULL,      -- e.g. LAB-01, MED-03
    title         VARCHAR(200) NOT NULL,
    category      VARCHAR(100) NOT NULL,            -- Lab, Medicine, Vitamins, Exercise,
                                                      -- Monitoring, Diet, Referral, Review
    description   TEXT,
    billing_codes VARCHAR(20)[]                      -- associated CPT/ICD-10/HCPCS codes
);

CREATE TABLE app.patient_orbs (
    orb_ref        VARCHAR(30) PRIMARY KEY,         -- ORB-PAT00847-001
    plan_id        VARCHAR(20) REFERENCES app.treatment_plans(plan_id),
    patient_id     VARCHAR(20) NOT NULL,
    orb_number     INT NOT NULL,                    -- 1..10, this plan's slot position
    catalog_orb_id INT REFERENCES app.orbs(id),     -- which catalog orb fills this slot
    status         VARCHAR(20) DEFAULT 'pending',   -- pending|in_progress|complete|skipped|locked
    target_date    DATE,
    completed_at   TIMESTAMPTZ,
    notes          TEXT,
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (plan_id, orb_number)
);

CREATE TABLE app.alert_log (
    id           SERIAL PRIMARY KEY,
    plan_id      VARCHAR(20),
    recipient    VARCHAR(20),                      -- 'patient' | 'clinic'
    checkpoint   VARCHAR(20),                      -- checkpoint_1 ... 4
    message      TEXT,
    sent_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Schema: `billing` (table shells only — Module 2 populates/uses these)

```sql
CREATE SCHEMA billing;

CREATE TABLE billing.billing_codes (
    id            SERIAL PRIMARY KEY,
    code          VARCHAR(20) UNIQUE NOT NULL,
    code_system   VARCHAR(20) NOT NULL,            -- CPT|ICD-10|HCPCS
    description   TEXT NOT NULL,
    unit_price    NUMERIC(10,2),
    medicare_rate NUMERIC(10,2),
    is_billable   BOOLEAN DEFAULT TRUE,            -- ICD-10 = FALSE
    requires_auth BOOLEAN DEFAULT FALSE,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE billing.quotation_log (
    quote_id     VARCHAR(20) PRIMARY KEY,          -- QTE-2025-003
    plan_id      VARCHAR(20),
    total        NUMERIC(10,2),
    sent_to      VARCHAR(200),
    sent_at      TIMESTAMPTZ DEFAULT NOW(),
    payload      JSONB                             -- full quote snapshot
);
```

---

## 2. Implementation Steps

### Step 1 — Backend skeleton & Docker Compose

Create the repo skeleton (shared by all modules):

```
orbs-mvp/
├── docker-compose.yml
├── README.md
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── alembic/                  # migrations
    └── app/
        ├── main.py               # FastAPI app + CORS + routers
        ├── config.py             # env settings (Pydantic Settings)
        ├── database.py           # async engine + session
        └── models.py             # SQLAlchemy models (3 schemas)
```

`docker-compose.yml`:

```yaml
version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: orbs
      POSTGRES_USER: orbs
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init:/docker-entrypoint-initdb.d   # CREATE EXTENSION pgcrypto
    ports: ["5432:5432"]

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://orbs:${DB_PASSWORD}@db/orbs
      KMS_KEY: ${KMS_KEY}
      MISTRAL_API_KEY: ${MISTRAL_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      SMTP_HOST: ${SMTP_HOST}
      JWT_SECRET: ${JWT_SECRET}
    depends_on: [db]
    ports: ["8000:8000"]

  frontend:
    build: ./frontend
    depends_on: [backend]
    ports: ["3000:80"]

volumes:
  pgdata:
```

### Step 2 — Enable pgcrypto and run migrations

```bash
# Enable pgcrypto (init script)
echo "CREATE EXTENSION IF NOT EXISTS pgcrypto;" > init/01-extensions.sql

# Start everything
docker compose up -d

# Run migrations
docker compose exec backend alembic upgrade head

# Seed the 10 orb templates + billing codes
docker compose exec backend python -m app.seed
```

### Step 3 — Migrate all three schemas

Write the SQLAlchemy models (`models.py`) and an initial Alembic migration covering every table
in [Section 1](#1-data-model): `vault.patient_vault`, `app.treatment_plans`, `app.diagnoses`,
`app.orbs`, `app.patient_orbs`, `app.alert_log`, `billing.billing_codes`, `billing.quotation_log`.

### Step 4 — Seed data

`app.seed` should populate `app.orbs` with the **orb catalog** — multiple example orbs per
category. Each plan still selects exactly **10** of these (one per `patient_orbs.orb_number`
slot, 1–10) based on the patient's diagnoses and the codes parsed from their plan PDF.

#### Orb Catalog (`app.orbs`)

| Catalog Code | Title | Category | Billing Codes |
|--------------|-------|----------|---------------|
| LAB-01 | Blood Work — Baseline Labs | Lab | CPT 83036, 80053 |
| LAB-02 | Complete Blood Count (CBC) | Lab | CPT 85025 |
| LAB-03 | Thyroid Function Panel | Lab | CPT 84443 |
| LAB-04 | Fasting Blood Glucose Check | Lab | CPT 82947 |
| LAB-05 | Chest X-Ray — Diagnostic Imaging | Lab | CPT 71046 |
| MED-01 | Begin Metformin 500mg | Medicine | ICD-10 E11.9 |
| MED-02 | Begin Lisinopril 10mg | Medicine | ICD-10 I10 |
| MED-03 | Begin Albuterol Inhaler | Medicine | ICD-10 J44.1 |
| MED-04 | Begin SSRI for Depression | Medicine | ICD-10 F32.9 |
| VIT-01 | Daily Multivitamin Protocol | Vitamins | — |
| VIT-02 | Vitamin D Supplementation | Vitamins | — |
| VIT-03 | Iron Supplementation | Vitamins | ICD-10 K92.1 |
| EXR-01 | First 20-Minute Walk | Exercise | — |
| EXR-02 | 7-Day Exercise Streak | Exercise | — |
| EXR-03 | Physical Therapy — Therapeutic Exercises | Exercise | CPT 97110 |
| EXR-04 | Physical Therapy — Manual Therapy | Exercise | CPT 97140 |
| MON-01 | Blood Sugar Logging — 7 Days | Monitoring | HCPCS A4253 |
| MON-02 | Blood Pressure Logging — 7 Days | Monitoring | ICD-10 I10 |
| MON-03 | CPAP Compliance Tracking | Monitoring | HCPCS E0601 |
| MON-04 | Weight & Symptom Journal | Monitoring | — |
| DIE-01 | Nutrition Overhaul — 7 Days | Diet | — |
| DIE-02 | Low-Sodium Diet Plan | Diet | ICD-10 I10, I25.10 |
| DIE-03 | Diabetic Meal Planning | Diet | ICD-10 E11.9 |
| REF-01 | Book Specialist Referrals | Referral | ICD-10 Z01.01, Z01.89 |
| REF-02 | Cardiology Referral | Referral | ICD-10 I25.10 |
| REF-03 | Orthopedic Referral — Knee | Referral | ICD-10 M17.11 |
| REF-04 | Behavioral Health Referral | Referral | ICD-10 F41.1 |
| REV-01 | Final Check-In — Office Visit | Review | CPT 99214 |
| REV-02 | Follow-Up Visit — Low Complexity | Review | CPT 99213 |
| REV-03 | Annual Wellness Visit | Review | HCPCS G0439 |

30 catalog entries across 8 categories (Lab, Medicine, Vitamins, Exercise, Monitoring, Diet,
Referral, Review). `enrollment.py` (Step 9) maps each of a plan's 10 parsed orbs to its closest
catalog entry via `catalog_orb_id`; if no catalog match is found, the orb is still enrolled
with `catalog_orb_id = NULL` and routed for clinician review of the catalog.

#### Billing Codes (`billing.billing_codes`)

Seed `billing.billing_codes` with the full ICD-10-CM / CPT / HCPCS reference set so Module 2's
quotation builder can price every code referenced by the catalog above (and any additional
codes parsed from a plan PDF).

**ICD-10-CM — Diagnosis codes** (`code_system = 'ICD-10'`, `is_billable = FALSE` — diagnoses are
not priced line items but appear in the quotation's `diagnoses` list):

| Code | Description |
|------|-------------|
| E11.9 | Type 2 diabetes mellitus, no complications |
| E11.65 | Type 2 diabetes with hyperglycemia |
| I10 | Essential (primary) hypertension |
| I25.10 | Atherosclerotic heart disease, unspecified |
| J06.9 | Acute upper respiratory infection, unspecified |
| J18.9 | Pneumonia, unspecified organism |
| J44.1 | COPD with acute exacerbation |
| F32.9 | Major depressive disorder, single episode |
| F41.1 | Generalized anxiety disorder |
| M54.5 | Low back pain |
| M17.11 | Primary osteoarthritis, right knee |
| N39.0 | Urinary tract infection |
| K21.0 | GERD with esophagitis |
| K92.1 | Melena (blood in stool) |
| Z23 | Encounter for immunization |
| Z00.00 | General adult medical exam, no abnormal findings |
| Z12.31 | Encounter for colorectal cancer screening |
| Z23.4 | Encounter for flu vaccination |
| R05.9 | Cough, unspecified |
| R51.9 | Headache, unspecified |
| R07.9 | Chest pain, unspecified |
| R55 | Syncope and collapse (fainting) |
| S72.001A | Femur fracture, initial encounter |
| T14.90 | Injury, unspecified |
| Z87.891 | Personal history of nicotine dependence |
| Z01.01 | Encounter for general exam with abnormal findings, eye |
| Z01.89 | Encounter for other specified special examinations |

**CPT — Procedure codes** (`code_system = 'CPT'`, `is_billable = TRUE`). Approximate
`unit_price` / `medicare_rate` shown for seed purposes — adjust to the clinic's actual fee
schedule:

| Code | Description | Unit Price | Medicare Rate | Requires Auth |
|------|-------------|-----------:|--------------:|:---:|
| 99213 | Office visit, established patient, low complexity | 75.00 | 60.00 | No |
| 99214 | Office visit, established patient, moderate complexity | 115.00 | 92.00 | No |
| 99203 | Office visit, new patient, low complexity | 100.00 | 80.00 | No |
| 99204 | Office visit, new patient, moderate complexity | 160.00 | 128.00 | No |
| 99395 | Preventive visit, established patient, 18–39 years | 150.00 | 120.00 | No |
| 99396 | Preventive visit, established patient, 40–64 years | 165.00 | 132.00 | No |
| 93000 | Electrocardiogram (ECG/EKG), routine | 25.00 | 20.00 | No |
| 71046 | Chest X-ray, 2 views | 40.00 | 32.00 | No |
| 80053 | Comprehensive metabolic panel (blood test) | 62.00 | 50.00 | No |
| 85025 | Complete blood count (CBC) with differential | 35.00 | 28.00 | No |
| 83036 | Hemoglobin A1c test (diabetes monitoring) | 45.00 | 36.00 | No |
| 84443 | Thyroid stimulating hormone (TSH) test | 40.00 | 32.00 | No |
| 82947 | Blood glucose test | 15.00 | 12.00 | No |
| 36415 | Routine venipuncture (blood draw) | 8.00 | 6.50 | No |
| 90837 | Psychotherapy, 60 minutes | 150.00 | 120.00 | No |
| 90834 | Psychotherapy, 45 minutes | 110.00 | 88.00 | No |
| 97110 | Therapeutic exercises (physical therapy) | 45.00 | 36.00 | No |
| 97140 | Manual therapy (physical therapy) | 40.00 | 32.00 | No |
| 27447 | Total knee replacement | 1500.00 | 1200.00 | Yes |
| 43239 | Upper GI endoscopy with biopsy | 450.00 | 360.00 | Yes |
| 45378 | Colonoscopy, diagnostic | 500.00 | 400.00 | Yes |
| 70553 | MRI brain with contrast | 1200.00 | 960.00 | Yes |
| 73721 | MRI joint of lower extremity | 900.00 | 720.00 | Yes |
| 99291 | Critical care, first 30–74 minutes | 250.00 | 200.00 | No |
| 99232 | Subsequent hospital care, moderate complexity | 110.00 | 88.00 | No |

**HCPCS Level II — Equipment and supplies** (`code_system = 'HCPCS'`, `is_billable = TRUE`):

| Code | Description | Unit Price | Medicare Rate | Requires Auth |
|------|-------------|-----------:|--------------:|:---:|
| A4253 | Blood glucose test strips, per 50 | 38.00 | 30.00 | No |
| E0601 | CPAP device (sleep apnea) | 700.00 | 560.00 | Yes |
| J0171 | Adrenalin epinephrine injection | 15.00 | 12.00 | No |
| J1040 | Methylprednisolone injection, 80mg | 20.00 | 16.00 | No |
| L0650 | Lumbar-sacral orthosis (back brace) | 250.00 | 200.00 | Yes |
| G0008 | Administration of influenza vaccine | 25.00 | 20.00 | No |
| G0439 | Annual wellness visit, subsequent | 140.00 | 112.00 | No |
| Q4161 | Skin substitute, per square centimeter | 150.00 | 120.00 | Yes |
| V2020 | Frames, purchases | 80.00 | 64.00 | No |
| V2100 | Sphere single vision, plano to plus/minus 4.00 | 50.00 | 40.00 | No |

Module 2's `build_quotation()` (Stage 2.5) reads from this fully-seeded `billing.billing_codes`
table, so any combination of catalog orb codes + plan-specific diagnosis codes will resolve to
a priced line item, a diagnosis entry, a prior-auth flag, or — if truly absent from this table —
an `unmatched` flag for review.

### Step 5 — ID generators

```python
def generate_patient_id() -> str:
    return f"PAT-{datetime.now().year}-{secrets.randbelow(99999):05d}"

def generate_orb_ref(patient_id: str, orb_number: int) -> str:
    return f"ORB-PAT{patient_id.split('-')[-1]}-{orb_number:03d}"

def generate_token(name: str, dob: str) -> str:
    raw = f"{name.lower().strip()}:{dob}"
    return "tok_" + hashlib.sha256(raw.encode()).hexdigest()[:12]
```

### Step 6 — Stage 1: Plan Creation (two-document strategy)

A treatment plan PDF is generated at the doctor visit. **Two versions** are produced:

| Version | Contents | Storage |
|---------|----------|---------|
| `PLN-2025-003_clinical.pdf` | Full PII | Locked S3 bucket (Object Lock), clinician access only |
| `PLN-2025-003_processing.pdf` | Redacted — IDs only | Pipeline-safe, standard storage |

The **processing PDF** is the only version that enters the automated pipeline (consumed by
Module 2). It carries:

```
Patient ID:  PAT-2025-00847      Plan ID:  PLN-2025-003
Patient Name: [REDACTED]
Each orb header:  Orb 1: Blood Work ... ORB-PAT00847-001
```

**Inputs:** patient PII, diagnoses, the 10 orb definitions, plan dates.
**Output:** two PDFs + initial records ready for ingestion.

### Step 7 — `services/vault.py`: PII encrypt/decrypt + access logging

Implement encrypt/decrypt helpers around `pgp_sym_encrypt`/`pgp_sym_decrypt` using `KMS_KEY`,
and append every read to `vault.patient_vault.access_log` (who accessed which record, when).

### Step 8 — Stage 3: Tokenization & Storage

PII is encrypted into the vault; everything else is stored with tokens only.

```python
async def store_plan(plan: dict, pii: dict, db) -> str:
    patient_id = generate_patient_id()              # PAT-2025-00847
    token      = generate_token(pii["name"], pii["dob"])

    # PII → encrypted vault
    await db.execute("""
        INSERT INTO vault.patient_vault
          (patient_id, token, name_encrypted, dob_encrypted, address_encrypted)
        VALUES ($1, $2,
                pgp_sym_encrypt($3, $6),
                pgp_sym_encrypt($4, $6),
                pgp_sym_encrypt($5, $6))
    """, patient_id, token, pii["name"], pii["dob"], pii["address"], KMS_KEY)

    # Plan → app schema (no PII)
    await db.execute("""
        INSERT INTO app.treatment_plans
          (plan_id, patient_id, provider, plan_start,
           duration_days, buffer_days, extension_days,
           target_date, hard_stop, next_visit)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
    """, plan["plan_id"], patient_id, plan["provider"], plan["plan_start"],
         14, 3, 7, plan["target_date"], plan["hard_stop"], plan["next_visit"])

    return patient_id
```

**Output:** PII in vault, plan + diagnoses in `app`, ready to enroll.

### Step 9 — Stage 4: Enrollment (`services/enrollment.py`)

The timeline is computed and 10 orb tracking rows are created.

```python
async def enroll(plan_id: str, patient_id: str, parsed_orbs: list, db):
    plan = await db.fetchrow(
        "SELECT * FROM app.treatment_plans WHERE plan_id = $1", plan_id)

    for orb in parsed_orbs:
        orb_ref = generate_orb_ref(patient_id, orb["orb_number"])
        catalog_orb_id = await match_catalog_orb(orb, db)   # best match from app.orbs, or NULL
        await db.execute("""
            INSERT INTO app.patient_orbs
              (orb_ref, plan_id, patient_id, orb_number, catalog_orb_id, status, target_date)
            VALUES ($1, $2, $3, $4, $5, 'pending', $6)
        """, orb_ref, plan_id, patient_id, orb["orb_number"], catalog_orb_id, orb["target_date"])

    await notify_patient(plan_id, "Your 10 Orbs to Better plan starts today.")
```

`match_catalog_orb()` resolves a parsed orb to a row in the `app.orbs` catalog (Step 4) by
comparing title/category and any billing codes on the parsed orb against `app.orbs.billing_codes`.
If no confident match is found, `catalog_orb_id` is left `NULL` and the orb is flagged for a
clinician to map to (or add) a catalog entry — it does not block enrollment.

**Computed timeline (14-day example, start June 13):**

| Marker | Day | Date |
|--------|-----|------|
| Plan start | 0 | Jun 13 |
| Checkpoint 1 | 11 | Jun 24 (`duration - buffer`) |
| Target date | 14 | Jun 27 (`duration`) |
| Checkpoint 3 | 18 | Jul 1 (`hard_stop - buffer`) |
| Hard stop | 21 | Jul 4 (`duration + extension`) |
| Next visit | — | Jul 8 |

**Output:** 10 `pending` orbs, status `active`, timeline set.

---

## 3. Deliverable

- Postgres up with `vault`, `app`, `billing` schemas migrated via Alembic.
- pgcrypto enabled; vault encryption + access logging working.
- Seed data loaded (30-entry orb catalog across 8 categories + full ICD-10/CPT/HCPCS
  billing codes).
- `store_plan()` and `enroll()` callable end-to-end, producing tokenized records and 10
  `pending` `patient_orbs` rows — each linked via `catalog_orb_id` to its matching `app.orbs`
  catalog entry — ready for Module 2 (ingestion) to feed and Module 3 (tracking) to update.
