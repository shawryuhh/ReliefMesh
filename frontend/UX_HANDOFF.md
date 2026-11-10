# ReliefMesh UX recovery handoff

This records the recovery at `b8714c7`. For the subsequent presentation pass, see [PRESENTATION_QA.md](PRESENTATION_QA.md) and [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md).

This pass extends the existing frontend. The mock service, domain contracts, response state and demo engine retain their original business behavior. Only `frontend/` changed; work is published on the `frontend` branch.

## What was created or changed

- **First-run accessibility:** 13 large native-script language choices, multilingual instructions, supported browser-language preselection, explicit Continue, saved preference reuse, immediate header switching and Urdu RTL. Local fonts cover all supported scripts.
- **Decision experience:** a fixed row inside the incident panel contains Approve, Modify and Reject while evidence scrolls independently. It distinguishes initial and replacement approval, displays resources, priority, confidence and replacement ETA, then shows dispatch/responders/released resources after approval.
- **Next action:** a presentation-only mapping derives review, approval, monitoring, disruption, replanning, rejection and resolution guidance from the current incident and plan.
- **Guided reading:** Report, Details, Plan, Decision and Activity shortcuts scroll the inner panel. IntersectionObserver highlights the visible stage; evidence remains readable. Incident-specific audit events appear in the last stage.
- **Replanning:** previous AMB-02 ETA 6 → 24 and updated AMB-05 ETA 9 are shown together. A map warning and the replacement decision dock emphasize the human decision.
- **Map:** existing Leaflet retained; incident/resource marker elements persist across updates, open popup content refreshes, selection pans without resetting zoom, selected markers have a finite emphasis animation, and zoom controls have translated accessible labels.
- **Motion:** short entrances, active navigation movement, changed metrics/status feedback, new audit-event emphasis, dialog entry/exit and a real demo progress bar. CSS transitions plus IntersectionObserver; no Motion for React, GSAP or other animation dependency. Reduced-motion users receive the same text and state cues without animations.
- **Visual hierarchy:** deep slate navigation, compact laptop spacing, stronger selected states, a distinct decision area, and a stacked mobile layout with a bounded incident scroller.
- **Interaction safeguards:** preserved service validation and both explicit approval gates; loading feedback, keyboard dialog containment/focus restoration, controls disabled during pending writes, and stale translation-request protection.

## Dependencies

No application packages were added or changed. `package.json` and `package-lock.json` remain unchanged. Twenty self-hosted Noto WOFF2 assets cover ten scripts at weights 400/600; their licenses and sources are in `public/fonts/NOTICE.txt`. Browser QA used temporary Playwright/Chromium tooling outside the application dependency list.

## Verification

- Production build: passed (`npm run build`).
- TypeScript: passed (`npm run typecheck`).
- Automated tests: all 9 passed; existing tests retained. All 206 UI keys exist in all 13 languages.
- Chromium: full timed canonical scenario passed initial approval, AMB-02 dispatch, road block, replacement approval for AMB-05, redispatch and resolution.
- Additional browser suite: 46 checks passed across first-run language detection/confirmation/persistence, Urdu direction, all desktop sizes (1366×768, 1440×900, 1920×1080), map selection, quick navigation, Modify/Reject, Tab/Shift+Tab containment, Resources, Audit trail, reduced motion and mobile overflow.
- Final targeted checks: mobile map width 314px at a 390px viewport, visible mobile decision dock, and an independently scrolling Resources view.
- Native-script screenshots inspected; no application JavaScript errors observed.

## Practical limits

This remains a frontend simulation, with no backend, live AI, real dispatch or road routing. Map tile requests were unavailable in this environment; local markers, assignment overlays and the tile-failure notice remained usable. Successful basemap downloads, physical touch devices, screen-reader output and other browser engines were not verified. Translation copy should receive native-speaker review before real use.

## Run in Windows PowerShell

Install Node.js 22.18 or later. In the existing `HackSprint` repository root:

```powershell
git fetch origin
git switch frontend
git pull --ff-only origin frontend
cd .\frontend
npm.cmd ci
npm.cmd run dev
```

Open http://localhost:3000 and keep the terminal running. `npm.cmd` avoids PowerShell's `npm.ps1` execution-policy issue. To stop the server, press Ctrl+C. No API key or `.env` file is required for the demo.

For a fresh clone:

```powershell
git clone --branch frontend https://github.com/shawryuhh/HackSprint.git
cd .\HackSprint\frontend
npm.cmd ci
npm.cmd run dev
```

## Files changed in this recovery

- `.gitignore`
- `README.md`
- `RECOVERY_STATUS.md`
- `app/fonts.css`
- `app/interaction.css`
- `app/layout.tsx`
- `app/page.tsx`
- `components/approvals/approval-modal.tsx`
- `components/approvals/decision-dock.tsx`
- `components/common/modal.tsx`
- `components/common/ui.tsx`
- `components/dashboard/metrics.tsx`
- `components/demo/demo-controls.tsx`
- `components/incidents/incident-detail.tsx`
- `components/layout/command-center.tsx`
- `components/layout/language-gate.tsx`
- `components/map/leaflet-map.tsx`
- `components/map/map-panel.tsx`
- `components/recommendations/recommendation-panel.tsx`
- `components/recommendations/route-feedback.tsx`
- `components/timeline/activity-timeline.tsx`
- `hooks/use-change-feedback.ts`
- `hooks/use-incident-story.ts`
- `lib/i18n/en.ts`
- `lib/i18n/locales/as.json`
- `lib/i18n/locales/bn.json`
- `lib/i18n/locales/catalog.tsv`
- `lib/i18n/locales/gu.json`
- `lib/i18n/locales/hi.json`
- `lib/i18n/locales/kn.json`
- `lib/i18n/locales/ml.json`
- `lib/i18n/locales/mr.json`
- `lib/i18n/locales/or.json`
- `lib/i18n/locales/pa.json`
- `lib/i18n/locales/ta.json`
- `lib/i18n/locales/te.json`
- `lib/i18n/locales/ur.json`
- `lib/i18n/preference.ts`
- `lib/i18n/provider.tsx`
- `lib/presentation/incident-state.ts`
- `public/fonts/NOTICE.txt`
- `scripts/locale-keys.json`
- `tests/preference.test.ts`
- `tests/presentation.test.ts`
- `public/fonts/*.woff2` — 20 bundled font files.
- `UX_HANDOFF.md` — this handoff.
