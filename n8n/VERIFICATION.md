# Verification — 2026-09-20

**Real n8n engine + local contract double. No real backend/AI/frontend integration.**

| Verification level | Result | Limits |
| --- | --- | --- |
| Static JSON/graph/Code validation | PASS: four inactive workflows, unique IDs/names, valid connection targets, reachable result/failure nodes, Code syntax, no credential exports/approval calls | Does not prove HTTP contracts exist in Person 2 backend |
| JavaScript logic tests | PASS: 14 tests | Pure embedded workflow logic, not n8n scheduling |
| Python contract-double tests | PASS: 17 tests | Local SQLite double, not PostgreSQL or backend branch |
| Actual n8n import | PASS: 4/4 imported via `import:workflow --separate` | Tested n8n 2.39.8, Node 24.19.0, Linux |
| Actual n8n execution | PASS: 14 expected outcomes (12 success, 2 intentionally failed) | Manual-trigger paths against local fixture HTTP server; no live backend |
| Webhook branch runtime | Not executed | JSON/connection/validation code checked; use documented test-webhook instructions |
| Windows PowerShell | Instructions supplied, not executed here | Local same-host npm + Python setup |
| Real backend integration / Gemini / real delivery | NOT RUN; blocked | Required backend contracts absent; live transport disabled |

The two expected failures are a successful test result, not successful delivery: execution 27 exhausted four 503 attempts; execution 28 stopped on the first 403. Both recorded an explicit failure and ended in n8n error state. An earlier isolated runtime probe with no reachable fixture server also made four attempts and stopped, including bounded failure-sink attempts; this was used to verify transport failure handling before the canonical run.

## Actual n8n execution evidence

Sanitized machine-readable evidence is in [fixtures/verification-evidence.json](fixtures/verification-evidence.json). It contains real CLI execution IDs, operation/attempt/key sequences, result outputs and final fixture audit/state. No lease/auth tokens or n8n encryption key are included. Raw execution logs stay ignored under `.runtime/verification/`; these may include runtime claim metadata and should not be published. When CLI error output was not flushed, the verification driver inspected the engine's persisted execution record.

| Execution | Scenario | Observed |
| --- | --- | --- |
| 15 | Intake with injected 429, then 503 | Third attempt accepted, same event ID/body; awaiting approval |
| 16 | Duplicate intake | Duplicate receipt; one original report |
| 17 | First gate | `WAIT_FOR_HUMAN`; no delivery |
| 18 | After separately injected fixture coordinator approval #1 | Claim → validate → simulated AMB-02 + RESCUE-01 → accepted callback |
| 19 | Poll again | `NO_AUTHORIZED_COMMAND`; no second initial dispatch |
| 20 | Road obstruction | ETA 6→24; pending replacement |
| 21 | Duplicate obstruction | Duplicate receipt, no new pending version |
| 22 | Second gate | `WAIT_FOR_HUMAN`; no AMB-05 delivery |
| 23 | After separately injected fixture coordinator approval #2 | AMB-05 only; continuing RESCUE-01 omitted from new delivery |
| 24 | Completion | Resolved; resources released; audit/history retained |
| 25 | Duplicate completion | Duplicate receipt; one resolution |
| 26 | Poll after resolution | `NO_AUTHORIZED_COMMAND`; no restart |
| 27 | Four injected 503 responses | `RETRY_EXHAUSTED`, failed execution, durable failure receipt |
| 28 | Injected 403 | One attempt, failed execution, durable failure receipt |

The verification driver additionally repeated delivery against the actual HTTP double after n8n dispatch (duplicate receipt), and tried old AMB-02 delivery after replacement (409). Tests exercise duplicate callbacks, concurrent delivery, SQLite restart persistence, wrong incident/resource/version, expired leases, automation approval rejection, forged commands, changed-payload conflicts, stale completion and terminal state. A final regression test verifies an already accepted callback cannot be overwritten by a different failure event.

Final canonical fixture: one report, two explicit approvals, two delivery effects, AMB-02/ASG-887 superseded, ASG-888/RESCUE-01 and ASG-889/AMB-05 completed, all three resources available, one resolution event, phase `resolved`. The double's predefined analysis is labelled synthetic; it is not AI evidence.

## Reproduce

Fast checks from repository root:

```text
python -m unittest discover -s n8n/tests -p 'test_*.py' -v
node --test n8n/tests/workflows.test.js
node n8n/scripts/build_workflows.js
```

Actual CLI run, with an installed n8n 2.39.8 binary and a **dedicated disposable profile**, no presentation service on port 8094:

```text
python n8n/scripts/verify_n8n.py --n8n-bin /absolute/path/to/n8n --profile /absolute/path/to/disposable-profile
```

This driver launches its own fixture server, imports the exports and runs the 14 scenarios. It supplies simulated coordinator decisions **between** workflow executions; the workflows cannot approve. Re-runs generate new execution IDs/timestamps and replace evidence. A local fixture approval helper for actual human-driven presentation is documented separately in README.

## Repository boundary

Base: frontend `fc2d69a62caaebe4bcd1ba286741598225ae2299`, selected only after confirming branch ancestry and inspecting handoff. No merge/cherry-pick. All changes are under `n8n/`. Backend and AI source were inspected via `git show` at their remote refs. Teammate suites were not run or modified. No real messages, provider requests or responders were contacted. Only `origin/n8n` is authorized for publication.
