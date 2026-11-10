# Backend operational write-path inventory

Reviewed against the `integration` branch. This is a source-level inventory, not proof that every runtime path is exercised.

## Service-level transaction boundaries

| Service | Mutating entry points | Commit behavior |
| --- | --- | --- |
| `incident_service.py` | `create_incident`, `update_incident`, `resolve_incident`, `cancel_incident` | Explicit `db.flush()`, `db.commit()`, and rollback handling |
| `resource_service.py` | `create_resource`, `update_resource_status` | Explicit flush, commit, rollback |
| `assignment_service.py` | `create_assignment`, `update_assignment_status` | Explicit flush/commit and rollback; preserve lock ordering and unique live-assignment constraint |
| `recommendation_service.py` | `create_recommendation`, `propose_replacement`, `approve_recommendation` | Multiple commit boundaries; internal dispatch and approval helpers share transaction |
| `disruption_service.py` | `report_disruption` | Explicit flush/commit/rollback |
| `action_log_service.py` | `create_manual_entry` | Explicit commit/rollback; `record_action` is called from other services and should not increment revision separately |

## Revision integration recommendation

**Prefer a database trigger-based revision bump**, after a full write-table inventory, rather than sprinkling manual increments across each service. That reduces the chance that future write paths forget to advance the revision. PostgreSQL row-level triggers must be designed to avoid multiple bumps for a single logical transaction; use a transaction-scoped marker or equivalent transaction-safe mechanism, and verify concurrency behavior.

A simpler alternative is one explicit shared commit helper called exactly once by every outermost transaction. This is easier to reason about but requires complete enforcement and tests for every entry point.

**Do not add a revision increment to `record_action` independently** when the caller is already committing an incident, resource, recommendation, or assignment mutation; otherwise a single logical operation may advance more than once.

## Additional write surfaces to audit before migration

- `backend/scripts/seed_demo_data.py` and Alembic migrations.
- Any direct `db.commit()` or raw SQL writes in API routes, scripts, tests, and new integration handlers.
- Report ingestion and translation persistence when implemented.
- Automation command/outbox mutations when implemented.
- Database-side effects and cascades.

## Safety acceptance criteria

1. A rollback never advances the committed revision.
2. Concurrent transactions cannot produce a revision that misrepresents commit order.
3. Exactly one revision increment per logical committed mutation transaction.
4. No new network or AI calls inside the revision lock/transaction.
5. Snapshot revision and all returned rows are read under the same repeatable-read transaction.
6. All backend tests and migration upgrade/rollback tests pass against isolated PostgreSQL.

No revision table, triggers, migrations, or service writes were changed in this inventory.
