# ReliefMesh integration readiness and local verification

**Status: development integration, not production deployment.** This runbook describes current behavior on the `integration` branch.

## Verified in GitHub Actions
- Frontend: automated tests, TypeScript checks and Next.js production build.
- Backend: pytest with a disposable PostgreSQL 16 service.
- See `.github/workflows/frontend-checks.yml` and `.github/workflows/backend-checks.yml`.
- A passing CI run does **not** prove that the frontend and backend have been started together or that real n8n/AI services are connected.

## Local read-only preview
1. Start a dedicated PostgreSQL development database and apply Alembic migrations.
2. Configure the backend with `APP_ENV=local`, `AUTH_ENABLED=true`, and a strong unique `API_KEY`. Never use demo credentials in shared or production deployments.
3. Run the backend locally. Verify `GET /integration/v1/snapshot-preview` with a valid key and confirm unauthorized requests are denied.
4. Configure the frontend server with `RELIEFMESH_BACKEND_URL=http://localhost:8000`, `RELIEFMESH_BACKEND_READ_KEY` (server-side only), and `RELIEFMESH_ENABLE_READ_PREVIEW=true`.
5. Start Next.js in **development mode** and open `/integration-preview` on localhost. The page is read-only. Never enable the preview on a public host.
6. Verify snapshot revisions, historical recommendation versions, unavailable resources, failed refresh warnings, and invalid-reference rejection.

## Operational safeguards
- `/` remains the simulated command center. It does not become a live operational UI by enabling the preview.
- The snapshot endpoint includes original emergency report text in its backend response; the frontend projection must never return those reports to the browser. The shared backend key is not a viewer-role authorization system.
- Never enable real dispatch, AI-triggered approvals, or n8n actions before authentication, coordinator identity, authorization, concurrency and complete end-to-end tests are reviewed.
- Backend revision updates are integrated into the reviewed service paths and demo reset. Future direct SQL writers and maintenance operations must preserve the revision contract.
- No deployment should be described as production-ready based only on CI success.

## Remaining release blockers
1. Dedicated viewer authentication and least-privilege access to sensitive report data.
2. Full schema validation of the backend snapshot, not only envelope and projected fields.
3. True end-to-end tests with running PostgreSQL, FastAPI and Next.js.
4. Backend AI and n8n contract integration with idempotency and human approval controls.
5. Frontend live adapter mapping for the full command center (currently mock-only).
6. Operational monitoring, error handling, retention and audit policy.
7. Review of migrations, concurrency and data recovery with realistic workloads.

No secrets should be committed to GitHub. Keep environment files untracked.
