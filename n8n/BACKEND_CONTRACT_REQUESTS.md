# Person 2 handoff — PROPOSED, NOT AGREED OR IMPLEMENTED

Inspected 2026-09-20: frontend `fc2d69a62caaebe4bcd1ba286741598225ae2299`, backend `c42d375e6e8238cd54fa87715dbe03973da6ca8c`, AI `7a58ba7858e8289eb9155a0123c3c600592c985b`.
Read the three documents directly from `origin/frontend` and the backend route/service/auth source and `ai/main.py` read-only. No teammate was contacted and no endpoint agreement is claimed. Person 2 must review this proposal and publish OpenAPI plus examples before a live adapter is written. The exports use **only `/fixture/...` on loopback**; none of the proposed production URLs below is wired into a node.

## Implemented versus missing

| Inspected implementation | Actual behavior | Automation decision |
| --- | --- | --- |
| POST `/incidents` | Structured incident, caller-supplied analysis fields; report metadata is audit data | Not immutable raw-report intake; do not substitute |
| POST `/assignments` | Immediately reserves/dispatches resources; `approved_by` optional, caller supplied | Forbidden shortcut; lacks gate #1 |
| POST `/replanning` | Immediately supersedes/swaps resources | Forbidden shortcut; lacks gate #2 |
| POST `/assignments/{id}/status` | Changes assignment/resource status | Not an authorized command callback |
| POST `/incidents/{id}/resolve` | Requires ACTIVE; updates incident, no full resource cleanup | Not safe completion ingestion; ordinary assignment flow never advances incident to ACTIVE |
| POST `/activity-log` | Appends a log only | A log is neither approval nor command |
| Shared optional `X-API-Key` | No coordinator/automation role distinction | Insufficient for live approval security |
| AI extract / score / deduplicate | Separate operations; Gemini extraction/dedup, deterministic score | Backend should orchestrate them |
| AI POST `/ai/analyze-incident` | Fixed INC-1042 recommendation | Not a live recommendation or authorization |
| `/integration/v1/*` below | No routes/models at inspected backend SHA | All remain blocked proposals |

## Exact requested contracts (all paths pending Person 2 agreement)

Keep the handoff's shared automation event entry point for raw intake, obstruction and completion. Do not introduce a second analysis pipeline in n8n.

| Proposed endpoint | Request | Successful response | Required Person 2 work |
| --- | --- | --- | --- |
| POST `/integration/v1/automation/events` | Event envelope below; `Idempotency-Key: event_id`; scoped automation credential | First: 202 `{event_id,accepted:true,duplicate:false,incident_id,revision}`; replay: 200 same receipt with `duplicate:true` | Persistent immutable report + unique receipt; authenticated producer; backend AI orchestration; validated obstruction/completion handlers |
| GET `/integration/v1/automation/commands?state=pending` | Automation credential; no body | 200 `{command_ids:["..."],phase,version}` for the canonical fixture; general live queue should omit single-incident phase/version or provide per-incident metadata | Durable transactional outbox; return eligible authorized commands only; agree production pagination and empty-queue shape |
| POST `/integration/v1/automation/commands/{id}/claim` | `{worker_id}`; stable claim-request idempotency key | 200 `{command: <claimed command below>,duplicate:false}` | Atomic exclusive claim, 180s lease proposal, bounded reclaim count (3), receipt replay; no claim for terminal/obsolete/failed command |
| POST `/integration/v1/automation/commands/{id}/validate` | `{claim_token}` | 200 `{valid:true,command:<same immutable command and lease>}` | **Additional proposal** required by handoff's pre-delivery revalidation: check approval, lease, current plan, assignment and incident lifecycle |
| POST `/integration/v1/automation/commands/{id}/result` | `{event_id,claim_token,outcome:"accepted"|"failed",occurred_at,delivery_reference?,error_code?}`; `Idempotency-Key: event_id` | 200 `{accepted:true,command_id,duplicate:false}`; exact replay duplicate=true | Durable result receipt, delivery status distinct from dispatch authorization; ignore/reject stale callbacks without applying old state |
| POST `/integration/v1/incidents/{id}/recommendation/approve` | `{version}` + authenticated coordinator + request key | 204 after commit | Frontend-only human intent, derive actor from auth; transaction commits approval, assignment delta, stable audit and command together; deny automation |
| GET `/integration/v1/snapshot` | Frontend authenticated read | Coherent revision, original reports, current plans, all assignments, operational events/history | Live integration evidence and frontend adapter prerequisite |

No real responder delivery endpoint is requested from Person 2: `/fixture/receiver/deliver` is the synthetic receiver, not a production backend route. `/fixture/failures` and `/fixture/control/*` are test utilities, not production proposals. In live mode, n8n saves execution failures and the backend persists command failure/reclaim state. Agree any durable operational failure API separately.

### Event envelope

```json
{
  "schema_version": 1,
  "event_id": "demo-run-01-report-01",
  "event_type": "report_received",
  "occurred_at": "2026-09-20T10:00:00Z",
  "source": "synthetic-demo",
  "correlation_id": "demo-run-01",
  "payload": {
    "source_report_id": "synthetic-report-01",
    "channel": "synthetic",
    "originalText": "Water entering Krishna Apartments Block C. My grandmother cannot walk.",
    "originalLanguage": "en",
    "receivedAt": "2026-09-20T10:00:00Z"
  }
}
```

Intake omits incident ID: backend creates or relates it. Preserve originalText, originalLanguage and receivedAt exactly; normalize only transport timestamp/source. Store submitted original report before AI processing. `accepted` acknowledges persistence, not successful analysis or dispatch. The short report does not establish a count of three or priority 94; this fixture service does not claim extraction or scoring.

Obstruction uses the same envelope with `event_type:"road_obstruction"`, `incident_id:"INC-1042"`, **proposed additional** `expected_version:1`, and payload:

```json
{"assignment_id":"ASG-887","resource_id":"AMB-02","previous_eta_minutes":6,"eta_minutes":24,"reason_code":"road_blocked"}
```

Backend validates the current assignment and version, records ETA, orchestrates AI, and persists **pending** replacement. Use backend-returned assignment IDs in a real run. The fixture IDs are never portable live IDs.

Completion uses `event_type:"response_completed"`, `incident_id:"INC-1042"`, `expected_version:2`, and:

```json
{"assignment_ids":["ASG-888","ASG-889"],"evidence":"simulated responder completion"}
```

Backend verifies the complete current assignment set, authenticated simulation capability (demo environment only), delivery/lifecycle and version, then atomically resolves, releases resources, cancels undelivered commands and preserves audit/history. Superseded AMB-02 stays historical. Agree the real completion evidence policy separately.

### Authorized command example (issued only after gate #2)

```json
{
  "command_id": "fixture-INC-1042-v2",
  "incident_id": "INC-1042",
  "recommendation_version": 2,
  "action": "redispatch",
  "authorization": {"approval_id":"fixture-approval-2","actor":"fixture-coordinator","version":2},
  "approved_resource_ids": ["AMB-05","RESCUE-01"],
  "new_assignments": [{"assignment_id":"ASG-889","resource_id":"AMB-05"}],
  "continuing_assignment_ids": ["ASG-888"],
  "superseded_assignment_ids": ["ASG-887"],
  "state": "claimed",
  "claim_attempts": 1,
  "claim_token": "RUNTIME_VALUE_NOT_EXPORTED",
  "lease_expires_at": "RUNTIME_TIMESTAMP",
  "created_at": "RUNTIME_TIMESTAMP"
}
```

Gate #1 instead issues `action:dispatch`, v1, new assignments AMB-02/ASG-887 and RESCUE-01/ASG-888, empty continuing/superseded lists. The full approved resource set is for validation; **delivery uses only `new_assignments`**. AMB-02 release is a backend transaction, not n8n changing resource state. See `fixtures/initial-command.json` and `replacement-command.json` for illustrative pre-claim commands, not executable permissions.

Result event IDs are stable within a claim and outcome, e.g. `command_id:result:1:accepted`. Preserve the same body and event ID on retries. A new lease uses its own callback ID, but retains the original command ID/immutable delivery payload. Receiver dedup must use command ID and immutable body hash, excluding renewable lease metadata; changing the actual resource set under an existing command ID is always a conflict.

## Required invariants and error agreement

1. Persist unique `(authenticated producer,event_id)` and canonical body hash. Exact repeat returns original result, changed body returns 409 `IDEMPOTENCY_CONFLICT`. Retain receipts after resolution. Also deduplicate `(source identity,source_report_id)` if different delivery event IDs refer to the same source report; the single-case double deliberately rejects additional reports rather than implementing semantic merge.
2. Approval and replacement approval are **two separate authenticated coordinator transactions**. Pending/AI/audit data can never create a delivery command. Automation cannot approve, assign, replan directly, resolve directly or mutate resource statuses. Close existing bypass routes before enabling live mode.
3. Backend owns versions/IDs/assignments. Reject wrong incident/resource/assignment, stale versions, obsolete leases, superseded and terminal callbacks. Same accepted receipt replay may be returned without state change; stale command callbacks return 409. No terminal incident can be reactivated by replay or a new delivery ID.
4. Claim/revalidate/result operations lock and validate current state. Max three lease claims; expired third claims must become `failed`/`needs_operator` in the real backend, not remain invisible forever. The test double exposes attempt counts in snapshot; it is not a production sweeper.
5. State checks plus delivery idempotency do not prove exactly-once physical dispatch. Real receiver must support durable idempotency and a cancellation/fencing design for resolve/replacement racing with delivery. The local receiver rechecks authority inside the same serialized transaction; a real remote receiver cannot inherit that property automatically.
6. Stable errors `{code, ...safe details}`: 401 auth; 403 forbidden; 404 unknown; 409 stale/version/lease/state/idempotency; 422 invalid schema. Only network/429/5xx are retriable. Same IDs across attempts. Retry-After over 30s goes to operator attention rather than retrying early.
7. Live claim/auth tokens go in n8n credentials/runtime only, not source or logs. Separate coordinator and automation roles, HTTPS, identity-bound claims. `X-Fixture-Actor` is a publicly known local test role marker and **is not authentication**.
8. Event-age policy is not agreed. The fixture accepts historical synthetic timestamps for repeatable demos and rejects stale state/version/assignment, not elapsed age. Person 2 must agree freshness/skew limits before live rollout.

## Sign-off checklist for the later integration pass

Person 2 returns exact URLs/OpenAPI, payload examples, scoped credential setup, tested approval/command/resolve migrations, PostgreSQL concurrency results, and a reachable isolated demo backend. Persons 2/3 agree backend-owned AI orchestration. Person 4 then adds a separate live transport with explicit configuration, HTTPS credential references and real receiver policy; re-runs every rejection/duplicate/terminal test against that backend. Merely changing the fixture URL or setting an environment variable does not enable live execution in this branch.
