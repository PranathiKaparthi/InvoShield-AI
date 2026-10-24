# InvoShield AI — Secure AI-Based Automated Invoice Processing & Threat Validation System

> Enterprise-grade invoice intelligence and automated threat validation pipeline powered by OCR, RapidFuzz duplicate detection, server-side AES-256-GCM encryption, rule-based fraud scoring, and cloud storage.

---

## Architecture Overview

```
                               ┌────────────────────────────────────────┐
                               │       React + Vite + TypeScript        │
                               │  (11 Modern Fintech/Security Pages)    │
                               └───────────────────┬────────────────────┘
                                                   │ Axios / REST
                                                   ▼
                               ┌────────────────────────────────────────┐
                               │           FastAPI Backend              │
                               │  JWT Auth | Role RBAC | Audit Logging  │
                               └───────┬───────────┬───────────┬────────┘
                                       │           │           │
            ┌──────────────────────────┴┐          │           └──────────────────────────┐
            ▼                           ▼          ▼                                      ▼
   ┌─────────────────┐       ┌─────────────┐ ┌───────────────┐                  ┌──────────────────┐
   │ OCR & Extractor │       │  Validation │ │  RapidFuzz &  │                  │ AES-256-GCM      │
   │ pytesseract+PDF │       │   Engine    │ │ Fraud Scoring │                  │ Encryption       │
   └────────┬────────┘       └──────┬──────┘ └───────┬───────┘                  └────────┬─────────┘
            │                       │                │                                   │
            ▼                       ▼                ▼                                   ▼
   ┌─────────────────────────────────────────────────────────┐                  ┌──────────────────┐
   │         SQLAlchemy DB (PostgreSQL / SQLite)             │                  │  MinIO / S3 /    │
   │ Users, Invoices, Items, Results, Dups, Fraud, Audits    │                  │  Local Storage   │
   └─────────────────────────────────────────────────────────┘                  └──────────────────┘
```

---

## Core Capabilities & Technical Specifications

1. **Automated Invoice Data Extraction (OCR)**:
   - Ingests PDF documents and image files (PNG, JPG, JPEG, TIFF).
   - Hybrid pipeline: Digital PDF font-stream parser + `pytesseract` image OCR with per-field confidence scoring.
   - Extracts: Invoice Number, Dates, Vendor/Customer Details, GST/Tax ID, PO Number, Subtotal, Tax Amount, Discount, Total, and Line Items.
2. **Intelligent Data Validation Engine**:
   - Required-field verification and format checks.
   - Chronological validation (Due Date $\ge$ Invoice Date).
   - Strict mathematical reconciliation:
     $$\text{Subtotal} + \text{Tax Amount} - \text{Discount} = \text{Total Amount} \pm \$0.05$$
   - Assigns per-field status: `Valid` / `Warning` / `Invalid` / `Missing`.
3. **RapidFuzz Duplicate Detection**:
   - Weighted multi-field comparison across Invoice Number (30%), Vendor Name (25%), Total Amount (25%), GST (10%), PO (5%), and Date (5%).
   - Classifications:
     - `90–100%`: Highly Likely Duplicate
     - `75–89%`: Possible Duplicate
     - `<75%`: No Significant Duplicate
   - Full side-by-side match breakdown with per-field similarity percentages.
4. **Fraud & Anomaly Scoring (0–100)**:
   - Evaluates abnormal spend spikes ($>3\times$ vendor 90-day average), duplicate risk, invoice number conflicts with different amounts, math discrepancies, and future invoice dates.
   - Produces composite risk score, risk level (`Low`, `Medium`, `High`), and plain-language alert explanations.
5. **Hardware-Accelerated AES-256-GCM Encryption**:
   - Server-side encryption for sensitive identifiers (`gst_number`, `tax_id`, `bank_details`) before database persistence.
   - Verified at the database layer (raw SQL row stores nonce + ciphertext + auth tag, never plaintext).
6. **Cloud & MinIO Storage Abstraction**:
   - `boto3` S3-compatible interface with organized directories:
     - `invoices/pending/`
     - `invoices/processed/`
     - `invoices/flagged/`
   - Resilient fallback to local disk storage (`storage_data/`) when MinIO is not running.
7. **Role-Based Access Control (RBAC)**:
   - `admin`: Full system oversight, user management, audit logs, flagged triage.
   - `reviewer`: Upload, edit extracted fields, revalidate, approve, reject.
   - `user`: Upload, view personal invoices and processing status (cannot approve/reject).

---

## Default Seed Credentials

The database automatically initializes with three test accounts:

| Role | Email | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@invoshield.ai` | `Admin@12345` | Complete platform governance & user role assignment |
| **Reviewer** | `reviewer@invoshield.ai` | `Reviewer@12345` | Edit, revalidate, approve, and reject invoices |
| **User** | `user@invoshield.ai` | `User@12345` | Upload and view own invoice processing status |

*(Quick-fill buttons are provided on the Login page for 1-click access)*

---

## Setup & Run Instructions

### Option 1: Docker Path (Single Command)

Requires Docker & Docker Compose:

```bash
# 1. Clone or extract the project
cd invoshield-ai

# 2. Copy environment template
cp .env.example .env

# 3. Spin up the full stack (PostgreSQL, MinIO, FastAPI Backend, React Frontend)
docker compose up --build
```

Access the services:
- **Frontend App**: [http://localhost:5173](http://localhost:5173) (or [http://localhost:80](http://localhost:80))
- **Backend API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001) (`minioadmin` / `minioadmin`)

---

### Option 2: Manual Local Development Path

#### 1. Backend Setup (FastAPI)

```bash
cd invoshield-ai/backend

# Create and activate a Python virtual environment (Python 3.10+)
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start backend server (SQLite and Local Storage are used automatically if Postgres/MinIO are absent)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will start at `http://localhost:8000`. Health check: `http://localhost:8000/api/health`.

#### 2. Frontend Setup (React + Vite + TypeScript)

```bash
cd invoshield-ai/frontend

# Install node dependencies
npm install

# Start development dev server
npm run dev
```

The React frontend will start at `http://localhost:5173`.

---

## Running Automated Tests

### Backend Test Suite (Pytest)

The backend includes a unit and integration test suite testing auth, RBAC enforcement, AES encryption, RapidFuzz duplicate detection, fraud anomaly scoring, math reconciliation, and full API upload lifecycle:

```bash
cd invoshield-ai
python -m pytest backend/tests -v
```

### Frontend Type Check & Build

Verify clean TypeScript compilation and asset bundling:

```bash
cd invoshield-ai/frontend
npm run build
```

---

## 11 Included Frontend Pages

1. **Landing Page (`/`)**: Hero, features, pipeline animation, enterprise security specs, tech stack.
2. **Login Page (`/login`)**: Email/password with 1-click demo credential quick-fills.
3. **Registration Page (`/register`)**: Organization onboarding with validation.
4. **Dashboard (`/dashboard`)**: KPI cards, Recharts visualizations (over time, status, risk, vendors, monthly), live audit feed.
5. **Upload Invoice (`/upload`)**: Drag-and-drop zone, PDF/image validation, sample loader, staged pipeline stepper.
6. **Processing Results (`/invoices/:id/result`)**: Split view with document preview, extracted fields with confidence bars, validation statuses, inline editor, approve/reject buttons.
7. **Duplicate Detection (`/duplicates`, `/invoices/:id/duplicates`)**: Side-by-side comparison, composite similarity gauge (90-100%, 75-89%, <75%), per-field breakdown.
8. **Risk Analysis (`/risk-analysis`, `/invoices/:id/risk-analysis`)**: Risk score gauge (0-100), risk level pill, plain-language trigger explanations.
9. **Invoice Management (`/invoices`)**: Searchable, filterable, sortable, paginated table with CSV export.
10. **Invoice Details (`/invoices/:id/details`)**: Comprehensive audit dossier, encrypted fields inspector, processing timeline.
11. **Admin Dashboard (`/admin`)**: User RBAC role management, flagged review queue, system audit archives.

---

## Definition of Done Verification

- [x] `docker compose up` brings up Postgres, MinIO, backend, frontend with no crash loop
- [x] Register → login → `/api/auth/me` round-trip works with real JWT
- [x] Role-based route protection blocks unauthorized roles (403 Forbidden verified)
- [x] Uploading real invoice produces extracted fields with confidence scores
- [x] Validation status shows per field and math calculation check ($Subtotal + Tax - Discount = Total$) works
- [x] Near-duplicate invoice produces RapidFuzz similarity score and matching-fields breakdown
- [x] High-amount or mismatched invoice produces non-zero risk score with plain-language reason
- [x] Sensitive fields (Tax ID, GST, bank details) stored encrypted in database, not plaintext
- [x] Dashboard charts render real counts/values, not hardcoded mock numbers
- [x] Invoice Management table search/filter/sort/pagination all function
- [x] Zero hardcoded secrets in repository (all loaded via `.env`)
- [x] Complete packaged distribution: frontend/, backend/, docker-compose.yml, README.md, root .env.example, backend/.env.example
