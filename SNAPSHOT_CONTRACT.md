# ReliefMesh operational snapshot consistency contract

Status: **proposal for integration**, not a deployed endpoint.

## Problem
The development preview currently reads incidents, resources, assignments and per-incident recommendations in separate HTTP requests. Paginated requests can cross database transactions, so even complete pages may not describe one coherent instant. Do not label these collections as a live operational snapshot.

## Proposed endpoint
`GET /integration/v1/snapshot`

Authenticated read-only response, assembled in one consistent database read transaction (e.g. PostgreSQL REPEATABLE READ or a verified equivalent):

```json
{
  "schema_version": 1,
  "revision": "opaque-monotonic-revision",
  "generated_at": "2026-11-10T12:00:00Z",
  "incidents": [],
  "resources": [],
  "assignments": [],
  "recommendations": [],
  "activity": [],
  "complete": true
}
```

The empty arrays above are schema placeholders, not example operational data.

## Requirements
1. All included entities must be read under the same database snapshot. Use a server-generated monotonic revision that changes after committed operational writes. An ordinary timestamp alone does not prove consistency.
2. Include active and resolved incident history, immutable original reports, vulnerabilities and duplicate links; preserve nullable coordinates/priority/confidence rather than inventing values.
3. Include current and historical assignments, recommendation versions and approval state, and audit events with stable IDs. Define paging and completeness semantics for large histories.
4. Authenticate viewers with least privilege. Keep coordinator credentials and automation credentials server-side and separate. Never make this endpoint public by default.
5. A client must reject unknown schema versions, missing fields, inconsistent revision, truncated results, or invalid state transitions. Do not silently fall back to mock data on failure.
6. Frontend live mode remains opt-in and read-only until this contract is implemented, reviewed, and integration-tested. Human approval and dispatch stay disabled in the preview.

## Acceptance tests to implement
- Concurrent update during snapshot read does not mix before/after state.
- A resolved incident retains its reports, recommendation history, assignments and audit events.
- Pagination cannot silently omit records or repeat IDs.
- Invalid credentials receive 401/403; no privileged keys reach browser JavaScript.
- Revision changes after a committed write; stale snapshots are identified.
- Failure/timeout does not display synthetic data as real.

This document intentionally does not modify the running backend, schema or database transaction semantics.
