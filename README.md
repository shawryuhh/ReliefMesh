# ReliefMesh — Human-in-the-Loop Disaster Response Coordination Platform

ReliefMesh is a full-stack disaster response command center designed for high-stakes emergency coordination. Built around a synthetic Bengaluru flood scenario (`INC-1042`, Krishna Apartments Block C), it combines multilingual report intake, deterministic AI priority scoring and resource recommendation, event-driven workflow automation, and a PostgreSQL system of record—while enforcing **strict human-in-the-loop approval gates** before any responder is dispatched or rerouted.

> **Safety & Synthetic Data Notice:** ReliefMesh operates exclusively on synthetic demonstration data (`source: "synthetic-demo"`). It never contacts real emergency services, never dispatches physical responders, and never exposes API keys to browser clients.

---

## Architecture Overview

```mermaid
flowchart LR
  subgraph Citizens["Synthetic Citizen Intake"]
    RPT["Multilingual Reports\n(13 Languages)"]
  end

  subgraph Automation["n8n Workflow Layer (n8n/)"]
    WF["intake / dispatch /\nreplan / resolution"]
    FIX["Fixture Harness & Server\n(SQLite + Backend Bridge)"]
  end

  subgraph AIEngine["AI Engine (ai/)"]
    EXT["Structured Extraction &\nDeduplication"]
    SCORE["Deterministic Priority\nScoring (0-100)"]
    REC["Resource-Aware Planner\n(approval_required: true)"]
  end

  subgraph Backend["FastAPI System of Record (backend/)"]
    API["REST + Demo Integration API\n(/integration/v1/*)"]
    GATE["Human Approval Gate\n(require_coordinator)"]
    PG[("PostgreSQL 16\nRow Locks + Revisions")]
  end

  subgraph Frontend["Next.js 16 Command Center (frontend/)"]
    PROXY["Loopback Server Proxy\n(/api/backend-demo)"]
    SIM["Simulated Fallback\n(Default Mode)"]
    UI["Coordinator Dashboard\n(Map, Queue, Decision Dock)"]
  end

  RPT --> WF
  WF <--> FIX
  FIX --> API
  API <--> EXT
  API <--> SCORE
  API <--> REC
  API --> GATE
  GATE <--> PG
  UI <--> SIM
  UI <--> PROXY
  PROXY <--> API
```

### Technology Choices & Subsystem Responsibilities

| Layer | Stack | Responsibility |
| :--- | :--- | :--- |
| **Frontend (`frontend/`)** | Next.js 16 (App Router), React 19, TypeScript, Leaflet, Node Test Runner | Operational command center with 13-language localization (including RTL Urdu), interactive map, incident queue, AI explanation cards, coordinator decision dock, **Simulated Fallback (default)**, and **Opt-In Live PostgreSQL + AI Backend Mode**. |
| **Backend (`backend/`)** | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, Pytest | Authoritative system of record for incidents, reports, resources, versioned recommendations, assignments, action logs, and monotonic `operational_revision` counters. Enforces state machines, `SELECT ... FOR UPDATE` locking, partial unique indexes, and coordinator-only authorization. |
| **AI Engine (`ai/`)** | Python 3.12, FastAPI, Pydantic, Google GenAI SDK (optional) | Deterministic priority scoring (`/ai/score-incident`), capability- and ETA-aware resource recommendation (`/ai/recommendation`), and structured extraction/deduplication/translation contracts (`/ai/extract-incident`, `/ai/deduplicate-incident`, `/ai/translate-report`) with validated synthetic demo fixtures when live Gemini credentials are not configured. |
| **Automation (`n8n/`)** | n8n Workflow JSON exports, Node.js harness, Python SQLite fixture server | Four bounded, idempotent workflow pipelines (`intake`, `dispatch`, `replan`, `resolution`) with `Idempotency-Key` headers, exponential backoff (`1s, 3s, 10s`), command lease validation, and optional synchronization with the FastAPI backend (`--backend-url`). |

---

## Core Engineering & Safety Guarantees

1. **Non-Bypassable Human Approval Gates**:
   - Creating an initial recommendation (`v1`) or a roadblock replacement proposal (`v2`) only inserts a `PENDING` recommendation and transitions the incident to `awaiting_approval` or `awaiting_replacement`.
   - Resource dispatch and assignment creation happen exclusively inside `approve_recommendation`, which is protected by `require_coordinator`.
   - Presenting an automation API key (`AUTOMATION_API_KEY`) or `X-Fixture-Actor: automation` on approval, modification, or rejection endpoints returns `403 Forbidden`.
2. **Idempotency & Concurrency Protection**:
   - Every write transaction locks rows in a deterministic order (`Incident` -> `Recommendation` -> `Assignment` -> `Resource`) using PostgreSQL `SELECT ... FOR UPDATE`.
   - Database-level partial unique indexes enforce at most one `PENDING` recommendation per incident (`uq_recommendation_pending_incident`) and at most one live assignment per resource (`uq_assignments_one_live_per_resource`).
   - Repeated automation events or duplicate `analysis_revision` / `Idempotency-Key` submissions replay the existing state without duplicating assignments or dispatches.
3. **Delta-Only Replacement Dispatch**:
   - When `AMB-02` encounters a flooded underpass (ETA `6 min -> 24 min`), the AI engine proposes `v2` (`AMB-05 + RESCUE-01`).
   - Upon human coordinator approval of `v2`, `AMB-02`'s assignment is atomically marked `SUPERSEDED` and `AMB-02` returns to `AVAILABLE`, `RESCUE-01` continues on its existing live assignment without duplication, and `AMB-05` (`ETA 9 min`) is dispatched.
4. **Explicitly Opt-In Live Backend Mode with Simulated Fallback**:
   - The frontend defaults to its self-contained **Simulated Fallback** (`createMockService()`) so it works offline or without backend infrastructure.
   - Evaluators can switch to **Live PostgreSQL + AI Backend (Opt-In)** from the **Demo Controls -> Data mode** selector (or via `NEXT_PUBLIC_RELIEFMESH_DEMO_MODE=backend` and `RELIEFMESH_ENABLE_BACKEND_DEMO=true`). All backend requests pass through the Next.js server-side loopback proxy (`/api/backend-demo`), keeping API keys out of browser bundles.

---

## Running the Finished Demo on Windows (PowerShell)

### Prerequisites
- **Node.js** 20+ (`node -v`)
- **Python** 3.12 (`python --version`)
- **PostgreSQL** 16 running locally on port `5432` (with database `reliefmesh` and user/password `reliefmesh`)

### 1. Start PostgreSQL & Migrate the Backend Database
```powershell
# Apply Alembic migrations and seed the initial demo scenario
cd C:\Users\HP\ReliefMesh\backend
$env:DATABASE_URL = "postgresql+psycopg2://reliefmesh:reliefmesh@localhost:5432/reliefmesh"
python -m alembic upgrade head
python -m scripts.seed_demo_data --reset --stop-at awaiting_approval
```

### 2. Start the FastAPI Backend Server (Terminal 1)
```powershell
cd C:\Users\HP\ReliefMesh\backend
$env:APP_ENV = "development"
$env:DATABASE_URL = "postgresql+psycopg2://reliefmesh:reliefmesh@localhost:5432/reliefmesh"
$env:AUTH_ENABLED = "true"
$env:API_KEY = "local-dev-read-key"
$env:COORDINATOR_API_KEY = "local-dev-coordinator-key"
$env:AUTOMATION_API_KEY = "local-dev-automation-key"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. Start the Next.js Frontend with Opt-In Backend Demo Enabled (Terminal 2)
```powershell
cd C:\Users\HP\ReliefMesh\frontend
npm ci
$env:RELIEFMESH_ENABLE_BACKEND_DEMO = "true"
$env:RELIEFMESH_ENABLE_INTEGRATION_PREVIEW = "true"
$env:RELIEFMESH_BACKEND_URL = "http://127.0.0.1:8000"
$env:RELIEFMESH_BACKEND_READ_KEY = "local-dev-read-key"
$env:RELIEFMESH_COORDINATOR_API_KEY = "local-dev-coordinator-key"
$env:RELIEFMESH_AUTOMATION_API_KEY = "local-dev-automation-key"
$env:NEXT_PUBLIC_RELIEFMESH_DEMO_MODE = "backend"
npm run dev
```

Open **http://localhost:3000** in your browser.
- To switch between **Live PostgreSQL + AI Backend (Opt-In)** and **Simulated Fallback (Default)** at any time, open **Demo controls** and use the **Data mode** dropdown.
- You can also inspect the low-level read-only snapshot contract diagnostic page at **http://localhost:3000/integration-preview**.

---

## Best 5-Minute Hackathon Demonstration Sequence

1. **Minute 0:00–1:00 — Operational Overview & Data Mode Selection**:
   - Open `http://localhost:3000`. Point out the Southeast Bengaluru sector map, the 4 live operational metrics (`02 Critical`, `09 Active`, `05 Available Ambulances`, `03 Available Rescue Teams`), and the **PostgreSQL + AI (Opt-In)** indicator in the Demo Controls bar.
   - Expand **Demo controls** and click **Start from report intake** (`0 / 11`) to show the complete lifecycle from the moment a citizen call arrives.
2. **Minute 1:00–2:15 — Report Intake, Deduplication, AI Scoring & Initial Plan (Steps 1–5)**:
   - Click **Run demo** (or step through **1. Receive emergency** -> **2. Merge duplicate reports** -> **3. Set priority 94** -> **4. Generate recommendation** -> **5. Request approval**).
   - Select `INC-1042` (*Krishna Apartments Block C*) and switch languages or click **Translate report** to demonstrate verified multilingual translation across 13 Indian languages.
   - Show that playback **automatically pauses at Step 5 (`Waiting for your approval`)** because AI/n8n cannot self-approve dispatch.
3. **Minute 2:15–3:15 — Human Approval Gate #1 & Simulated Dispatch (Step 6)**:
   - Inspect the **AI response recommendation** (`AMB-02` ALS ambulance at 2.1 km / 6 min ETA + `RESCUE-01` water rescue team at 7 min ETA) and optionally open **Modify** to show capability and availability validation.
   - Click **Approve dispatch** in the Decision Dock. Watch `AMB-02` and `RESCUE-01` transition to `Dispatched` and available ambulance count drop from `05` to `04`.
4. **Minute 3:15–4:15 — Road Obstruction, AI Replanning & Human Approval Gate #2 (Steps 7–10)**:
   - Click **Run demo** (or step through **7. Simulate road block** -> **8. Trigger replanning** -> **9. Recommend AMB-05**).
   - Point out the route disruption alert (`AMB-02` delayed from `6 min` to `24 min`) and the new `v2` replacement recommendation (`AMB-05` at `9 min` ETA replacing `AMB-02`, while `RESCUE-01` **Continues on scene**).
   - Show that playback pauses again at **Human Approval Gate #2 (`9 / 11`)**. Click **Approve dispatch** on the replacement plan: `AMB-02` is released back to `Available`, `RESCUE-01` remains dispatched without duplication, and `AMB-05` is dispatched.
5. **Minute 4:15–5:00 — Resolution, Audit Trail & Resilience Scenarios (Step 11)**:
   - Step **11. Resolve incident** (or let autoplay complete it). `INC-1042` transitions to `Resolved`, all assigned units (`AMB-05`, `RESCUE-01`) return to `Available`, and the incident moves cleanly to **Resolved / History**.
   - Switch to the **Audit trail** tab to show the complete chronological log attributed to `Report intake`, `AI service`, `Coordinator`, and `Automation`.
   - Optionally demonstrate honest error handling using the **Simulate a state** dropdown (`Automation offline`, `Stale data`, `API failure`) and click **Retry** to restore normal operation.

---

## Running All Verification Suites

```powershell
# 1. Frontend unit tests (53 tests), TypeScript check, and production build
cd C:\Users\HP\ReliefMesh\frontend
npm test
npm run typecheck
npm run build

# 2. Backend PostgreSQL integration & concurrency suite (115 tests)
cd C:\Users\HP\ReliefMesh\backend
$env:DATABASE_URL = "postgresql+psycopg2://reliefmesh:reliefmesh@localhost:5432/reliefmesh"
$env:TEST_DATABASE_URL = "postgresql+psycopg2://reliefmesh:reliefmesh@localhost:5432/reliefmesh_test"
python -m pytest -q

# 3. AI engine unit & contract tests (26 tests, no live API keys required)
cd C:\Users\HP\ReliefMesh
python -m unittest discover -s ai -p "test_*.py" -v
python -m pytest tests/test_ai.py -q

# 4. n8n workflow & SQLite fixture contract tests (31 tests)
cd C:\Users\HP\ReliefMesh\n8n
node --test tests/workflows.test.js
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## Honest Limitations & Scope Boundaries

- **Synthetic Demo Scope**: The canonical 11-step interactive demo flow is centered on `INC-1042` (*Krishna Apartments Block C*) alongside 9 background Bengaluru incidents and a 19-unit responder fleet.
- **Offline-Safe AI & Translation**: Priority scoring (`/ai/score-incident`) and resource selection (`/ai/recommendation`) are 100% deterministic in `ai/main.py`. Unstructured report extraction, semantic deduplication, and report translation use validated synthetic fixtures when `GEMINI_API_KEY` is not configured, and honestly reject unverified arbitrary text (`TRANSLATION_UNAVAILABLE`) rather than fabricating translations.
- **Local Loopback Security Model**: The Next.js `/api/backend-demo` and `/api/backend-preview` proxy routes intentionally restrict access to loopback hosts (`localhost` / `127.0.0.1`) for local demonstration safety and are not a public multi-tenant authentication system.
- **n8n Execution Harness**: The repository includes importable n8n workflow JSON exports (`n8n/workflows/*.json`), a deterministic Node.js execution harness (`n8n/scripts/run_fixture_workflow.js`), and a local fixture server (`n8n/scripts/fixture_server.py`) with an optional `--backend-url` bridge rather than requiring a cloud-hosted n8n instance.
