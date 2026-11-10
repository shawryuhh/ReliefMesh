# ReliefMesh integration contract audit

Status: **read-only API review; no live adapter enabled**. Source: `integration` branch. This document records verified code-level observations, not passing integration tests.

## Current components
- Frontend `frontend/lib/api/index.ts` exports `createMockService()` for both `ReliefService` and `DemoService`; there is no live HTTP adapter.
- Frontend `frontend/lib/services/contracts.ts` requires dashboard, incidents, resources, activity, recommendation reads; approve/modify/reject, assignment creation, translation, and subscribe.
- Backend `GET /dashboard` returns `incident_counts`, `resource_counts`, `active_assignments_count`, `recent_activity`, `current_incidents`, `current_resources`. This is **not** the frontend `DashboardSnapshot` (which requires recommendations, assignments, metrics, health, demoIndex and scenario).
- Backend `GET /incidents`, `GET /incidents/{id}`, `GET /integration/v1/incidents/{id}/recommendation` and `POST /integration/v1/incidents/{id}/recommendation/approve` exist.
- Backend approve endpoint accepts versioned approval, derives actor from `require_coordinator`, and claims atomic dispatch in its route description. Confirm transactional invariants with live PostgreSQL tests.
- No frontend implementation for `modifyRecommendation`, `rejectRecommendation`, `translateReport` or `subscribe` against backend is present.
- n8n documentation identifies workflows as fixture-only, not a live backend connection.

## Contract mapping to implement
| Frontend operation | Backend candidate | Gap / required decision |
| --- | --- | --- |
| getDashboard | GET /dashboard plus collection endpoints | Compose a coherent snapshot including all assignments, recommendations, history and event IDs; do not invent missing fields. |
| getIncidents / getIncident | GET /incidents, GET /incidents/{id} | Explicit mapping for status, severity, coordinates, reports, vulnerabilities and language. |
| getResources | GET /resources | Normalize type/status and ETA; do not fabricate coordinates. |
| getActivityLog | GET /activity-log | Normalize event source/type and stable audit IDs. |
| getRecommendation | GET /integration/v1/incidents/{id}/recommendation | Normalize state, version, explanation and replacement reference. |
| approveRecommendation | POST /integration/v1/incidents/{id}/recommendation/approve | Match request version, coordinator-only identity and stale-version errors; never put privileged coordinator credentials in browser JS. |
| modifyRecommendation | No verified matching route in inspected recommendations router | Agree server-side versioned modification semantics before enabling. |
| rejectRecommendation | No verified matching route in inspected recommendations router | Agree server-side rejection semantics for initial vs replacement plan. |
| createAssignment | POST /assignments exists | Do not expose direct assignment as a browser bypass of approval; decide whether to remove from live UI interface. |
| translateReport | AI /ai/translate-report documented | Backend-owned proxy, authentication, original-text preservation and persistence required. |
| subscribe | No verified push endpoint | Poll coherent snapshots with revision/ETag or agree SSE; handle staleness and cancellation. |

## P0 integration decisions
1. Choose an authoritative backend snapshot schema and its revision/version semantics, including resolved incidents and immutable reports. Frontend `DashboardSnapshot` contains mock-only `demoIndex`, `scenario`, and `health.mode: "mock"`; separate these from live operational data.
2. Map backend status enums to frontend lifecycle states explicitly; never infer `awaiting_replacement`, `blocked` or `resolved` from missing information.
3. Define authenticated coordinator approval through a server-side session/proxy. Backend `AUTH_ENABLED=false` treats any caller as coordinator; prohibit that setting in deployed live mode. Restrict CORS and protect sensitive API keys.
4. Verify approve/replacement atomicity, stale-plan rejection, resource exclusivity and terminal cleanup with PostgreSQL concurrency tests.
5. Agree modify/reject APIs, translation handling, and automation event/command contracts before switching frontend or n8n out of demo mode.
6. Keep the existing frontend mock/demo and n8n fixtures operational and clearly labeled until a complete isolated end-to-end test passes.

## Proposed next implementation sequence
- Add versioned example JSON fixtures from the **current** backend for incident, resource, recommendation, dashboard, audit and assignment responses.
- Add adapter contract tests and an explicit opt-in live-mode adapter; default remains mock.
- Implement safe read-only polling first; then coordinator approval through authenticated server-side flow; finally integrate AI and n8n.
- Run unit, typecheck, production build, PostgreSQL concurrency and full browser lifecycle tests before any live-mode rollout.

Do not merge this branch to `main` or use for real emergency dispatch before these gates pass.
