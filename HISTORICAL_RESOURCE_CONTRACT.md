# Historical resource references in ReliefMesh snapshots

Status: integration contract note; no production archive/delete API has been added.

## Current backend behavior
- `assignments.resource_id` is a non-null foreign key to `resources.id`. Normal PostgreSQL deletion of a referenced resource is blocked unless the referencing assignments are handled first.
- `assignments.incident_id` likewise references `incidents.id`.
- Resource statuses include `AVAILABLE`, `DISPATCHED`, `ACTIVE`, and `UNAVAILABLE`; there is no explicit archived state in the current resource enum.
- Historical assignment statuses include `COMPLETED`, `CANCELLED`, and `SUPERSEDED`.
- The frontend's cross-record validator currently requires all assignment resource and incident IDs to exist in the returned snapshot. This is correct only when the snapshot contains the **full relevant history**.

## Rules for future archival
1. Do not delete a resource with historical assignments simply to remove it from an active dashboard. Prefer an explicit inactive/archive field while retaining the immutable ID and historical references.
2. An `UNAVAILABLE` resource may still appear in historical assignments; that is not an orphan.
3. If a future snapshot intentionally filters archived resources, include a separate minimal historical-resource reference collection or a documented tombstone with stable ID and non-sensitive display label.
4. Never treat a missing referenced resource as available, and never infer dispatch eligibility from an archived record.
5. Avoid false orphan errors by validating against complete authoritative collections rather than a paginated/filtered active-only list.
6. Keep authorization and report privacy separate from archival visibility.

## Tests to add before archival
- Historical `COMPLETED` and `SUPERSEDED` assignments remain resolvable after resource becomes `UNAVAILABLE`.
- Attempted deletion of a referenced resource is rejected by PostgreSQL.
- An intentionally archived resource remains visible as a historical reference but cannot be dispatched.
- Incomplete snapshots fail closed instead of inventing missing resource details.

The current development snapshot endpoint queries all resource and assignment rows and has a bounded size limit. It does not implement archival or tombstones.
