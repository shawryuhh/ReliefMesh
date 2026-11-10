# ReliefMesh — Person 4 automation

**Status: importable, runnable LOCAL FIXTURE demonstration. Live backend integration is disabled.**

This branch owns only `n8n/`. Backend is authoritative, frontend collects coordinator decisions, AI recommends, n8n triggers/delivers, database persists. No workflows approve a plan, allocate resources, call Gemini or use the unsafe existing assignment/replanning routes. No real messages are sent.

The current backend lacks the required contracts at `c42d375`. Exact proposed endpoints, request/response shapes and Person 2 changes are in [BACKEND_CONTRACT_REQUESTS.md](BACKEND_CONTRACT_REQUESTS.md). Those names have **not** been agreed with Person 2. All executable paths are explicitly local `/fixture/...` paths. Setting a URL or env variable will not enable live mode.

## Files and workflows

| File | Purpose / trigger |
| --- | --- |
| `workflows/intake.json` | Manual synthetic Krishna report or synthetic webhook → validate → report intake receipt |
| `workflows/dispatch.json` | Manual one-shot poll → claim → validate → simulated delivery → callback; handles initial dispatch and replacement |
| `workflows/obstruction.json` | Manual/webhook AMB-02 ETA 6→24 → event receipt; stops while replacement is pending |
| `workflows/completion.json` | Manual/webhook current assignment completion signal → backend-double resolution receipt |
| `scripts/fixture_server.py` | Clearly labelled local HTTP contract double + simulated receiver; SQLite persistence |
| `scripts/fixture_control.py` | Separate manual fixture coordinator action; never called by workflows |
| `scripts/workflow_logic.js`, `build_workflows.js` | Shared validation/retry logic and reproducible export generator |
| `scripts/run_fixture_workflow.js` | Fast HTTP fixture harness; does not claim to be n8n |
| `scripts/verify_n8n.py` | Disposable actual-n8n CLI verification; synthetic test decisions between runs |
| `tests/` | Static, retry, role, concurrency, state/duplicate and terminal-lifecycle tests |
| `fixtures/*.json` | Safe synthetic event/command examples and sanitized verification evidence |
| `.env.example` | Configuration/credential-name reference; no secret values |

Exports are inactive. Every graph has a visible `Result or WAIT FOR HUMAN` endpoint and an `Explicit failure` node. The dispatch graph runs one command per click; its `Request context.stage` advances through `poll → claim → validate → delivery → callback`. This keeps one shared bounded retry loop. A pending plan yields `WAIT_FOR_HUMAN` then stops. Click again only after a separate human approval. Empty queues never cause busy loops. There is no automatic demo restart or recurring poll in these exports.

## Windows PowerShell setup

Tested runtime: **n8n 2.39.8, Node.js 24.19.0, Python 3.12**, on Linux. Use Node 24.x and Python 3.12+ for the documented Windows setup. Python standard library and Node built-ins suffice for all fixture tests; no pip install is needed. The PowerShell commands below are provided for your machine; physical Windows execution has not been verified here.

Use a **separate clone** so your frontend working directory stays on its existing branch:

```powershell
cd $env:USERPROFILE
git clone --branch n8n --single-branch https://github.com/shawryuhh/HackSprint.git ReliefMesh-N8N
cd ReliefMesh-N8N
git branch --show-current
node --version
py -3 --version
```

The branch must print `n8n`. All remaining commands run from this clone's root. `npm.cmd` and `npx.cmd` avoid PowerShell's `npm.ps1` execution-policy issue.

**Terminal 1: start the local test double and leave it running.**

```powershell
py -3 .\n8n\scripts\fixture_server.py
```

It listens only at `http://127.0.0.1:8094`. State persists in ignored `n8n/.runtime/fixture.sqlite`. It cannot contact a real backend, provider or responder. It models one canonical incident and two fixture plans; the analysis/replacement are predefined test-double behavior, not actual AI results.

**Terminal 2: install the exact tested n8n version locally and import.**

```powershell
New-Item -ItemType Directory -Force .\n8n\.runtime\engine | Out-Null
npm.cmd install --prefix .\n8n\.runtime\engine n8n@2.39.8 --no-audit --no-fund
$env:N8N_USER_FOLDER = Join-Path (Resolve-Path .\n8n\.runtime).Path 'profile'
$env:N8N_LISTEN_ADDRESS = '127.0.0.1'
$env:N8N_PORT = '5678'
$env:N8N_DIAGNOSTICS_ENABLED = 'false'
& .\n8n\.runtime\engine\node_modules\.bin\n8n.cmd import:workflow --separate --input=.\n8n\workflows
& .\n8n\.runtime\engine\node_modules\.bin\n8n.cmd start
```

Open [local n8n](http://localhost:5678), finish its local owner setup, and open the four **ReliefMesh FIXTURE** workflows. If n8n has already been set up, use **Import from File** in its workflow menu for each export instead. Keep all workflows inactive/unpublished for this manual demonstration. No API key or responder credential is required in fixture mode. The exports use standard Manual Trigger, Webhook, Code, HTTP Request, IF, Wait, Stop and Error, and Sticky Note nodes. No community nodes are required.

Use the local npm installation on the same Windows host as Python. n8n Cloud/Docker cannot reach this host's loopback URL unchanged; those layouts are not configured here. Do not replace the URL with a real backend address: the fixture response guard also requires `fixture:true`.

## Canonical demo — human pauses are mandatory

Terminal 3, in the clone root:

| Step | Human action | Observable result |
| --- | --- | --- |
| 1 | In n8n, execute **01 Intake** | Report accepted; backend double stores originals; phase `awaiting_approval` |
| 2 | Execute **02 Authorized dispatch and replacement** | `WAIT_FOR_HUMAN`; zero delivery, no assignment |
| 3 | Run approval command below with version 1; type the exact confirmation | Double commits first approval and command; AMB-02 + RESCUE-01 |
| 4 | Execute **02** again | Claim/revalidate; one simulated initial delivery; callback recorded |
| 5 | Execute **03 Road obstruction** | ETA 6→24; AMB-05 ETA 9 suggested by double; `awaiting_replacement` |
| 6 | Execute **02** again | `WAIT_FOR_HUMAN`; AMB-05 remains available, no redispatch |
| 7 | Run approval command with version 2; type the exact confirmation | Double releases/supersedes AMB-02, retains ASG-888/RESCUE-01, creates AMB-05 command |
| 8 | Execute **02** again | Only AMB-05 is newly delivered; no second RESCUE-01 dispatch |
| 9 | Execute **04 Completion** | Double verifies current assignment IDs, resolves/releases and retains history |
| 10 | Repeat **04**, then **02** | Duplicate receipt; no new command; incident remains resolved |

```powershell
py -3 .\n8n\scripts\fixture_control.py approve --version 1
# Type APPROVE 1 only after reviewing the first pending fixture plan.

# Run step 4, step 5, and step 6 in n8n before this:
py -3 .\n8n\scripts\fixture_control.py approve --version 2
# Type APPROVE 2 only after reviewing the pending replacement.

py -3 .\n8n\scripts\fixture_control.py snapshot
```

This fixture-only terminal approval is **not** the actual frontend/backend human gate. It is a separate manual stand-in because Person 2's real gate does not exist. Live integration must use the real frontend coordinator approval and authenticated backend transaction. The workflow has no approval button, endpoint or credentials. The test driver injects synthetic decisions solely for automated verification.

Inspect the final n8n node output and the snapshot audit to present both waits and the stable command/event IDs. The real frontend remains on its independent mock; it will not observe the local test double. Do not present this as full ReliefMesh integration.

## Webhook examples

For Intake, Obstruction or Completion, open the workflow's **Synthetic webhook** node, select **Listen for test event**, and use its displayed test URL. The fixed paths are `reliefmesh-fixture-intake`, `reliefmesh-fixture-obstruction`, and `reliefmesh-fixture-completion`.

```powershell
$body = Get-Content .\n8n\fixtures\intake.json -Raw -Encoding UTF8
Invoke-RestMethod -Method Post -Uri 'http://localhost:5678/webhook-test/reliefmesh-fixture-intake' -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

Listen again before testing an exact duplicate. For the other workflows substitute both the fixture filename and webhook path. Webhooks use last-node response; validation errors produce an n8n failed execution. The intake source must provide a stable source ID and timestamp **before submission**. A retry reuses the same file/body; never regenerate event IDs per attempt. The manual nodes embed the same files' synthetic values. Original text/language are retained exactly, even whitespace/native script.

The event files contain the complete intake/obstruction/completion examples. Initial and replacement command files are illustrative backend-issued values. **Do not POST these files to a delivery endpoint as authorization**: the dispatcher must obtain a fresh valid claim from the double. Fixture assignment IDs are ASG-887/AMB-02, ASG-888/RESCUE-01, ASG-889/AMB-05; live runs must use real backend-returned IDs.

## Retry, failure and idempotency behavior

- Each HTTP stage gets **4 total attempts**, delays **1, 3, 10 seconds**, 5s HTTP timeout, no redirects. Network errors, 429 and 5xx retry. Retry-After is respected up to 30s; longer delays stop for operator attention. 401/403/404/409/422 stop on the first attempt. There is no infinite loop.
- The retry context carries the unchanged body, event ID, command ID and idempotency key. Source/occurred_at normalization happens once before the first attempt. Same ID with changed logical payload fails with 409. Duplicate reports/events may start another n8n execution, but do not duplicate backend effects.
- SQLite transactions persist test-double receipts and serialize competing claims/deliveries. Receiver delivery is deduplicated by command ID plus immutable payload hash, including assignments. Lease changes do not create another dispatch. The backend remains the final state enforcement layer.
- Before delivery, the double validates current approval/version/assignment/lease. The receiver checks again atomically. Stale AMB-02 callbacks after replacement cannot reactivate its assignment. Exact event replays after resolution return receipts without state changes; new attempts to restart this single-case fixture are rejected.
- Delivery exhaustion attempts a bounded `outcome:failed` callback, then a local failure receipt and an explicit failed n8n execution. Callback failure never triggers a new delivery in the same execution. If the failure sink is also down, execution data retains the original failure. Each stage's retry budget is separate; inspect `stage` and `attempt` in `Request context`.
- The double permits a maximum of three expired-lease claims; accepted/failed commands are not continually polled. Failed/stale work requires operator review. There is deliberately no automatic failure replay or reset button. Live reclaim/fencing/sweeper policy needs Person 2 sign-off.
- A completed incident never restarts on its own. To start a **deliberately new disposable fixture demo**, stop Terminal 1, then start with a new database filename (do not delete shared state):

```powershell
py -3 .\n8n\scripts\fixture_server.py --db .\n8n\.runtime\demo-run-02.sqlite
```

Fixed synthetic IDs are scoped to that isolated database. Never use fixture reset/reseed against a live backend.

## Credentials and configuration

Fixture mode needs no secrets. `X-Fixture-Actor: automation` is a publicly known local role marker, **not authentication**. Only the local coordinator script sends `fixture-coordinator`; the fixture rejects automation calls to its approval control. The test service binds loopback and is not a deployable production service.

For a future agreed live transport, create an n8n **Header Auth** credential named **ReliefMesh Automation**, using the backend-provided header/scheme and scoped automation value. Enter its secret in n8n's credential UI; never export it, put it in `.env.example`, a Code node, fixture, webhook body or repository. Do not use coordinator credentials. The currently implemented shared backend X-API-Key is insufficient for this role split. Live base URL is intentionally blank in `.env.example`; no live switch or live credential reference is enabled in these exports. Never put credentials in frontend configuration.

## Verification

See [VERIFICATION.md](VERIFICATION.md) for the recorded result and limits. Re-run fast checks:

```powershell
node .\n8n\scripts\build_workflows.js
node --test .\n8n\tests\workflows.test.js
py -3 -m unittest discover -s .\n8n\tests -p 'test_*.py' -v
```

Optional fixture harness, with Terminal 1 running:

```powershell
node .\n8n\scripts\run_fixture_workflow.js intake
node .\n8n\scripts\run_fixture_workflow.js dispatch
```

The harness executes the exact embedded Code-node source with HTTP but **does not simulate n8n node scheduling/import**. Actual n8n verification is separate. `scripts/verify_n8n.py` was run against the installed CLI on Linux in its own disposable environment; do not run it alongside your presentation server because it needs port 8094. On Windows use the UI demo above or the locally installed `n8n.cmd execute --id=ReliefMeshFixtureintake --rawOutput` with the same N8N_USER_FOLDER and the UI server stopped. Keep Terminal 1 running. Logs/state under `.runtime` are ignored and should not be committed.

## What remains blocked

Person 2 must implement immutable idempotent raw intake, backend-owned AI orchestration, versioned pending plans, coordinator-only gate #1/#2, atomic command creation, list/claim/validate/result APIs, scoped roles, stale/terminal checks and atomic completion/resource release/history. Person 3 must supply the agreed live recommendation behavior. Person 1 must later wire a live adapter. Until that evidence exists, these workflows demonstrate the **automation contract only**. No real ambulance/GPS/municipal integration, Gemini request or live backend state mutation has been performed.

Reference: [n8n HTTP Request documentation](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/) describes full-response/status and Never Error used by the explicit classifier. The npm package's published engine metadata and the locally installed CLI were used to verify the pinned runtime version.
