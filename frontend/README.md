# ReliefMesh frontend

A standalone crisis-coordination command center. Every emergency, AI recommendation, dispatch, assignment and automation event is simulated in this browser. No backend, AI service, database, n8n installation or API key is required.

## Run on your computer

Requires **Node.js 22.18 or later** and npm. From the **HackSprint repository root**:

```powershell
git fetch origin
git switch frontend
git pull --ff-only origin frontend
cd .\frontend
npm.cmd ci
npm.cmd run dev
```

Open **http://localhost:3000**. Keep the terminal open while demonstrating. If PowerShell blocks `npm.ps1`, use `npm.cmd ci` and `npm.cmd run dev` instead.

Verify production and the mock service:

```sh
npm run build
npm run typecheck
npm test
npm start
```

`npm start` needs the completed production build. The test runner uses Node's built-in TypeScript stripping; no test framework is installed.

Use the GitHub `frontend` branch as the source of truth; no downloadable ZIP is required.

## Demonstration

The initial dashboard contains ten fictional Bengaluru-area incidents and 19 operational resources (seven ambulances, five rescue teams, three hospitals, four shelters). `INC-1042` opens with its initial plan ready for approval.

1. Click **Run demo**. The simulator resets and introduces the canonical emergency, merges two duplicate reports, sets priority 94, generates the fixed mock recommendation and requests approval.
2. The sequence **pauses for a real click on Approve dispatch** in the incident panel. The decision dock remains visible while the report and recommendation scroll. It never approves itself.
3. `AMB-02` and `RESCUE-01` become dispatched. Available-resource metrics and audit records update.
4. The next timed stages show the road obstruction, AMB-02's ETA changing from 6 to 24 minutes, replanning and the proposed `AMB-05` replacement (ETA 9 minutes).
5. The sequence **pauses again**. Click **Approve replacement**. AMB-05 dispatches, AMB-02 is released, and RESCUE-01 stays assigned.
6. The final timed stage resolves the incident and releases the remaining responders. A calm completion summary stays visible for five seconds, then selects the highest-priority remaining active incident. Open **Resolved / History** to review the completed case and its full audit trail. Playback stops until you explicitly choose **Run demo again**.

**Reset demo** restores the original ready-for-approval dashboard, including the initial resource statuses and ETAs. The expanded **Demo controls → Start from report intake** resets to the pre-report state for manual stepping. Only the next valid step is enabled. Pause stops future timed transitions; Run demo starts a new run.

Approve, modify and reject are explicit local simulation operations. Modify lets you select available ambulance/rescue resources, checks ambulance + water-rescue coverage, saves a revised plan and still requires approval. Reject confirms the decision and optionally records a reason; rejecting a replacement does not release already-dispatched responders.

The road obstruction is a **scripted AMB-02 scenario**, not a route planner. If you modify the first dispatch to another ambulance, its approval works, but this particular autoplay stops with an explanation. Reset to run the canonical scenario again.

## Interface

- Overview: live-derived metrics, Leaflet/OpenStreetMap map, priority-sorted incident queue, structured incident detail, recommendation and audit timeline.
- Incidents: searchable, priority-sorted **Active incidents** queue by default; approval, critical, **Resolved / History** and all-case filters. History includes resolved and rejected cases without active approval controls. With no active cases, the workspace shows a clear operational empty state.
- Resources: category and availability filters; capabilities, capacity, assignment and ETA.
- Audit trail: timestamped events, sources, incident IDs and event metadata; source filtering.
- Demo controls: manual lifecycle steps plus loading, API failure, no incidents, no available resources, offline automation and stale-data scenarios.
- API failure offers Retry; Reset demo recovers all simulated fault states. Offline and resource-unavailable states block dispatch.
- Native dialog modals provide focus trapping and Escape dismissal; controls have labels, visible focus, semantic status text and reduced-motion handling.

The map is loaded only on the client (`next/dynamic`, `ssr: false`). It uses normal OpenStreetMap raster tiles, so **the basemap needs internet access**. If tiles fail, a message appears and local incident/resource markers remain interactive. Dashed lines illustrate simulated assignments; they are not road routes. Zoom, recenter, resource visibility, marker selection and list-to-map focus are supported.

## Language system

First launch shows 13 native-script language cards: English, Hindi, Kannada, Tamil, Telugu, Malayalam, Marathi, Bengali, Gujarati, Punjabi, Urdu, Assamese and Odia. A supported browser locale is preselected, but Continue is always required before entering. A saved choice skips onboarding on later visits. The header selector changes language immediately. Urdu changes document direction; operational identifiers remain unchanged. Storage failures do not prevent selection. Bundled Noto fonts support every script without external font requests.

`lib/i18n/en.ts` defines 216 interface keys. The 12 JSON catalogs contain every key; missing-key coverage is verified by `tests/locales.test.ts`. Catalog wording is intentionally compact, and should receive native-speaker review before any real deployment. Place names and original user reports remain as data, not interface translations.

Report translation is a separate `translateReport()` service. The canonical English report has fixed translations for all 13 languages. INC-1040 also demonstrates a Hindi original with a stored English translation. Other report/language pairs explicitly report unavailable mock translation; the frontend does not invent translations. Originals are never overwritten.

The latest presentation polish makes the replacement ETA comparison visible directly in the decision dock, distinguishes dispatched map markers, and labels assignment lines. See [PRESENTATION_QA.md](PRESENTATION_QA.md) for this pass’s findings and verification.

## Architecture and integration

Start with [TEAM_INTEGRATION_PLAN.md](TEAM_INTEGRATION_PLAN.md) for each person’s next tasks, P0 blockers, proposed wire contracts and acceptance tests. [TEAM_CONTRACT_INVENTORY.md](TEAM_CONTRACT_INVENTORY.md) records what the current backend and AI code actually implement. These are planning documents; the frontend still uses its existing mock service.

See [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md) for every service method, response type, failure case and teammate integration requirement. The later completion-fix inspection found new `backend` and `ai/ml` branches; see [RESOLUTION_FIX.md](RESOLUTION_FIX.md) for the read-only findings and contract mismatches. Neither branch is merged or connected.

```text
Components → Response context/hooks → ReliefService interface → local mock adapter
Demo controls → DemoService interface → scripted local state transitions
Language provider → centralized UI catalogs
Report translation → ReliefService.translateReport → fixed translation fixtures
```

React components never import `lib/mocks`. `lib/api/index.ts` is the adapter selection point. `lib/api/config.ts` reserves `NEXT_PUBLIC_API_BASE_URL`; setting it does not silently enable nonexistent endpoints. No production URLs or authentication mechanism are invented.

| Teammate | Integration work later |
| --- | --- |
| Person 2 — backend | Implement `ReliefService` reads and mutations against agreed endpoints; authentication, authorization, durable incidents/resources/assignments, server-side availability checks, recommendation version checks and atomic dispatch. Replace the adapter in `lib/api/index.ts`. |
| Person 3 — AI/translation | Supply incident understanding, confidence, priority and recommendation/explanation data matching `types/index.ts`; implement original-preserving report translation. Replace fixed outputs rather than moving AI logic into UI components. |
| Person 4 — n8n/automation | Supply real intake, duplicate, dispatch, monitoring, failure, replanning and resolution events through the backend; update service health and deliver snapshots/events through the service subscription. Disable demo controls for real operations. |

The mock `subscribe()` notifies the UI after mutations. A real adapter should emit updates on WebSocket/SSE events or polling. Service reads and writes are asynchronous already. Domain codes (`flood`, `water_rescue`, status unions) need to be agreed with teammates; map them in the adapter if their API uses different values.

The current public service interface contains `getDashboard`, `getIncidents`, `getIncident`, `getResources`, `getActivityLog`, `getRecommendation`, `approveRecommendation`, `modifyRecommendation`, `rejectRecommendation`, `createAssignment`, `translateReport` and `subscribe`.

The client-side checks are **demo behavior**, not a substitute for backend enforcement. All simulation state resets on page reload; only language selection persists. This frontend is not intended to coordinate a real emergency.

## Files and packages

This recovery extends the existing application. All changes stay inside `frontend/` on the `frontend` branch. See [UX_HANDOFF.md](UX_HANDOFF.md) for the exact recovery scope and file list.

| Path | Purpose |
| --- | --- |
| `app/` | App Router page, providers, metadata and responsive styling |
| `components/layout/`, `dashboard/` | Command-center navigation, header, metrics |
| `components/map/`, `incidents/` | Client-only map, incident queue, original/structured report |
| `components/recommendations/`, `approvals/` | Mock plan explanation and approval/modify/reject controls |
| `components/resources/`, `timeline/`, `demo/`, `common/` | Resource view, audit events, demo controls, dialogs and reusable states |
| `types/index.ts` | Domain and service data contracts |
| `lib/api/`, `lib/services/` | Configuration, replaceable adapter and service contracts |
| `lib/mocks/` | Fictional datasets, deterministic transitions and report translations |
| `lib/i18n/` | Language metadata, provider and centralized dictionaries |
| `state/`, `hooks/` | Shared response state and timed demo orchestration |
| `tests/` | Lifecycle, state integrity, approval and locale coverage tests |
| `scripts/` | Reproducible locale generation from the compact vocabulary catalog |

Runtime packages: Next.js 16.3.4, React/React DOM 19.2.6, Lucide React 1.31.0, Leaflet 1.9.4. Development packages: TypeScript 5.9.3, Tailwind CSS and its PostCSS plugin 4.2.1, and Node/React/Leaflet type declarations. Versions are locked in `package-lock.json`.

Next.js may generate `AGENTS.md` and `CLAUDE.md` development guidance automatically. These are framework-generated files, not application features.

## Verification and remaining limits

- Production build and TypeScript checks passed.
- Fourteen automated tests passed: the existing nine plus five terminal-lifecycle, history/filtering, selection, scheduling-eligibility and explicit-restart tests. See [RESOLUTION_FIX.md](RESOLUTION_FIX.md) for the targeted completion diagnosis and verification.
- Chromium browser checks passed for both approval gates and the full canonical demo; language onboarding/persistence in English, Hindi, Kannada, Tamil and Urdu; map selection, section navigation, Modify/Reject, dialog Tab wrapping, resources/audit views, reduced motion, desktop sizes and a 390px mobile viewport.
- No application JavaScript errors were observed. External map tiles were unavailable in the test environment; the fallback message and local markers worked. Basemap rendering with successful tile downloads remains unverified.
- Basemap tiles require internet; no real routing, translations, AI decisions, dispatch, persistent storage or external automation is implemented.
- UI translations are initial implementation copy, not certified emergency-response translations. Native-speaker review remains necessary.
