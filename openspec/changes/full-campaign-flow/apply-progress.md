# Apply Progress: Full Campaign Flow

Cumulative across batches. Latest batch: PR-2 Execution Substrate (REQ-26..28, 42).

## PR-1: Custom-Project Generator (REQ-22..25) — COMPLETE

- [x] 1.1 RED: order/GoToTask/databank tests (REQ-22)
- [x] 1.2 `customproject/models.py` — CustomProject, CustomProjectTask, GoToTask, DatabankSpec, Filters
- [x] 1.3 `catalog.py` (21) + `renderers.py` per-type sections, WF in CrossChecks, unknown→Error (REQ-25)
- [x] 1.4 `generator.py` + `writer._write_project_archive` — Databanks, per-task type, taskXMLFile (REQ-23)
- [x] 1.5 RED: `validator.py` golden + `sqcli -h`; deviation→ValidationError, no dispatch (REQ-24)
- [x] 1.6 E2E: loadconfig accepts 4-task archive; single-task byte-identity (REQ-23)

Commits: `680b67e`, `de914cd`, `eecd919` on `feat/llm-generation-monitor-slice1`.

Evidence: `pytest tests/customproject/ -q` → 58 passed, 4 skipped; E2E suite 6 passed in 3:39.

## PR-2: Execution Substrate (REQ-26..28, 42) — COMPLETE

- [x] 2.1 RED: mock parity + resume tests (REQ-28, REQ-26) — `tests/substrate/`
- [x] 2.2 `substrate/executor.py` + `lifecycle.py` — state machine, PhaseResult (REQ-26)
- [x] 2.3 `poller.py`, `events.py` (CampaignMonitor, REQ-42), `exporter.py`
- [x] 2.4 RED: sqcli selectors — relative, missing, `SQCLI_PATH`, mock (fail-closed)
- [x] 2.5 retest→optimize in one load, gate hold (REQ-27); legacy parity (REQ-28)

Commit: `d88dca4` on `feat/execution-substrate` (stacked off `feat/llm-generation-monitor-slice1`).

### Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `SQX_FORCE_MOCK=1 pytest tests/substrate/ -q` → **17 passed** (38.15s); plain `pytest tests/substrate/ -q` → **17 passed** (37.95s) |
| Runtime harness command/scenario and exact result | Mock parity + resume + chained chain against live mock server on port 5050 (16 integration tests in `test_executor.py`, `test_chained_tasks.py` hit real HTTP through `AsyncSQXClient`); regression `pytest tests/sqx/ -q` → 24 passed; `pytest tests/customproject/ -q` → 58 passed, 4 skipped |
| Rollback boundary | `QUANTLAB_UNIFIED_SUBSTRATE=1` opts into the substrate (default `0` → legacy paths operational, REQ-28). The substrate is a new package (`sdk/quantlab/substrate/`) plus new tests; reverting commit `d88dca4` removes all substrate code without touching PR-1 or legacy files |

### Deviations from Design

- Task 2.5's `execute_chain` was implemented ahead of its RED test (RED→GREEN order inverted for that one unit). The chained tests were then written and pass — behavior matches the REQ-27 contract, but the strict TDD evidence for 2.5 is test-after-code. All other units followed RED → GREEN.

### Notes / Gotchas

- `tests/` has no `__init__.py`, so pytest inserts `tests/substrate/` as the import root; cross-module `from tests.substrate...` imports fail. Test doubles live inline in each test module.
- The executor must advance through the transient `RUNNING` state (`STARTED → RUNNING → COMPLETED`) — the state machine rejects a direct `STARTED → COMPLETED`.
- Resume syncs the daemon lifecycle to the last completed stage (`resume_at`) so a fresh daemon does not force a re-dispatch (REQ-26 s2: resume at N+1).

## Remaining PRs (not in scope for this batch)

- [ ] PR-3: Compiler Pipeline (REQ-29..30, 39) — tasks 3.1-3.4
- [ ] PR-4: Demo Deploy + Gates (REQ-31..32, 38) — tasks 4.1-4.3
- [ ] PR-5: Archive + Feedback (REQ-33..34, 40..41) — tasks 5.1-5.4
- [ ] PR-6: Mobile + Orchestration (REQ-35..36, 01M, 37, 43..44) — tasks 6.1-6.4
