# Team contract inventory — source inspection

Inspected 2026-09-20. This describes checked-in behavior, not a deployed service or a claim that teammate tests were run. Proposed changes and ownership are in [TEAM_INTEGRATION_PLAN.md](TEAM_INTEGRATION_PLAN.md). Existing frontend method signatures remain in [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md).

## Exact source baselines

| Remote branch | Full inspected SHA | Finding |
| --- | --- | --- |
| frontend | `6026a6b0dc5158745e0da16352082a1f498b355b` | Working mock-backed Next.js UI; both approval gates; resolved/history behavior |
| backend | `c42d375e6e8238cd54fa87715dbe03973da6ca8c` | FastAPI/SQLAlchemy/PostgreSQL operational CRUD and assignment/replanning transactions |
| ai/ml | `7a58ba7858e8289eb9155a0123c3c600592c985b` | FastAPI extraction, deterministic scoring, semantic deduplication, fixed recommendation stub |
| main | `987253e300cbcd75221054c23eaf99bb1185c3d5` | Empty tracked tree; untouched |

All remote heads were fetched explicitly, including heads outside the clone's frontend-only fetch refspec. No additional branch appeared relative to the preceding completion pass. No n8n, automation, workflow, database or integration branch exists in this snapshot. No n8n workflow files were found in the teammate trees inspected. **PERSON 4 HAS NOT PUBLISHED THE N8N WORK YET.**

Source links below are pinned so later teammate changes do not silently change the evidence:

- [Backend source tree](https://github.com/shawryuhh/HackSprint/tree/c42d375e6e8238cd54fa87715dbe03973da6ca8c/backend): all routes, schemas, models, services, core configuration/security, DB session, initial migration, Alembic environment/config/template, seed, tests, requirements, environment example and README were inspected read-only.
- [AI implementation](https://github.com/shawryuhh/HackSprint/blob/7a58ba7858e8289eb9155a0123c3c600592c985b/ai/main.py), [AI tests](https://github.com/shawryuhh/HackSprint/blob/7a58ba7858e8289eb9155a0123c3c600592c985b/tests/test_ai.py), README and requirements were inspected read-only.
- Frontend: the four requested handoff/QA documents, contracts, types, API selection/configuration, response context and mock service were read. Canonical fixture, command-center and recommendation/disruption rendering were also inspected to resolve mapping questions.

The older handoff documents record historical inspections. Their statements that no backend/AI branches existed were true of those inspections; this inventory is the current comparison.

## Backend: exact endpoint inventory

Paths are unversioned. Success returns a bare object/list, not a `{data: ...}` envelope. Unless noted, reads/updates return 200, creates 201. All operational routers use optional `verify_api_key`; `/health` does not. Framework `/docs`, `/redoc` and `/openapi.json` are also enabled without that router dependency.

`?` in the following schema definitions means optional input; `nullable` describes actual response nullability. Every list uses `limit=100` (1–500), `offset=0` (>=0), except the dashboard's separate activity limit.

| Method/path | Request/query | Successful response | Domain failures / behavior |
| --- | --- | --- | --- |
| GET `/health` | None | `{status: "ok" or "degraded", environment, database: "ok" or error text}` | Executes `SELECT 1`; caught DB query failures still return HTTP 200/degraded. Configuration/import failures can prevent startup. |
| POST `/incidents` | IncidentCreate below | IncidentResponse, 201 | Creates UNASSIGNED; persists report metadata only in intake audit. |
| GET `/incidents` | `status`, `severity` (unvalidated string), `type`, `min_priority` 0–100, pagination | IncidentResponse[] | Newest created first; includes terminal incidents unless filtered. |
| GET `/incidents/{id}` | Path ID | IncidentResponse | 404 absent. |
| PATCH `/incidents/{id}` | IncidentUpdate | IncidentResponse | 404; no expected version, no phase check, no row lock. |
| POST `/incidents/{id}/resolve` | Optional `{reason?: string or null}` | IncidentResponse | 404/409; only ACTIVE → RESOLVED; does not finish assignments or free resources. |
| POST `/incidents/{id}/cancel` | Same optional reason body | IncidentResponse | 404/409; source state table also allows ACTIVE, despite route description mentioning only UNASSIGNED/ASSIGNED. No assignment/resource cleanup. |
| POST `/resources` | ResourceCreate | ResourceResponse, 201 | Always initially AVAILABLE. |
| GET `/resources` | `status`, `type`, pagination | ResourceResponse[] | Newest created first. |
| GET `/resources/{id}` | Path ID | ResourceResponse | 404 absent. |
| POST `/resources/{id}/status` | `{resource_id, status, reason?}` | ResourceResponse | 404/409/422; body ID must equal path. Direct status writes do not create/close assignments. |
| POST `/assignments` | AssignmentCreate | AssignmentResponse[], 201 | 404 missing entities, 409 terminal incident/unavailable/race. Immediately marks resources DISPATCHED. No persisted approval gate. |
| GET `/assignments` | `incident_id`, `resource_id`, `status`, pagination | AssignmentResponse[] | Includes historical assignments; newest created first. |
| GET `/assignments/{id}` | Path ID | AssignmentResponse | 404 absent. |
| POST `/assignments/{id}/status` | `{status, reason?}` | AssignmentResponse | 404/409/422; ACTIVE, COMPLETED, CANCELLED allowed according to state table; direct SUPERSEDED forbidden. |
| POST `/replanning` | ReplanningRequest | `{incident, superseded_assignment, new_assignments}`, 201 | 404/409/422; immediately replaces and dispatches. Not a pending recommendation operation. |
| POST `/activity-log` | ActionLogCreate | ActionLogResponse, 201 | 422 for foreign keys that do not exist. Does not change incident/assignment state. |
| GET `/activity-log` | `source`, `action`, `incident_id`, `resource_id`, `assignment_id`, inclusive `since` datetime, pagination | ActionLogResponse[] | Newest timestamp first; no ID tie-breaker/cursor. |
| GET `/activity-log/{log_id}` | Integer path ID | ActionLogResponse | 404 absent. No PATCH/PUT/DELETE audit routes. |
| GET `/dashboard` | `activity_limit=20`, range 1–200 | DashboardResponse below | Active incident list only; recent audit only; no recommendation collection or full assignment history. |

There is no recommendation read/create/approve/modify/reject endpoint, no raw-report or report-translation endpoint, no dedicated road-obstruction/ETA endpoint, no AI client, no n8n command delivery endpoint, and no WebSocket/SSE route.

### Actual request/response fields

| Schema | Fields and constraints |
| --- | --- |
| IncidentCreate | Required `location` nonempty string, `type` nonempty free text, `severity` enum. Optional nullable `latitude` [-90,90], `longitude` [-180,180], `people_affected` integer >=0, `confidence` [0,1], `priority_score` integer [0,100], `report_metadata` arbitrary object. `needs` defaults to `[]`. No client-selected ID, original report collection, vulnerabilities or duplicate count. |
| IncidentUpdate | Optional nullable `location`, coordinates, severity, priority, confidence, people, needs. No type/status/version input. Uses `exclude_unset=True`, so explicit null for DB-nonnullable fields can reach an integrity failure rather than a well-defined domain validation error. |
| IncidentResponse | `id, location, latitude?, longitude?, type, severity, priority_score?, confidence?, people_affected?, needs, status, created_at, updated_at, current_assignments`. Question marks here indicate nullable values. Current assignments contains only ASSIGNED/ACTIVE rows. |
| ResourceCreate | Required nonempty `type`, `location`; optional nullable bounded coordinates and nonnegative `capacity`; `capabilities=[]`. No ETA/distance/name/assignedIncident fields. |
| ResourceResponse | `id, type, location, latitude?, longitude?, capabilities, status, capacity?, created_at, updated_at`. Assignment relation must be joined from assignment data. Capacity is descriptive; not consumed by dispatch. |
| AssignmentCreate | Required `incident_id`, `resource_ids` nonempty list, `decision_source` arbitrary string. Optional nullable `approved_by`, `reason`, `ai_recommendation`. Resource IDs are deduplicated by locking helper; duplicate input is not explicitly rejected here. |
| AssignmentResponse | `id, incident_id, resource_id, status, assigned_at, completed_at?, decision_source, approved_by?, created_at, updated_at`. No recommendation ID/version. |
| AIRecommendation embedded input | `incident_id`, `priority_score` integer [0,100], nonempty `recommended_resources`, `reason` text, `approval_required=true`, optional confidence [0,1]. Stored as action-log metadata only when passed to assignment/replan; not independently persisted or read as a pending plan. Not validated against actual assignment incident/resource selection. |
| ReplanningRequest | Required `incident_id, old_resource_id, new_resource_ids` nonempty list, `reason, decision_source`; optional `old_assignment_id, approved_by, ai_recommendation`. New IDs must exclude old resource. No expected recommendation version. |
| ActionLogCreate | Required arbitrary strings `source, action`; optional `reason, result, incident_id, resource_id, assignment_id, metadata` (nested arbitrary JSON). Metadata is not constrained to frontend's flat string/number values. |
| ActionLogResponse | Integer `id`, timestamp, source, action, nullable reason/result/foreign IDs/metadata. Pydantic maps ORM `log_metadata` to response `metadata`. |
| DashboardResponse | `incident_counts:{by_status,by_severity,critical_count,high_priority_count}`, `resource_counts:{by_status,by_type,available_count}`, `active_assignments_count`, `recent_activity`, `current_incidents`, `current_resources`. Counts are live queries, not cached tables. High priority is HIGH/CRITICAL severity, not a numeric priority cutoff. |

### Enums and transitions actually implemented

- Incident statuses: UNASSIGNED, ASSIGNED, ACTIVE, RESOLVED, CANCELLED.
- Resource statuses: AVAILABLE, DISPATCHED, ACTIVE, UNAVAILABLE.
- Assignment statuses: ASSIGNED, ACTIVE, COMPLETED, CANCELLED, SUPERSEDED.
- Severity: LOW, MEDIUM, HIGH, CRITICAL (four buckets, unlike frontend's five-point severity).
- Incident types and resource types are free strings, not enums. Reference incident values: flood, medical, fire, structural_collapse, other. Resource values: ambulance, rescue_unit, volunteer, shelter, hospital.
- Resource transitions: AVAILABLE → DISPATCHED/UNAVAILABLE; DISPATCHED → ACTIVE/AVAILABLE/UNAVAILABLE; ACTIVE → AVAILABLE/UNAVAILABLE; UNAVAILABLE → AVAILABLE. Same-state calls conflict.
- Incident transition table: UNASSIGNED → ASSIGNED/CANCELLED; ASSIGNED → ACTIVE/UNASSIGNED/CANCELLED; ACTIVE → RESOLVED/CANCELLED; terminal states have no exits.
- Assignment table: ASSIGNED → ACTIVE/CANCELLED/SUPERSEDED; ACTIVE → COMPLETED/CANCELLED/SUPERSEDED; terminal states have no exits. ASSIGNED → COMPLETED currently conflicts.

**Reachability defect:** only assignment creation changes an incident to ASSIGNED. The assignment-status service changes the assignment and resource but never changes the incident to ACTIVE. Incident PATCH cannot set status. Therefore the normal public create → assign → activate-assignment path cannot reach an incident state accepted by `/resolve`. The seed also stops at ASSIGNED. This is a source-level finding, not a runtime test claim.

**Terminal consistency defect:** resolve/cancel update just incident and audit; even a separately initialized ACTIVE incident can resolve with live assignments and unavailable resources remaining. Cancellation from ASSIGNED has the same cleanup gap.

### What is already transaction-safe, and what is not

`assignment_service.create_assignment` locks the incident then all resource rows in sorted ID order, validates availability, writes assignments/resources/incident/audit in one commit, and rolls back on failure. A PostgreSQL partial unique index permits at most one ASSIGNED/ACTIVE assignment per resource. Integrity races become 409. This is useful existing implementation and should be retained.

`replanning_service.replan` locks incident, old assignment, then sorted old/new resource rows. It checks the old assignment is still live, validates replacements, marks old assignment SUPERSEDED, releases old resource, creates replacement assignments and marks their resources DISPATCHED in one transaction. Other existing responders are not touched. If a replacement is unavailable, the old response stays intact. The old assignment is kept; its `completed_at` is not set by this flow. Duplicate new IDs are not explicitly validated: iterating them can cause a transition conflict and rollback.

These operations enforce exclusivity, **not approval**. `approved_by` may be omitted or spoofed; `decision_source="ai"` is accepted. `approval_required` is logged but not enforced. Capability coverage (ambulance plus water rescue), recommendation identity/version and resource-selection agreement are not checked. Pending plans have no reservation model because they do not exist yet.

Assignment lifecycle writes lock assignment and resource and atomically free resources on COMPLETED/CANCELLED. Incident updates/resolve/cancel and direct resource status updates do not use the same locking discipline. Direct resource status can say AVAILABLE while a live assignment still exists, or DISPATCHED with no assignment. The partial index still protects assignment inserts, but visible state can be inconsistent. Coordinate these write paths before adding approval transactions.

Dashboard aggregation performs multiple reads in a normal session; no explicit repeatable-read snapshot/isolation setting or revision is configured. Under concurrent changes, using the same database does not by itself guarantee a coherent multi-query snapshot. `current_incidents` excludes RESOLVED/CANCELLED; that cannot directly replace the frontend incident collection without breaking History. `recent_activity` is limited and sorted descending, while the frontend expects oldest-first retained lifecycle evidence.

### Errors, auth, CORS and persistence

- Domain NotFound/Conflict/ValidationFailed handlers emit 404/409/422 with `{detail: string}`. Missing/incorrect API key emits 401 with the same string-detail shape.
- Contrary to the broad `ErrorResponse` docstring, ordinary FastAPI/Pydantic request validation still uses `{detail: [...]}`. No global request-validation override exists. Some other exceptions are unnormalized 500s. No stable machine-readable error codes, request IDs, auth roles or coordinator identity are implemented.
- `AUTH_ENABLED=false` by default; when true, operational routes check one shared `X-API-Key`. AI, automation and human callers are not distinguished. Do not put this privileged shared key in frontend public configuration.
- CORS allows configured origins, credentials, every method and every header. Default origins is `*`. Explicit frontend origins and the chosen credential policy must be agreed before browser integration.
- PostgreSQL persists incidents, resources, assignments and action_logs. ARRAY columns hold needs/capabilities; JSONB holds log metadata. One initial migration `f72a07645e04`; sequences generate incident/assignment/resource IDs. No report, recommendation, translation, idempotency receipt or dispatch-command table exists.
- API audit is append-only by absence of mutation routes; no database-level append-only enforcement is implemented.
- Environment: `DATABASE_URL` is required by Settings (the README/example value is not a code default); `AUTH_ENABLED=false`, `API_KEY=""`, `CORS_ORIGINS="*"`, `APP_ENV="local"`. `.env` is loaded by pydantic-settings. `TEST_DATABASE_URL` is consumed only by tests.
- The test fixture defaults to a fixed localhost `reliefmesh_test` URL; it does not derive host/credentials from the development DATABASE_URL despite README wording. It creates/migrates the test DB and truncates app tables **before** tests. Tests must be run only with an explicitly disposable TEST_DATABASE_URL; the code does not prove a custom override differs from a live database.

### Seed and test evidence

The seed creates ten resources (including unsupported frontend `volunteer`), then INC-1042, then assigns and replans immediately. Its ambulance capability is generic `medical`, not evidence of advanced life support. Resource coordinates and ETAs are absent. Incident seed uses people=4, confidence=.88 and coordinates 12.9352/77.6146; frontend uses 3, .91 and 12.9347/77.6269. Frontend source text itself does not establish the people count. These are conflicting synthetic fixtures requiring agreement, not facts to silently translate.

The seed does **not** resolve, despite README “fully resolved narrative” wording. It does not pause for approvals. `--fleet-only` skips the narrative. Repeated narrative seeding without a clean disposable database can collide because it forcibly resets incident/assignment sequence positions and uses fixed resource IDs. Do not use this script to reset a shared live database or a browser-run historical record.

There are **41 test functions**, inspected but not executed this documentation pass: activity log 6, assignments 11, dashboard 3, health 1, incidents 4, replanning 10, resources 6. They cover CRUD, transitions, rollback, assignment and replan races against real PostgreSQL, audit retention and current-state aggregation. They do not cover verified approvals/version conflicts, successful incident resolution with resource cleanup, raw-report retention, AI calls, translation or n8n retries. The dashboard test named “excludes resolved” actually cancels an incident. Existing tests explicitly allow assignments without `approved_by`; later approval enforcement must update those fixtures while retaining their transaction assertions.

## AI/ML: actual operations

These are independent endpoints; no pipeline connects them to each other, backend or n8n. No persistence, resource mutation, HTTP authentication, CORS middleware or event transport is implemented here.

| Operation | Request | Response | Errors | LLM / determinism | Frontend compatibility |
| --- | --- | --- | --- | --- | --- |
| GET `/ai/health` | None | `status="healthy", service, model="gemini-3.6-flash", api_key_configured` | No provider call; can say healthy with no key | No LLM; deterministic given process env | Does not establish provider readiness or match ServiceHealth |
| POST `/ai/analyze-incident` | No body schema | Fixed `incident_id="INC-1042", priority_score=94, confidence=.91, recommended_resources=[AMB-02,RESCUE-01], reason` prose, `approval_required=true` | No explicit domain errors | No LLM; deterministic **mock** | Missing version/state/replacement/explanation; not based on actual incident/resources |
| POST `/ai/extract-incident` | `{text: string}` | ExtractedIncident below | Request 422; provider/parsing/etc exceptions become 500 `{detail:str(exception)}` | Gemini structured output, temperature=0; not guaranteed repeatable | Useful analysis; not Incident, not an original-preserving translation |
| POST `/ai/score-incident` | AdvancedScoreRequest below | `priority_score:int, risk_level:string, requires_human_review:bool, scoring_breakdown:dict` | Request type/missing-field 422; no custom numeric-range validation/error handler | Pure math; deterministic for validated finite inputs | Priority is usable; review flag is not dispatch approval; not a Recommendation |
| POST `/ai/deduplicate-incident` | `{new_report_text, active_incidents:[{incident_id,location,incident_type,summary_text}]}` | `{is_duplicate, matched_incident_id:string or null, similarity_reason}` | Request 422; provider/parsing exceptions 500 raw detail | Gemini structured output, temperature=0; not guaranteed repeatable | Returns a suggestion, not a merge; no membership/active-state validation of matched ID |

### Extraction and scoring schemas

ExtractedIncident fields, all required: `location:string`, `incident_type:string`, `people_affected:int`, `vulnerable_groups:string[]`, `medical_urgency:bool`, `severity_score:int`, `time_sensitivity_hours:float`, `environmental_threat:bool`, `confidence_score:float`.

AdvancedScoreRequest has those same fields, except confidence defaults to 1.0. The extraction/scoring Field descriptions mention ranges, but actual `ge/le` constraints are absent. People can be negative, severity can be outside 1–5, confidence outside 0–1; vocabulary and uniqueness are also unenforced. Location and report text have no minimum length. The prompt normalizes extracted text to English but returns no originalText/originalLanguage/receivedAt, report ID, coordinates, needs or frontend vulnerability code. `elderly`/`disabled` do not automatically equal the frontend's `elderly_mobility` (mobility must be evidenced).

Scoring implemented:

- Severity: `(severity_score/5)*35`; medical urgency adds 25.
- Vulnerabilities: `min(number of entries*7.5,15)`; duplicate strings are currently counted.
- Environmental threat adds 10.
- Time: `max(round(10*exp(-.35*max(0,hours)),1),1)`.
- Scale: if people>1, `min(round(log10(people)*5,1),10)`, otherwise 0.
- `building_collapse`, `dam_breach`, `active_fire`, `hazmat_leak` get a floor of 85 **before** confidence reduction. Extractor example `fire` does not trigger `active_fire` automatically.
- Confidence<.75 sets requires_human_review. Confidence<.6 multiplies score by .85: a **15% reduction**, not an 85% reduction. This can bring a critical-type score below 85. Final result is rounded/clamped to 0–100.
- Risk thresholds: Critical>=80, High>=60, Medium>=40, else Low. Risk level and backend severity are distinct concepts unless the team agrees a conversion.

A source-isolated execution of this checked-in pure scoring function produced **94** for this **proposed synthetic fixture**, without provider calls: people=3, severity=5, vulnerable_groups=[elderly,limited_mobility], medical_urgency=true, environmental_threat=true, hours=1, confidence=.91. Contributions were 35+25+15+10+7+2.4 = 94.4, rounded to 94. This proves a deterministic fixture is possible; it does not prove the LLM will extract these fields from the short original report or that these assumptions are true. Agree and label supplied scenario context before using it.

### Gemini, structured output, fallbacks and tests

Both LLM endpoints construct `ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)` and call `with_structured_output(...)`. Their async routes use synchronous `chain.invoke`, which can block the event loop. The source does not configure explicit timeouts, retries, model selection via env, a fallback or exception redaction. Library defaults are not a tested fallback policy.

Health checks GOOGLE_API_KEY or GEMINI_API_KEY, but the constructor does not explicitly choose/pass either; provider/library environment behavior has not been verified in this pass. `python-dotenv` is listed, but no `load_dotenv()` is called and the README's `uvicorn main:app --reload` does not explicitly load an env file. Therefore the documented .env setup is not demonstrated by application code. The model string's availability for the teammate's account is also unverified; Person 3 must show a real health/provider smoke test using a supported configured model. Both backend and AI README commands default to port 8000: agree separate ports (proposed backend 8000, AI 8001).

No live initial/replacement resource selector, typed recommendation explanations, translation endpoint, original report retention or fallback recommendation exists. `similarity_reason` is dedup prose and `scoring_breakdown` explains arithmetic; neither replaces frontend resource-selection explanations. “Multilingual extraction” does not prove translation support for all 13 target languages. The AI cannot itself prevent duplicate dispatch: backend merge/assignment constraints must enforce that.

Requirements use broad minimum versions, not a reproducible lock. There are **3 test functions**, inspected but not executed here: health status, one critical score case, one mocked extraction. No dedup, recommendation, translation, invalid-range, failure, canonical-94 or live-provider coverage exists. The mocked extraction test patches the model object inside a LangChain composition; a green run on the selected dependency versions must be supplied rather than assumed. README says to run pytest inside `ai`, but the tests are in root `tests/test_ai.py`; run from repository root after installing AI dependencies.

## Verification scope of this documentation pass

No backend server/database or paid Gemini request was started. No teammate branch was checked out or edited. Test counts above are static AST counts, not pass counts. The only executed teammate calculation was the pure scoring function described above. Frontend application source, tests, dependencies and mock selection remain unchanged; prior 14-test/browser results belong to the completed frontend pass, not a new integration test result.
