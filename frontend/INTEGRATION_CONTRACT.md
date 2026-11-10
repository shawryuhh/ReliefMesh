# ReliefMesh frontend integration contract

For the later backend/AI source comparison and proposed team alignment, see [TEAM_INTEGRATION_PLAN.md](TEAM_INTEGRATION_PLAN.md) and [TEAM_CONTRACT_INVENTORY.md](TEAM_CONTRACT_INVENTORY.md). The branch inventory below records the original inspection; the TypeScript service contract remains unchanged.

## Current integration status

The inspected repository is `shawryuhh/HackSprint`. The frontend baseline for this pass is `b8714c7`. All remote heads were fetched explicitly because the local clone originally had a single-branch fetch refspec.

| Remote branch | Inspected commit | Subsystem and findings |
| --- | --- | --- |
| `origin/frontend` | `b8714c7` at start of pass | Existing Next.js/React/TypeScript frontend, in-memory mock adapter, 13-language UI and local demo engine |
| `origin/main` | `987253e` | Empty tracked tree; history removes the frontend setup guide from main |

No separate backend, API, database, AI/ML, agent, n8n, workflow, automation or integration branch was published at inspection. No teammate endpoint, request schema, authentication implementation, environment configuration or WebSocket/SSE mechanism is available to compare. No branches were merged or cherry-picked.

This document specifies the **existing TypeScript service boundary**, not an implemented HTTP API. URLs, HTTP verbs, wire envelopes and authentication remain to be agreed with teammates. Nothing has been connected to a nonexistent endpoint.

## Where an adapter belongs

- `lib/services/contracts.ts`: `ReliefService`, `DemoService`, and `ServiceError` definitions.
- `types/index.ts`: shared domain objects and discriminated string unions.
- `lib/api/index.ts`: currently constructs `createMockService()` and exports it as both services. This is the future adapter-selection point.
- `state/response-context.tsx`: consumes snapshots and subscriptions, serializes UI actions, refreshes after mutation, and presents localized failures.
- `lib/api/config.ts`: `NEXT_PUBLIC_API_BASE_URL` is reserved only. Setting it currently does **not** enable a network adapter. It is public browser configuration, never a place for credentials.

No application authentication is implemented. The mock uses `approvedBy: "coordinator"`; this is not an authenticated identity. The backend must derive identity from a verified session/token. Do not send privileged keys to the browser.

## Service operations

Requests below are method arguments. Responses are resolved Promise values, with no HTTP wrapper expected by components. An HTTP adapter must validate and unwrap its wire response before returning these types.

| Operation | Request | Successful response / TypeScript type | Expected failure or absence |
| --- | --- | --- | --- |
| `getDashboard()` | No arguments | `Promise<DashboardSnapshot>`: incidents, resources, recommendations, assignments, activity, metrics, health, demoIndex, scenario | `ServiceError("error.api")` for failed reads. Empty collections are valid states. |
| `getIncidents()` | No arguments | `Promise<Incident[]>`; mock sorts by descending priority | API failure as above; no results gives `[]`. |
| `getIncident(id)` | `id: string`, e.g. `INC-1042` | `Promise<Incident \| undefined>` | Unknown ID resolves `undefined`, not a fabricated incident. Adapter maps a genuine not-found response to this result; transport failure remains an error. |
| `getResources()` | No arguments | `Promise<Resource[]>` with current status, capabilities and assignment | API failure as above; `[]` is accepted. The mock's unavailable-resource scenario retains records with unavailable status. |
| `getActivityLog()` | No arguments | `Promise<ActivityEvent[]>`; mock stores oldest first and UI reverses for display | API failure as above; no events gives `[]`. Agree ordering explicitly. |
| `getRecommendation(incidentId)` | `incidentId: string` | `Promise<Recommendation \| undefined>`; current plan, including its version | Missing current plan resolves `undefined`; transport failure is an error. |
| `approveRecommendation(incidentId, version)` | Incident ID and the **displayed** plan's numeric version | `Promise<void>`; refreshed snapshot contains approved plan, assignments, resource statuses and audit events | Stale/nonpending plan or wrong incident phase: `error.stalePlan`; unavailable/invalid resources: `error.resources`; missing ambulance/water rescue: `error.coverage`; operational failures below. |
| `modifyRecommendation(incidentId, resourceIds, version)` | Incident ID, unique `string[]` of selected resources, displayed version | `Promise<void>`; updated plan has a newer version and remains pending until explicit approval | Same version/phase/resource/coverage validation as approval. Cannot include the failed resource identified by `replacementFor`. |
| `rejectRecommendation(incidentId, reason, version)` | Incident ID, optional-reason text as `string` (empty allowed), displayed version | `Promise<void>`; initial plan rejection sets incident rejected; replacement rejection leaves incident blocked and existing responders dispatched | `error.stalePlan` and operational failures. Mock trims reason and limits it to 500 characters. No new dispatch occurs. |
| `createAssignment(incidentId, resourceId)` | Incident ID and resource ID | `Promise<Assignment>`; returns existing active assignment for the same pair if one exists | `error.approval` unless current plan is approved, resource belongs to that plan, and incident is dispatched; `error.resources` for missing/unavailable resources. Must not bypass approval. |
| `translateReport(report, language)` | Full `EmergencyReport` plus supported `Language` | `Promise<EmergencyReport>` retaining original fields and adding translatedText/translatedLanguage | `error.translation` when no translation is available. The current adapter only translates known fixtures; it does not translate arbitrary user reports. |
| `subscribe(listener)` | `listener: () => void` | Synchronous `() => void` unsubscribe function | Listener signals invalidation, not a payload. Context calls `getDashboard()` after notification. Reconnect/error semantics require an agreed network adapter. |

All three recommendation mutations return `void`, **not** the new plan. The UI already refreshes afterwards. A stale-version failure must leave state unchanged and require a refreshed plan before retrying.

## Domain payload expectations

| Type | Required fields / semantics |
| --- | --- |
| `Incident` | `id`, `location`, numeric `latitude`/`longitude`, `type`, `severity`, `priority`, `people`, `needs`, `confidence`, `status`, `vulnerabilities`, `reports`, `duplicates`. Current presentation expects at least one report. Severity is displayed out of 5, priority out of 100, confidence as a fraction multiplied by 100. |
| `EmergencyReport` | `id`, `originalText`, `originalLanguage`, ISO timestamp `receivedAt`; optional `translatedText`, `translatedLanguage`. Never replace the original text/language with a translation. |
| `Resource` | `id`, `type`, coordinates, `capabilities: string[]`, `status`, numeric `capacity`; optional `name`, `assignedIncident`, `eta` (minutes), `distanceKm`. An assigned resource's incident ID must refer to a known incident. |
| `Recommendation` | `incident`, `priority_score`, `recommended_resources: string[]`, `reason`, `approval_required`, `confidence`, `explanation`, `version`, `state`; optional `replacementFor`. IDs must reference resources. `version` increases when modifying/replacing a plan. |
| `RecommendationExplanation` | `key: string`, optional `params: Record<string, string \| number>`. Current UI recognizes `explain.distance`, `available`, `als`, `eta`, `water`, `priority`, `continues`, `blocked`, `selected` under the `explain.` prefix. See mapping below. |
| `Assignment` | `id`, `incidentId`, `resourceId`, `approvedBy`, ISO `createdAt`, status `dispatched \| released \| completed`. Identity and authorization must come from backend enforcement. |
| `ActivityEvent` | Stable unique `id`, ISO `timestamp`, `source`, `type`, `title`, `description`, `incidentId`; optional flat `metadata: Record<string, string \| number>`. Current title/description values are translation keys such as `events.approved` / `eventDescriptions.approved`. |
| `DashboardMetrics` | `criticalIncidents`, `activeIncidents`, `availableAmbulances`, `availableRescueTeams`. Must be consistent with the same snapshot's records. |
| `DashboardSnapshot` | `incidents`, `resources`, `recommendations`, `assignments`, `activity`, `metrics`, `health`, `demoIndex`, `scenario`. Lists form one coherent state, especially after approval and replacement. |

Domain union values must match `types/index.ts` exactly. Examples: resource types `ambulance/rescue/hospital/shelter`; the water-rescue capability is `water_rescue`; languages are `en/hi/kn/ta/te/ml/mr/bn/gu/pa/ur/as/or`. Preserve operational IDs literally in every language.

`reason` currently holds a localized catalog key such as `plan.reason` or `plan.modified`. Free-form AI prose is **not** a drop-in equivalent to localized keys. Teammates must agree on a structured explanation schema or explicitly extend the presentation contract before integration.

Explanation params used today: `{id, distance}` for distance, `{id, eta}` for ETA, `{id, old, eta}` for blocked ETA, and `{id}` for resource-specific facts. Unsupported explanation keys currently fall back to the modified-plan label, so do not introduce new keys without implementing their rendering.

## Events and update behavior

Supported events: `incident_received`, `duplicates_merged`, `priority_updated`, `recommendation_generated`, `approval_requested`, `approved`, `modified`, `rejected`, `resource_dispatched`, `road_block_detected`, `replanning_started`, `replacement_recommended`, `replacement_approved`, `redispatched`, `incident_resolved`.

Sources are `intake`, `ai`, `coordinator`, `automation`. Relevant metadata today includes:

- `resources`: display string containing operational IDs.
- `old` / `eta`: previous and new ETA in minutes; the route-disruption UI reads these from `road_block_detected`.
- `count`, `priority`, `people`: numeric audit facts.
- `reason`: rejection reason; rendered as text.

Example existing event shape:

```json
{
  "id": "EVT-example",
  "timestamp": "2026-09-19T12:00:00.000Z",
  "source": "automation",
  "type": "road_block_detected",
  "title": "events.road_block_detected",
  "description": "eventDescriptions.road_block_detected",
  "incidentId": "INC-1042",
  "metadata": { "resources": "AMB-02", "old": 6, "eta": 24 }
}
```

No WebSocket, SSE or polling transport exists yet. A future adapter can implement one and invoke subscribed listeners after new authoritative state becomes readable. Mutations must be atomic server-side; UI action serialization is not protection against two coordinators approving the same resource. Keep event IDs stable across refreshes to avoid duplicate “New” emphasis.

## Error normalization

Use `ServiceError(key)` at the adapter boundary. Unknown thrown errors become `error.api` in the response context. Do not expose raw server stack traces as UI copy.

- `error.api`: failed/unavailable read or generic operation failure.
- `error.stalePlan`: outdated version, no pending plan, missing incident/plan or incompatible phase in current mock behavior.
- `error.resources`: duplicate, empty, unknown, wrong-type or unavailable selection.
- `error.coverage`: missing ambulance or water-rescue capability.
- `error.approval`: assignment not authorized by an approved plan.
- `empty.incidents`, `empty.resources`, `notice.offline`: currently block operational writes in their respective simulation scenarios.
- `error.translation`: translation unavailable.
- `error.order`, `error.canonical`: demo sequencing/script constraints, not proposed backend business errors.

Authentication/authorization-specific errors are **not defined yet**. Before live integration, agree their handling and translations rather than disguising them as an empty dataset or automatically retrying a rejected action. HTTP status-to-key mappings are still undecided.

## Compatibility work that remains explicit

1. `ServiceHealth.mode` currently only accepts `"mock"`; `automation` accepts `"simulated" | "offline"`. A real health mode requires an agreed type and UI change.
2. `DashboardSnapshot.demoIndex` and `scenario` are demo-specific. Decide whether the adapter supplies compatibility values or a deliberate domain/presentation split is introduced. Do not fabricate a live demo state silently.
3. The canonical map disruption and autoplay are tied to `INC-1042`, AMB-02 and AMB-05. They are presentation fixtures, not a general road-obstruction/routing engine. Assignment lines are straight illustrative lines.
4. Both approvals must remain explicit server-authorized coordinator decisions. Replanning can create a pending replacement, never dispatch it automatically.
5. Replacement approval releases resources removed from the approved plan, keeps continuing responders, and dispatches replacements. Replacement rejection preserves currently dispatched responders. Validate versions and resource availability transactionally.
6. UI language persists locally; incidents and assignments currently reset on reload. Backend persistence and cross-client updates are not implemented.

## Teammate responsibilities

| Owner | Required before integration |
| --- | --- |
| Person 2 — backend/database/API | Agree endpoints and wire schemas; implement auth/roles, persistence, atomic version checks and resource reservation, all service operations, health and update transport. Supply OpenAPI/examples and error mappings for review. |
| Person 3 — AI/ML/translation | Produce typed incident/recommendation/explanation outputs, confidence/priority conventions and original-preserving translations. Coordinate localized explanation keys/schema and unsupported-translation behavior with frontend/backend. |
| Person 4 — n8n/automation | Send intake/duplicate/dispatch/monitoring/disruption/replanning/resolution events through the backend. Preserve approval boundaries, stable event IDs, delivery retries/deduplication and service-health signals. |

Review actual teammate branches and contracts when they appear. Compatibility documentation is not authorization to merge or switch the frontend to a live adapter automatically.
