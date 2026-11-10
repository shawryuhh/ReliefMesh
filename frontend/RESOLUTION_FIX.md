# Resolved incident lifecycle fix

Baseline: `19b57f6` on `frontend`. This is a targeted lifecycle/presentation fix; the service contract, domain model, canonical sequence, Leaflet implementation and both human approval gates remain intact.

## Diagnosis

Before editing, the production Chromium demo completed both approvals and resolution. After another nine seconds, progress remained 11/11, the audit did not advance and there was exactly one INC-1042. No automatic restart was reproduced.

The confusing continuation came from the default All queue retaining the resolved case, `selectedId` retaining INC-1042, its selected map halo, and the generic Run demo button. Resources, assignments and active metrics were already being finalized correctly by the mock service.

Code review also found a separate asynchronous-start race: a late reset response could set playback running after a stop/reset/unmount. Start now checks the existing generation guard after awaiting reset. This was not the cause of the observed completed-state behavior.

## Behavior now

- Default **Active incidents** excludes resolved and rejected cases. Approval and Critical filters also exclude closed cases. **Resolved / History** includes both closed statuses; **All** retains every case. All queues sort by priority.
- A selected case transitioning to resolved gets a five-second, restrained green confirmation. It reports the state's people count as **People in report**, not an unsupported claim that those people were rescued. Released responder IDs come from completed assignments; canonically these are RESCUE-01 and AMB-05. AMB-02 was released earlier at replacement. Stale action notices are cleared.
- The resolved case immediately leaves the Active queue. After five seconds, selection moves to the highest-priority remaining active incident, or an empty selection with **No active incidents requiring attention**. Choosing a case or changing the filter cancels the handoff; deliberately opening History never starts another handoff.
- Historical details have a status/read-only label, no approval controls, subdued priority emphasis, the original report and recommendation, and the complete incident timeline. Resolved state takes precedence over any stale pending recommendation in presentation mapping.
- Map history remains accessible through subdued check-mark markers with no selection halo/pulse. Completed assignment lines disappear through the existing status logic. Available responder markers and metrics reflect the released resources.
- The presentation bar says **Demo complete**, 11/11, Resolved, with **Run demo again**. Only an explicit restart resets the scenario. As before, this in-memory reset replaces the prior demo run and its audit; it does not provide durable cross-run archives. Resolution itself preserves all data and events.
- Eight new strings are translated in every catalog: 216 keys across all 13 languages. Urdu direction and operational IDs are preserved.

## Scheduling and duplicate protection

The existing generation guard remains. A single owned timeout is cleared on Pause, Reset, effect cleanup and unmount. Completion, resolved/rejected terminal state and fault scenarios cannot schedule a step. Neither human approval step is scheduled. Repeated start calls during an awaited reset are ignored. A stale failed operation cannot stop a newer generation. Context action locking and service step-order checks remain; intake also explicitly rejects an already-existing canonical ID.

An already executing asynchronous adapter mutation is not retroactively cancelled by clearing a timeout. The current mock mutations are synchronous before their returned promise resolves. A future network adapter must still provide atomic/versioned writes as described in the existing integration contract; this change does not invent a cancellation API.

## Verification

- Production build and TypeScript validation pass.
- All **14 automated tests** pass: existing nine unchanged plus five in `tests/completion.test.ts`.
- New tests cover terminal status/index, completed assignments, released resources/metrics, retained lifecycle, rejected post-completion mutations, scheduling eligibility, active/history/all filtering, highest-priority/empty selection, stale-plan suppression and concurrent duplicate intake after explicit reset.
- Chromium production completion checks: **38 passed**, including both approval gates, ETA 24 to replacement 9, completion feedback, immediate queue removal, subdued map/no assignment lines, resource availability, a 9.5-second post-resolution observation, selection handoff, historical lifecycle/read-only view, Urdu, explicit restart, Pause and Reset.
- Chromium development/React Strict Mode: **37 checks passed**, including three synchronous Run-button clicks at startup without duplicate intake/playback.
- Existing-feature Chromium regression: **47 checks passed** for five first-run languages and persistence, 13 language cards, Urdu RTL, three desktop sizes (1366×768, 1440×900, 1920×1080), mobile overflow, translated docks, map selection, section navigation, Modify/Reject, Tab/Shift+Tab dialog trapping, Resources/Audit, reduced motion and the operational empty state.
- No application page errors occurred in these runs. External map tile downloads failed in the environment; the fallback message and local interactive markers worked. Successful external basemap loading is not verified here. Screenshots of the confirmation and Urdu historical view were visually inspected.
- Timeout/unmount cleanup and the awaited-reset generation check were reviewed in code; no delayed network adapter was introduced solely for testing.

## Team branches inspected read-only

Initial fetch found `frontend` at `19b57f6`, `main` at `987253e`, and two new teammate branches: `backend` at `c42d375` and `ai/ml` at `7a58ba7`. No n8n/automation branch was found. No branch was merged, cherry-picked or modified.

### backend

FastAPI, Pydantic, SQLAlchemy, PostgreSQL and Alembic. Endpoints include `/health`; incident collection/item reads and writes plus `/resolve` and `/cancel`; resource reads/writes and `/status`; assignment reads/writes and `/status`; `/replanning`; `/activity-log`; and `/dashboard`.

Example environment declares `DATABASE_URL`, `AUTH_ENABLED`, `API_KEY`, `CORS_ORIGINS`, `APP_ENV` and optional `TEST_DATABASE_URL`. Optional `X-API-Key` authentication is enabled by `AUTH_ENABLED`; it defaults off. No WebSocket/SSE mechanism was found in the application sources inspected.

The dashboard uses `incident_counts`, `resource_counts`, `active_assignments_count`, `recent_activity`, `current_incidents` and `current_resources`, not the frontend `DashboardSnapshot`. Backend incident statuses are uppercase UNASSIGNED/ASSIGNED/ACTIVE/RESOLVED/CANCELLED; assignment statuses are ASSIGNED/ACTIVE/COMPLETED/CANCELLED/SUPERSEDED. These need deliberate adapter mapping to the more detailed frontend states.

Assignment creation accepts `incident_id`, `resource_ids`, `decision_source`, optional `approved_by`, `reason` and `ai_recommendation`. Replanning swaps `old_resource_id` for `new_resource_ids` with optional approval metadata. These are not yet the frontend versioned pending-recommendation/explicit-human-approval contracts. Person 2 must agree atomic approval/dispatch semantics, both approval gates, recommendation versions and snapshot/event delivery before connection.

### ai/ml

FastAPI/Pydantic with LangChain and ChatGoogleGenerativeAI. `/ai/health` checks `GOOGLE_API_KEY` or `GEMINI_API_KEY`. No HTTP auth or push-event transport is present in the inspected `ai/main.py`.

- `POST /ai/analyze-incident`: no request body; fixed mock INC-1042 recommendation (priority 94, AMB-02 + RESCUE-01).
- `POST /ai/extract-incident`: `{ text }` to structured location, incident type, people affected, vulnerable groups, medical urgency, severity, time sensitivity, environmental threat and confidence fields.
- `POST /ai/score-incident`: typed scoring inputs to deterministic `priority_score`, `risk_level`, `requires_human_review` and `scoring_breakdown`.
- `POST /ai/deduplicate-incident`: `new_report_text` and `active_incidents` to `is_duplicate`, `matched_incident_id` and `similarity_reason`.

These are useful upstream operations, but not yet a stable versioned frontend recommendation/explanation or translation contract. Person 3 needs to agree mappings and backend ownership; Person 4 still needs the real automation/event flow. No APIs are connected in this fix. `INTEGRATION_CONTRACT.md` remains unchanged; all operational data, AI output, dispatch, translation fixtures and automation remain mocked.

## Changed files

`state/response-context.tsx`; `hooks/use-demo.ts`; `components/demo/demo-controls.tsx`; `components/incidents/{incident-list,incident-detail,resolution-summary}.tsx`; `components/map/leaflet-map.tsx`; `app/presentation.css`; `lib/presentation/{incident-state,incident-queue,demo-playback}.ts`; `lib/mocks/service.ts`; `tests/completion.test.ts`; `lib/i18n/en.ts`; all 12 JSON locale catalogs and their `catalog.tsv` source; `scripts/locale-keys.json`; `README.md`; this document.
