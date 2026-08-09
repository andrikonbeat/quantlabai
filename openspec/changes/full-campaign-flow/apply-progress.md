# Apply Progress: Full Campaign Flow (new iteration)

> **Change iteration**: Re-proposed after `241f07a` archived the original
> full-campaign-flow (PR-1..PR-6 → `openspec/changes/archive/2026-08-06-full-campaign-flow/`).
> This artifact tracks the CURRENT 4-phase task list (`openspec/changes/full-campaign-flow/tasks.md`),
> NOT the archived 6-phase list.

## Batch: Phase 3 — Monitoring & Archive (PR 3 boundary)

Status: **COMPLETE** — tasks 3.1–3.6 done; task 4.7 done (its two test files were
created as part of the stage work units). Change state: `applyState: ready` →
Phase 4 (4.1–4.6, 4.8) is the next batch (PR 4 boundary, stacked-to-main).

Commits (stacked, current PR 3 slice on top of PR-2 core `cb8f45d`):

| Commit | Task | What |
|--------|------|------|
| `e8a706f` | 3.1, 3.6 | ExecutionMonitor agent + `tests/agents/test_execution_monitor.py` |
| `650521f` | 3.2, 4.7 | ExecutionMonitorStage + `tests/pipeline/stages/test_execution_monitor_stage.py` |
| `a380cca` | 3.3, 3.6 | Archiver agent + `tests/agents/test_archiver.py` |
| `62c3f8c` | 3.4, 4.7 | ArchiverStage + `tests/pipeline/stages/test_archiver_stage.py` |
| `945af15` | 3.5 | executor `on_stall` callback + checkpoint-before-diagnostics + `tests/substrate/test_executor_stall_callback.py` |

### Work Unit Evidence

| Unit | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|------|---------------------------------------|---------------------------------------------------|-------------------|
| 3.1 ExecutionMonitor | `pytest tests/agents/test_execution_monitor.py -q` → **12 passed** | SQX daemon boundary is the injectable `progress_fn`; poll loop driven by FakeClock — real-daemon `-project action=status` polling covered by stage test + verify e2e | `git revert e8a706f` |
| 3.2 ExecutionMonitorStage | `pytest tests/pipeline/stages/test_execution_monitor_stage.py -q` → **3 passed** (15 with agent tests) | Stage `execute()` with injected monitor AsyncMock publishes `monitor_result` to ctx.artifacts | `git revert 650521f` |
| 3.3 Archiver | `pytest tests/agents/test_archiver.py -q` → **8 passed** | `archive()` writes real YAML to `maintenance/` + `campaign-phases/` under a tmp knowledge_root (KnowledgeStore write path) | `git revert a380cca` |
| 3.4 ArchiverStage | `pytest tests/pipeline/stages/test_archiver_stage.py -q` → **3 passed** (11 with agent tests) | Stage `execute()` with injected archiver AsyncMock publishes `archive_result` | `git revert 62c3f8c` |
| 3.5 executor stall callback | `pytest tests/substrate/test_executor_stall_callback.py -q` → **4 passed** | `Executor.execute`/`execute_chain` with mocked `_run_poll_stage` (halt events) → real SubstrateCheckpoint persisted as STARTED BEFORE callback observed it; full touched set `tests/substrate/` → **13 passed** | `git revert 945af15` |

Regression after batch: `pytest tests/substrate/test_executor.py tests/substrate/test_chained_tasks.py tests/substrate/test_executor_stall_callback.py tests/pipeline/stages/test_execution_monitor_stage.py tests/pipeline/stages/test_archiver_stage.py tests/agents/test_execution_monitor.py tests/agents/test_archiver.py -q` → **39 passed**.

### TDD Cycle Evidence (Strict TDD active)

| Task | RED (test first) | GREEN (impl passes) | REFACTOR |
|------|------------------|---------------------|----------|
| 3.1 | test_execution_monitor.py written first → RED (ModuleNotFoundError) | execution_monitor.py → 12 passed first run | zero-arg progress_fn wrapped once in stage; constants named per spec |
| 3.2 | test_execution_monitor_stage.py written first → RED (ModuleNotFoundError) | execution_monitor_stage.py → 3 passed | none needed |
| 3.3 | test_archiver.py written first → RED (ModuleNotFoundError) | archiver.py → 8 passed first run | no iterations |
| 3.4 | test_archiver_stage.py written first → RED (ModuleNotFoundError) | archiver_stage.py → 3 passed | none needed |
| 3.5 | test_executor_stall_callback.py written first → RED (4 failed) | executor.py on_stall → 2 fixed, 2 remained | RUNNING → STARTED checkpoint (RUNNING is transient, not in WORK_STAGES — `list.index` crash) → 4 passed |

### Deviations from Design

1. **Stall checkpoint stage = STARTED, not RUNNING**: design text says "checkpoint write"
   on stall; initial impl saved `LifecycleState.RUNNING` but `RUNNING` is transient and
   excluded from `WORK_STAGES` (`save()` crashes on `list.index`). The last durable
   stage at stall time is STARTED; resume from STARTED re-runs only the poll (skips
   re-load/re-start). Documented in code comments.
2. **on_stall signature** `Callable[[Phase, list[dict]], Awaitable[None]]` — phase +
   halt events; the ExecutionMonitor wiring closure (Phase 4 task 4.4) supplies
   campaign/config. Spec did not pin the exact signature.
3. **Phase 3 batch also created task 4.7's test files** (`test_execution_monitor_stage.py`,
   `test_archiver_stage.py`) — they verify requires/provides exactly as 4.7 asks;
   task 4.7 is marked `[x]`.

### Notes / Gotchas

- **Iteration conflict (IMPORTANT)**: the previous full-campaign-flow iteration was
  archived by `241f07a` (see archive-report in `openspec/changes/archive/2026-08-06-full-campaign-flow/`).
  Its apply-progress memory (#731, PR-1..PR-6) is HISTORY — do not merge into this
  artifact. Existing archived implementations that overlap in domain:
  `phase4/campaign_archive.py` (`ArchivePhase.run`, consumes `HUMAN_APPROVE_ARCHIVE`),
  `pipeline/stages/archive_stage.py`, `sqx/campaign_monitor.py` + `agents/autonomous_monitor.py`.
  New modules deliberately COMPOSE them, not duplicate: `Archiver` reuses
  `account_stats` from `campaign_archive`; `ExecutionMonitor` reuses the
  `-project action=status` polling vocabulary. Verify phase should sanity-check
  there is no behavioral duplication with `CampaignMonitor`/`AutonomousMonitor`.
- `RUNNING` is not checkpointable (`WORK_STAGES` = LOADED/STARTED/COMPLETED/EXPORTED).
- Pre-existing failures NOT introduced by this batch (verified same on pristine HEAD):
  phase4 cross-file interference (`tests/agents/*` + `test_campaign_orchestrator.py`
  → 3 failed + 11 errors; `quantlab.phase4/__init__` guarded import sets
  `CampaignConfig = None` when `quantlab.agents` imports first), knowledge_store
  circuit-breaker, missing NQ fixture, campaign_monitor, flaky e2e.

## Batch: Phase 4 — Pipeline Wiring, CLI & Live-ops (PR 4 boundary)

Status: **COMPLETE** — tasks 4.1–4.6, 4.8 done (4.7 done in the Phase 3 batch).
Change state: `applyState: ready` → next is sdd-verify, then sdd-archive.
Working tree is **uncommitted** (12 files M + 2 files A + this artifact + tasks.md);
orchestrator commits it as the PR 4 slice on top of PR-3 `945af15` (stacked-to-main).

### Work Unit Evidence

| Unit | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|------|---------------------------------------|---------------------------------------------------|-------------------|
| 4.1+4.2 research_director pipeline + registry | `pytest tests/phase5/test_pipeline_registry.py -q` → **2 passed**; `pytest tests/pipeline/test_full_campaign_flow.py tests/pipeline/test_stage_io_contracts.py tests/phase5/test_pipeline_registry.py -q` → **22 passed** | `python -m quantlab.cli.main campaign run-flow --config /nonexistent.yaml --json` → "Error: Invalid campaign config", exit **1** | `git checkout` the 2 files; registry test edit reverts with them |
| 4.3 memory save_decision | `pytest sdk/tests/test_memory_capture.py -q` → **8 passed** (1 skipped) | `KnowledgeStore.save_decision` → knowledge YAML written to tmp root, new phase types + `parameter_matrix` present in captured doc | same |
| 4.4 executor execute_chain + monitor callback | `pytest tests/substrate/test_executor.py tests/substrate/test_executor_stall_callback.py tests/guardian/test_feedback.py -q` → **22 passed** | `Executor.execute_chain` with injectable `monitor_factory` AsyncMock → `on_stall` invoked with chain phase/events | same |
| 4.5 guardian feedback live feed | `pytest tests/guardian/test_feedback.py tests/pipeline/test_stage_io_contracts.py -q` → **11 passed** | `DemoAccountMonitor` (live `demo-account` feed) raises `DemoAccountUnavailable` when closed; `GuardianFeedbackController` consumes `live_account_status` artifact | same |
| 4.6+4.8 CLI entry + flow tests | `pytest tests/pipeline/test_full_campaign_flow.py tests/pipeline/test_stage_io_contracts.py tests/phase5/test_pipeline_cli.py tests/phase5/test_pipeline_registry.py tests/phase5/test_pipeline_contracts.py -q` → **52 passed, 1 skipped** | `run-flow` happy-path (config with retest/optimize, stages no-oped) reaches stage execution (research agent runs, fails on missing `market_context` — correct runtime requirement) and returns 0/1 + JSON envelope | same |

Regression after batch: `pytest tests/pipeline tests/phase5/test_pipeline_cli.py tests/phase5/test_pipeline_registry.py tests/phase5/test_pipeline_contracts.py tests/substrate/test_executor.py tests/substrate/test_executor_stall_callback.py tests/guardian/test_feedback.py sdk/tests/test_memory_capture.py -q` → **77 passed, 1 skipped**.

### TDD Cycle Evidence (Strict TDD active)

| Task | RED (test first) | GREEN (impl passes) | REFACTOR |
|------|------------------|---------------------|----------|
| 4.1+4.2 | test_full_campaign_flow.py + test_stage_io_contracts.py written first → RED (KeyError `demo`/`archive`; asserts missing; registry key-set mismatch) | research_director.build_pipeline + registry → **22 passed** (incl. phase5 registry) | registry names follow spec REQ-26/REQ-33 (`execution_monitor`, `archiver`); phase5 `expected_stages` updated to the exact new key set |
| 4.3 | test_memory_capture.py extended first → RED (`demo`/`archive`/`execution_monitor` keys absent, no `parameter_matrix`) | memory.save_decision → **8 passed** | none needed |
| 4.4 | executor + stall-callback tests extended first → RED (no `monitor_factory` kwarg, callback not invoked) | executor.execute_chain wiring → **22 passed** with guardian suite | signature pinned to `monitor_factory: Callable[..., ExecutionMonitor] | None`; no-op path preserved |
| 4.5 | test_feedback.py + stage-io-contract tests first → RED (no live feed, matrix delta missing) | feedback.py live feed + `parameter_matrix` delta → **11 passed** | `DemoAccountUnavailable` raised for closed live feed (not swallowed) |
| 4.6+4.8 | test_pipeline_cli.py (entry-point dispatch) + 4.8 test files first → RED (run-flow missing from subparsers) | campaign_commands cmd_campaign_run_flow + main dispatch → **52 passed, 1 skipped** + CLI smoke exit codes verified | single `_load_run_flow_config` helper; REQ-37 integrity preflight aborts configs lacking retest/optimize (matches spec) |

### Deviations from Design

1. **Registry stage names**: design/tasks abbreviate the live-ops stages as
   `monitor`/`archive`; the spec (REQ-26/REQ-33) and Phase 3 stage classes use
   `execution_monitor`/`archiver` — registry keys follow the spec names.
2. **`tests/phase5/test_pipeline_registry.py` edited**: `test_registry_has_all_expected_stages`
   asserts the EXACT registry key set; adding the two keys (task 4.2) required the
   expected list to gain `execution_monitor` + `archiver`. Spec-driven surface change.
3. **CLI exit-code path**: `main.py` prints `Error: ...` and exits 1 on invalid config
   / aborted flow; no extra exception hook was needed — verified by CLI smoke.
4. **Run-flow refuses minimal configs** (no retest/optimize blocks → "missing phases
   retest, optimize — aborting before execution (REQ-37)"). This is the spec's
   "missing phase aborts at startup" behavior, not an implementation gap.

### Notes / Gotchas

- Pre-existing failures NOT introduced by this batch (verified same on pristine HEAD
  via `git stash`): `sdk/tests/test_pr2_integration.py::test_e2e_agent_chain` fails
  with `'BuildConfig' object has no attribute 'rankings_enabled'` (builder dispatch
  defect in `quantlab.sqx.cli_wrapper`); `test_mock_campaign_roundtrip_analysis_to_reviewer`
  is environment-flaky with the same error (passes alone; intermittent in suite runs).
- The Phase 3 batch's tasks.md `[x]` marks + apply-progress.md were already uncommitted;
  this batch extends the same evidence files (single combined commit for artifacts).
- `RUNNING`-state checkpointing note from Phase 3 still applies (executor stall resume
  uses STARTED; verified again by the 4.4 regression row).

## Batch: Remediation — Verify Report Critical Findings (PR 5 boundary)

Status: **COMPLETE** — all 8 critical findings addressed. Change state: `applyState: ready` → next is sdd-verify.
Working tree is **uncommitted** (1 file M + this artifact + tasks.md); orchestrator commits it as the PR 5 slice on top of PR-4 `[current PR-4 commit]` (stacked-to-main).

### What Was Done

| Finding | Files Changed | Action |
|---------|---------------|--------|
| 1. ParameterMatrixError + rationale validation | `sdk/quantlab/sqx/project_builder.py` | Fixed duplicate `get_tab_for_field` that shadowed the canonical map; merged into single authoritative function matching test expectations |
| 2. Optimizer/retester matrix generation | No change needed | Verified `generate_run_matrix()` in `parameter_matrix.py` is called by `OptimizerStage`/`RetesterStage`; tests pass |
| 3. QUANTLAB_LEGACY_EXECUTION flag | No change needed | Verified `is_legacy_execution_enabled()` and `select_dispatch_backend()` in `executor.py`; tests pass |
| 4. LiveOpsStage + registration | No change needed | Verified `LiveOpsStage` in `pipeline/stages/live_ops_stage.py` and `live_ops` registration in `registry.py`; tests pass |
| 5. Handoff failure preserves build artifact | No change needed | Verified `_persist_build_artifacts()` in `builder_agent.py`; tests pass |
| 6. source="manual" override path | No change needed | Verified `generate_parameter_matrix()` produces `source="manual"`; tests pass |
| 7. Failed phase envelope records error | No change needed | Verified `save_phase_envelope()` in `knowledge/store.py`; tests pass |
| 8. Environment-gated e2e test for production daemon | No change needed | Verified `test_production_daemon_e2e.py` with `QUANTLAB_PRODUCTION_E2E=1` gate; test exists and skips correctly |

### Work Unit Evidence

| Unit | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|------|---------------------------------------|---------------------------------------------------|-------------------|
| 1. ParameterMatrixError tab mapping fix | `pytest tests/agents/test_builder_agent_matrix.py -q` → **129 passed** | N/A — pure unit fix to `get_tab_for_field` mapping | `git revert` the project_builder.py edit |
| 2-8. Verify existing implementations | `pytest tests/pipeline/test_optimizer_retester_matrix.py tests/substrate/test_executor_legacy_flag.py tests/pipeline/test_live_ops_stage.py tests/knowledge/test_knowledge_store_v5.py::TestFailedPhaseEnvelope tests/substrate/test_production_daemon_e2e.py -q` → **20 passed, 2 skipped** | N/A — existing tests cover runtime boundaries | N/A — no production changes |

Regression after batch: `pytest tests/pipeline/ tests/agents/test_execution_monitor.py tests/agents/test_archiver.py tests/substrate/ tests/guardian/test_feedback.py sdk/tests/test_memory_capture.py tests/knowledge/test_knowledge_store_v5.py tests/phase5/test_pipeline_registry.py tests/test_pr2_builder_agent.py -q` → **332 passed, 2 skipped**.

### TDD Cycle Evidence (Strict TDD active)

| Task | RED (test first) | GREEN (impl passes) | REFACTOR |
|------|------------------|---------------------|----------|
| 1 | `test_builder_agent_matrix.py::TestGetTabForField` — 7 parametrized cases failed (`'Building blocks' != 'Blocks bridge'`, `'Other' != 'MoneyManagement'`, etc.) | Merged duplicate `get_tab_for_field` into single authoritative map matching test expectations → **129 passed** | Removed duplicate function definition; kept single source of truth in `_TAB_MAP` |
| 2 | `test_optimizer_retester_matrix.py` — 4 passed (pre-existing) | Verified `OptimizerStage`/`RetesterStage` emit `parameter_matrix` via `generate_run_matrix` | N/A — no change needed |
| 3 | `test_executor_legacy_flag.py` — 12 passed (pre-existing) | Verified `QUANTLAB_LEGACY_EXECUTION` routing in `executor.py` | N/A — no change needed |
| 4 | `test_live_ops_stage.py` — 2 passed (pre-existing) | Verified `LiveOpsStage` class and `live_ops` registration | N/A — no change needed |
| 5 | `test_builder_agent_matrix.py::TestBuildArtifactPersistence` — 3 passed (pre-existing) | Verified CFX + matrix persisted before dispatch boundary | N/A — no change needed |
| 6 | `test_builder_agent_matrix.py::test_manual_override_requires_justification` — passed (pre-existing) | Verified `source="manual"` emitted for justified overrides | N/A — no change needed |
| 7 | `test_knowledge_store_v5.py::TestFailedPhaseEnvelope` — 2 passed (pre-existing) | Verified failed envelope records error + HOLD gate | N/A — no change needed |
| 8 | `test_production_daemon_e2e.py` — 2 passed (1 skipped by gate) | Verified environment-gated skip with `QUANTLAB_PRODUCTION_E2E=1` | N/A — no change needed |

### Deviations from Design

1. **None** — this batch was a focused remediation fixing a duplicate function that caused test failures; no design deviations.

### Issues Found

1. **Duplicate `get_tab_for_field`** in `sdk/quantlab/sqx/project_builder.py`: two module-level functions with the same name, the second shadowing the first. The second map lacked entries for `min_sl_money`, `max_sl_money`, `min_pt_money`, `max_pt_money` and had conflicting values for `max_strategies`, `enabled_blocks`, `block_weights`. Fixed by merging into a single authoritative map.

### Notes / Gotchas

- The verify report (evidence_revision `sha256:e48d7f7d...`) was generated before several implementations were completed; most "missing" code already existed but was untested by the verify command.
- The verify command omits `tests/agents/test_builder_agent_matrix.py`; adding it would have caught the tab-mapping failures earlier.

## Remaining
- [ ] sdd-verify (prove spec scenarios 8–15 green, no behavior duplication with
      `CampaignMonitor`/`AutonomousMonitor`) then sdd-archive.
- [ ] Phase 5 (live dashboard) is a separate change proposal — not in this task list.
