# ReliefMesh remaining write-path audit

Follow-up to BACKEND_WRITE_INVENTORY.md. Reviewed on the `integration` branch.

## Additional writers

| Location | Finding | Revision implication |
| --- | --- | --- |
| `backend/scripts/seed_demo_data.py` | Uses raw `TRUNCATE ... RESTART IDENTITY CASCADE` and direct `db.commit()` for reset; also changes sequences and invokes normal service-layer mutations. | Reset must not silently preserve an obsolete revision. Database triggers on individual tables may not cover `TRUNCATE`; explicitly design reset handling. |
| `backend/app/services/id_generator.py` | Uses PostgreSQL `nextval()` and may create sequences. | Sequence allocations are not committed operational state; do not count each ID allocation as a revision. |
| `backend/alembic/versions/` | Schema migrations create/alter tables and enum types. | Add a new migration; do not rewrite published migrations. Treat migration/schema version separately from operational data revision. |
| `backend/tests/conftest.py` | Truncates application tables between tests. | Test cleanup is a separate maintenance operation, not a user-visible operational transaction. Reset revision fixture state between tests. |
| `backend/app/api/routes/` | Routes inspected delegate mutation logic to services; no independent route-level commits found in the reviewed source. | Revision integration should follow transaction boundaries, not HTTP handler invocation counts. |
| `backend/app/services/action_log_service.py` | Shared `record_action` flushes logs within callers' transactions. | A single incident update plus audit log must increment once, not twice. |

## Design decision before implementation

Use a **transaction-scoped revision increment** on the outermost committing operational transaction. Do not use a PostgreSQL sequence as the revision source. One viable strategy is a single-row `operational_revision` record updated with `UPDATE ... SET revision = revision + 1` once per transaction. PostgreSQL's row lock serializes competing writers; rollback also undoes the increment.

A database trigger can cover ORM and raw SQL writers but requires careful treatment of multiple row/table changes per transaction, `TRUNCATE`, and maintenance operations. A service helper is simpler but easy to miss in future code. Before selecting either, test it with actual PostgreSQL concurrency and rollback cases.

## Remaining work
1. Inventory all write operations in future report-intake and automation implementations as they are added.
2. Choose and implement the revision update mechanism, including seed/reset policy.
3. Add migration and tests for concurrency, rollback, multi-table mutations, and coherent snapshot reads.
4. Ensure snapshots cannot claim a valid revision before all mutation paths are covered.

No operational code or schema was changed by this audit.
