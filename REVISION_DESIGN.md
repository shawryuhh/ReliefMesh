# ReliefMesh persistent snapshot revision design

Status: **design only — no migration or runtime revision counter is implemented**.

## Goal
Give each coherent operational snapshot a monotonic revision that advances on every committed state-changing transaction. This allows the frontend to detect stale data and avoid combining incompatible states.

## Proposed database model
Create a one-row `operational_revision` table with `id = 1`, `revision BIGINT NOT NULL`, and a database-managed timestamp. Add this in a **new Alembic migration**, without rewriting the existing migrations.

## Write transaction rule
Every committed operational mutation must atomically increment this row **in the same PostgreSQL transaction** as the underlying incident/resource/report/recommendation/assignment/event changes. If the mutation rolls back, the increment must roll back too. A separate post-commit increment is incorrect.

Use an explicit shared service helper or database trigger coverage; choose one after auditing **every** write path. A database sequence alone is not a suitable committed revision because aborted transactions consume sequence values, and concurrent commits can be observed out of order.

## Read transaction rule
The snapshot endpoint reads the revision and all included collections inside one `REPEATABLE READ READ ONLY` transaction. The revision must correspond to the same database snapshot as the rows. Use a transaction-scoped snapshot timestamp for metadata, not the client's clock.

## Consistency and deployment requirements
- Audit all state-changing routes and seed scripts. Include terminal resolution, recommendation approval/replacement, direct assignment transitions, AI intake, and audit logging.
- Preserve a deterministic lock order and avoid adding network/LLM calls inside database transactions.
- Increment revision for *committed* changes only; verify simultaneous writes produce distinct ordered revisions.
- Do not enable live dispatch or treat `revision: null` as a valid production sync token.
- For multi-page history, use a cursor/snapshot token or an explicit truncation indicator. The current 500-row development cap is not a production pagination contract.
- Keep viewer authorization separate from coordinator approval. Never expose original report text without verified viewer access.

## Acceptance tests
1. Initial revision is defined on a clean database.
2. One committed mutation advances the revision exactly once.
3. A rolled-back mutation does not advance it.
4. Two concurrent committed mutations advance monotonically with no lost updates.
5. Snapshot read concurrent with mutation sees a self-consistent before-or-after state and matching revision.
6. All relevant write routes advance the revision, including seed scripts and audit entries.
7. Stale client revision is rejected or clearly marked; no mock fallback.
8. Schema migration upgrade and rollback are tested on isolated PostgreSQL.

## Implementation sequence
1. Inventory all write transactions and identify the correct increment point.
2. Add migration + revision helper or triggers.
3. Add concurrency/rollback tests and integrate the revision into snapshot serialization.
4. Update frontend snapshot schema to require a monotonic revision and test stale data handling.
5. Enable only after PostgreSQL CI and browser tests pass.
