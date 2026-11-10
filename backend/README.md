# ReliefMesh Backend

System of record for incidents, resources, assignments, and the audit trail
in the ReliefMesh crisis-coordination platform.

## Purpose

During a disaster, reports come in from ingestion (WhatsApp/SMS via n8n) and
get triaged by an AI service, which recommends what to do (assign a
resource, replace one stuck behind a blocked road, etc.). A human coordinator
approves those recommendations before anything is dispatched. **This backend is the single source of
truth that all of that funnels through.** It owns:

- The incident/resource/assignment data model and their state machines.
- Concurrency safety — two simultaneous requests can never assign the same
  resource twice.
- The approval gate — AI/n8n can only submit *pending* plans; dispatch
  happens exclusively when a coordinator approves one.
- Atomicity — a multi-step operation (e.g. approving a replacement) either fully applies
  or fully rolls back, never partially.
- The append-only audit trail of every decision and state change.

**This backend deliberately does not do AI reasoning, deduplication, or
priority scoring.** It receives decisions from the AI service / n8n / a
human and enforces that applying them is safe and consistent. If you're
integrating a new AI/n8n flow and find yourself wanting the backend to
"decide" something, that decision belongs upstream — the backend should
only be asked to validate and persist it.

## Architecture overview

```
app/
  api/routes/        FastAPI routers — one file per resource, thin: parse
                      request, call a service function, return its result.
  api/deps.py         Shared dependencies (DB session, optional API key auth).
  api/common_responses.py  Reusable OpenAPI error-response fragments.
  core/               Config, domain exception types, free-text domain values.
  db/                 SQLAlchemy engine/session/declarative base.
  models/             SQLAlchemy ORM models + the fixed status enums.
  schemas/            Pydantic request/response models (the actual wire
                      contract — read these first when integrating).
  services/           All business logic lives here: locking, state-machine
                      transitions, atomic transactions, audit logging.
    state_machine.py     Single source of truth for allowed status
                          transitions (incident/resource/assignment).
    id_generator.py      Human-readable IDs (INC-1042, AMB-02, ASG-887) via
                          native Postgres sequences.
    assignment_service.py   Create/update assignments; the locking
                             primitives reused everywhere else.
    recommendation_service.py  Plan intake, replacement proposals, and
                             the coordinator approval gate (dispatch).
    disruption_service.py   Road-block reports (ETA revision, `blocked`).
    dashboard_service.py    Read-only aggregation for the frontend.
alembic/               Migrations (single initial migration; schema is small
                        and stable — see "Migrations" below).
scripts/seed_demo_data.py   Seeds the canonical Krishna Apartments demo.
tests/                 pytest suite, run against a real (isolated) Postgres.
```

**Design choices worth knowing before you change anything:**

- `Incident.type` and `Resource.type` are free-text strings, not enums —
  new incident/resource types need zero backend code changes. Incident
  *status* and resource/assignment *status* ARE fixed enums with explicit
  transition tables in `state_machine.py`; don't add ad-hoc `if status ==`
  checks anywhere else.
- Every entity ID is human-readable and generated via a Postgres sequence
  (`nextval()`), not app-side counters — atomic under concurrency for free.
- Resource `capacity` exists on the model but is **not** consumed/decremented
  by assignment logic in this MVP — it's descriptive only.
- Double-booking a resource is prevented three ways at once: `SELECT ...
  FOR UPDATE` row locks (fixed ID order, to avoid deadlocks), a re-check of
  state after the lock is acquired, and a partial unique index in Postgres
  (`assignments(resource_id) WHERE status IN ('ASSIGNED','ACTIVE')`) as a
  hard backstop. See `assignment_service.py` and `recommendation_service.py`.
- Every write that touches a plan locks in the same order: incident →
  recommendation → the incident's live assignments → resources (by ID).
- The audit trail (`action_logs`) is append-only by omission: there is no
  PATCH/PUT/DELETE route for it anywhere, so it can't be rewritten via the
  API.

## Prerequisites

- Python 3.11+
- Docker Desktop (for PostgreSQL)
- `pip install -r requirements.txt` inside a virtualenv

## Docker / PostgreSQL setup

The backend expects a single PostgreSQL 16 instance holding two databases:
the dev/demo database (`reliefmesh`) and an isolated test database
(`reliefmesh_test`, created automatically the first time you run the test
suite — see below).

If you don't already have the container running:

```bash
docker run -d --name reliefmesh-postgres \
  -e POSTGRES_USER=reliefmesh \
  -e POSTGRES_PASSWORD=reliefmesh \
  -e POSTGRES_DB=reliefmesh \
  -p 5432:5432 \
  postgres:16-alpine
```

If it already exists, just make sure it's running:

```bash
docker start reliefmesh-postgres
docker ps --filter name=reliefmesh-postgres
```

## Environment variables

Copy `.env.example` to `.env` and adjust as needed:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://reliefmesh:reliefmesh@localhost:5432/reliefmesh` | Dev/demo database connection. |
| `AUTH_ENABLED` | `false` | If `true`, every request needs a matching `X-API-Key` header. Off by default so the demo/local dev is never blocked. |
| `API_KEY` | `change-me` | Shared key, checked only when `AUTH_ENABLED=true`. |
| `COORDINATOR_API_KEY` | *(empty)* | Key identifying the human coordinator. Required to approve plans when `AUTH_ENABLED=true`. |
| `AUTOMATION_API_KEY` | *(empty)* | Key for n8n/AI. May submit plans, propose replacements and report disruptions; gets `403` on approval. |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins. |
| `APP_ENV` | `local` | Informational only, surfaced in `/health`. |
| `TEST_DATABASE_URL` | *(unset)* | Optional override for the isolated test database (defaults to `reliefmesh_test` on the same host/credentials). See "Test database isolation." |

## Migrations

Alembic-managed, schema in `alembic/versions/` (currently one migration
covering the full initial schema: `incidents`, `resources`, `assignments`,
`action_logs`, their enums, sequences, and the partial-unique locking
constraint).

```bash
alembic upgrade head        # apply migrations (dev database, via DATABASE_URL)
alembic revision -m "..."   # create a new migration after a model change
alembic downgrade -1        # roll back one migration
```

## Starting the backend

```bash
uvicorn app.main:app --reload --port 8000
```

- **API docs (Swagger UI): http://localhost:8000/docs**
- ReDoc: http://localhost:8000/redoc
- Raw OpenAPI schema: http://localhost:8000/openapi.json
- Health check: http://localhost:8000/health — verifies the process *and*
  the live Postgres connection; poll this from n8n/infra, not `/docs`.

## Running tests

```bash
pytest
```

### Test database isolation

Tests run against **real PostgreSQL**, never SQLite — the assignment/
replacement tests exercise genuine `SELECT ... FOR UPDATE` locking and
concurrent-transaction behavior that SQLite can't reproduce. To keep this
from writing test data into your dev/demo database:

- `tests/conftest.py` overrides `DATABASE_URL` to point at a separate
  `reliefmesh_test` database (same Postgres instance/credentials) *before*
  the app is imported anywhere.
- A session-scoped fixture creates that database if it doesn't exist yet
  and runs `alembic upgrade head` against it.
- A function-scoped fixture `TRUNCATE`s all app tables after every test, so
  tests are independent and repeatable.

Your dev database (`reliefmesh`) is never touched by `pytest`. You can
point tests at a different database (e.g. in CI) via `TEST_DATABASE_URL`.

## Seeding the Krishna Apartments demo

```bash
python -m scripts.seed_demo_data --reset
```

This is the canonical demo script — it drives the **real service layer**
(not raw SQL), so it's also an end-to-end smoke test of the exact code path
the live demo uses. It:

1. Registers a 10-resource fleet (5 ambulances, 2 rescue units, a
   volunteer, a shelter, a hospital), ordered so the IDs land exactly on
   `AMB-02` and `AMB-05`.
2. Creates incident `INC-1042` ("Water entering Krishna Apartments Block C.
   My grandmother cannot walk.").
3. Submits plan v1 (`AMB-02` + `RESCUE-01`) — pending, nothing dispatched.
4. Approves v1 as the coordinator: both are dispatched (`ASG-887`, `ASG-888`).
5. Reports a road block on `AMB-02` (ETA 6 → 24 min); the incident is `blocked`.
6. Proposes replacement plan v2 (`AMB-05` + `RESCUE-01`, replacing `AMB-02`)
   — pending again, `AMB-02` still dispatched.
7. Approves v2: `AMB-02`'s assignment is superseded (not deleted) and it's
   released, `AMB-05` is dispatched, `RESCUE-01` continues untouched.

After running, `GET /dashboard` and `GET /activity-log` show the fully
resolved narrative, ready to walk through live. To drive the rest of the
story live from the UI instead, stop early with
`--stop-at {awaiting_approval,dispatched,blocked,awaiting_replacement}`.

**Seed reset behavior:** by default the script *adds* to whatever's already
in the target database. Pass `--reset` to `TRUNCATE` every application
table first (and reset the resource/report/recommendation ID sequences, so
`AMB-02`/`AMB-05`/`RESCUE-01`/`REC-01` land correctly again) — only do this
against your local dev database, never anything shared. Pass `--fleet-only`
to seed just the resource roster and skip the incident narrative.

## Important API endpoints

All routes except `/health` are versionless and (optionally, see
`AUTH_ENABLED`) require an `X-API-Key` header. Full request/response
schemas and examples are in Swagger UI at `/docs` — this is a map, not a
substitute.

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness + DB connectivity check. |
| `POST /incidents` | Create an incident (ingestion/AI → backend). |
| `GET /incidents`, `GET /incidents/{id}` | List/get incidents, with status/severity/type/priority filters. |
| `PATCH /incidents/{id}` | Update incident fields (not status). |
| `POST /incidents/{id}/resolve`, `POST /incidents/{id}/cancel` | Terminal status transitions. |
| `POST /resources` | Register a resource (starts `AVAILABLE`). |
| `GET /resources`, `GET /resources/{id}` | List/get resources, with status/type filters. |
| `POST /resources/{id}/status` | Direct status transition (e.g. maintenance). |
| `POST /assignments` | Atomically assign available resources, referencing an already-approved recommendation. |
| `GET /assignments`, `GET /assignments/{id}` | List/get assignments, filterable by incident/resource/status. |
| `POST /assignments/{id}/status` | Transition to `ACTIVE`/`COMPLETED`/`CANCELLED` (never `SUPERSEDED` — only replacement approval sets that). |
| `GET /integration/v1/incidents/{id}/recommendation` | Current (highest-version) plan, any state. |
| `POST /integration/v1/incidents/{id}/recommendation` | Submit the initial plan (pending; idempotent on `analysis_revision`). |
| `POST /integration/v1/incidents/{id}/disruptions` | Report an obstructed responder; incident becomes `blocked`. |
| `POST /integration/v1/incidents/{id}/recommendation/replacement` | Propose a pending replacement plan for a blocked incident. |
| `POST /integration/v1/incidents/{id}/recommendation/approve` | Coordinator-only. Approve the pending plan and dispatch it. **The critical demo path.** |
| `GET /activity-log`, `POST /activity-log`, `GET /activity-log/{id}` | Append-only audit trail; filterable, paginated. |
| `GET /dashboard` | Frontend-ready aggregated snapshot (counts, recent activity, current incidents/resources). |

## Example integration flow (n8n)

A typical end-to-end flow through n8n for a new report:

1. Ingestion webhook receives a raw report (WhatsApp/SMS) → n8n forwards
   the text to the AI service for extraction.
2. n8n calls `POST /incidents` with the AI's structured output (see payload
   below). The backend assigns `INC-1042` and logs `incident_received`.
3. n8n asks the AI service for a resource plan and submits it with
   `POST /integration/v1/incidents/{id}/recommendation`. Nothing is
   dispatched yet; the incident is `awaiting_approval`.
4. A coordinator approves it (`.../recommendation/approve`), which
   dispatches the resources.
5. If a field report says a resource can't reach the scene (e.g. a road
   block), n8n calls `.../disruptions`, then submits the AI's replacement
   plan with `.../recommendation/replacement`. The coordinator approves it
   like any other plan.
6. n8n polls `GET /activity-log?since=<timestamp>` and/or `GET /dashboard`
   to drive notifications and the operator view.

## Example AI → backend payloads

**Reporting a new incident** (`POST /incidents`):

```json
{
  "location": "Krishna Apartments, Block C",
  "latitude": 12.9352,
  "longitude": 77.6146,
  "type": "flood",
  "severity": "CRITICAL",
  "people_affected": 4,
  "needs": ["medical", "evacuation"],
  "confidence": 0.88,
  "priority_score": 94,
  "report_metadata": {
    "channel": "whatsapp",
    "raw_text": "Water entering Krishna Apartments Block C. My grandmother cannot walk."
  }
}
```

`report_metadata` is not stored on the incident row — it's recorded into
the `incident_received` action-log entry for provenance (source channel,
raw text, merged report IDs, etc.).

**Submitting the initial plan** (`POST /integration/v1/incidents/INC-1042/recommendation`):

```json
{
  "recommended_resources": ["AMB-02", "RESCUE-01"],
  "reason": "plan.reason",
  "explanation": [
    {"key": "explain.distance", "params": {"id": "AMB-02", "distance": 2.1}},
    {"key": "explain.water", "params": {"id": "RESCUE-01"}}
  ],
  "confidence": 0.91,
  "priority_score": 94,
  "analysis_revision": "analysis-1"
}
```

`reason` and explanation `key`s are frontend catalog keys; the backend
stores them as-is. Resending the same `analysis_revision` with the same plan
returns the existing recommendation (`200`) instead of creating another;
with a different plan it's a `409 IDEMPOTENCY_CONFLICT`.

**Approving it** (`POST .../recommendation/approve`, coordinator key):

```json
{"version": 1}
```

`approved_by` is never accepted from the body — it's derived from the key.

## Replacement flow

The road-block scenario: a dispatched resource can no longer reach the
incident. Every step is a separate call, and nothing is released or
dispatched until the coordinator approves the replacement.

1. **Report the disruption** (`POST .../disruptions`):

   ```json
   {"resource_id": "AMB-02", "eta_minutes": 24, "previous_eta_minutes": 6, "reason": "road_blocked"}
   ```

   The assignment's ETA is revised (the old one kept in
   `previous_eta_minutes`), the incident moves to `blocked`, and
   `AMB-02` stays `DISPATCHED`.

2. **Propose the replacement** (`POST .../recommendation/replacement`):

   ```json
   {
     "base_version": 1,
     "replacement_for": "AMB-02",
     "recommended_resources": ["AMB-05", "RESCUE-01"],
     "reason": "plan.replacementReason",
     "explanation": [
       {"key": "explain.blocked", "params": {"id": "AMB-02", "old": 6, "eta": 24}},
       {"key": "explain.available", "params": {"id": "AMB-05"}}
     ],
     "analysis_revision": "analysis-2"
   }
   ```

   `recommended_resources` is the *complete* new plan, continuing responders
   included. `base_version` must be the currently approved version (else
   `409 STALE_PLAN`). This creates pending v2 and moves the incident to
   `awaiting_replacement`.

3. **Approve it** (`POST .../recommendation/approve` with `{"version": 2}`,
   coordinator key). In one transaction, locked incident → recommendation →
   live assignments → resources (by ID):
   - responders no longer in the plan: assignment `SUPERSEDED` (kept
     forever), resource back to `AVAILABLE`;
   - continuing responders: untouched (same assignment row);
   - newcomers: must all be `AVAILABLE` (else `409 RESOURCE_UNAVAILABLE`
     and *nothing* changes), then dispatched with new assignments that
     reference v2.

   The incident returns to `dispatched`. Any failure — including the
   partial-unique-index backstop catching a race — rolls back everything.

Each step is written to `action_logs` (`road_block_detected`,
`replanning_started`, `replacement_recommended`, `approval_requested`,
`replacement_approved`, `assignment_superseded`, `resource_dispatched`,
`redispatched`).

The old `POST /replanning` endpoint, which swapped resources without
approval, has been removed.
