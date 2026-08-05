# Apply Progress: Full Campaign Flow

Cumulative across batches. Latest batch: PR-6 Mobile + Orchestration (REQ-35..36, 01M, 37, 43..44).

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

## PR-3: Compiler Pipeline (REQ-29..30, 39) — COMPLETE

- [x] 3.1 RED: missing JDK→CompilerConfigError, no partial .jfx; non-exec javac (REQ-29)
- [x] 3.2 `compiler/compiler.py` javac compile + `jfx.py` packaging (REQ-29)
- [x] 3.3 `fixloop.py` bounded fix, per-iteration log, bound→CompileError + history (REQ-30)
- [x] 3.4 `jforex_deploy.py` .jfx routing; RED: compile failure blocks deploy (REQ-39)

Commits: `121e9e3`, `4aed525`, `805269b` on `feat/compiler-pipeline` (stacked off `feat/execution-substrate`).

### Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `pytest tests/compiler/ -q` → **40 passed** (0.79s). Per-unit: config/compile/package (3.1+3.2) 24 passed; `test_fixloop.py` (3.3) 8 passed; `test_jforex_routing.py` (3.4) 8 passed |
| Runtime harness command/scenario and exact result | Fake-JDK subprocess harness: every test builds a real `jdk/bin/javac` shell script executed via `subprocess.run` (no system JDK — the environment has none). Covered: missing JDK / non-executable javac fail-closed, happy compile → `.jfx` ZIP with class entries, self-correcting fix loop (fail → fix → recompile → package), bound-halt → CompileError + history, deploy routing. Regression: `pytest tests/substrate/ -q` → 17 passed; `pytest tests/phase4/ tests/substrate/ -q` → 625 passed, 2 pre-existing failures (see Notes) |
| Rollback boundary | `QUANTLAB_COMPILER=0` keeps the `.java`-only deploy path (`compile_strategy` returns the `java_path` unchanged, no compile runs). New package `sdk/quantlab/compiler/` + `tests/compiler/`; the only touched existing file is `sdk/quantlab/phase4/jforex_deploy.py` (additive methods `compile_strategy`/`export_and_compile` — `export_strategy` unchanged). Reverting `121e9e3..805269b` removes all compiler code without touching PR-1/PR-2 |

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1 | `tests/compiler/test_compiler_config.py` | Unit | N/A (new pkg) | ✅ Written (ModuleNotFoundError before impl) | ✅ Passed | ✅ 10 cases | ✅ Clean |
| 3.2 | `tests/compiler/test_compiler.py` + `test_jfx.py` | Unit | N/A (new pkg) | ✅ Written before impl | ✅ Passed | ✅ 11 cases | ✅ Clean |
| 3.3 | `tests/compiler/test_fixloop.py` | Unit | N/A (new pkg) | ✅ Written (ModuleNotFoundError) | ✅ Passed | ✅ 7 cases | ✅ Clean |
| 3.4 | `tests/compiler/test_jforex_routing.py` | Unit | ✅ 625 passed (phase4+substrate) | ✅ Written (AttributeError before impl) | ✅ Passed | ✅ 8 cases | ✅ Clean |

### Deviations from Design

- **JDK env var resolved**: design AD-5/Slice 3 list `QUANTLAB_JDK_HOME` (design text mentions `JDK_HOME` in one spot). Verified the existing `jforex_deploy.py` has NO JDK dependency, so `QUANTLAB_JDK_HOME` is the canonical variable (open question closed: no `JDK_HOME`/`JAVA_HOME` fallback, fail-closed per AD-5).
- **`errors.py` added**: design lists `compiler.py`/`fixloop.py`/`jfx.py` only; a shared `errors.py` leaf (matching the existing `phase4/errors.py` convention) avoids a `compiler ↔ fixloop` import cycle. Three behavior modules unchanged from design.
- **`.jfx` layout provisional**: JAR-with-classes ZIP chosen (REQ-29 "package compiled classes into a .jfx archive"); design open question "JAR-with-classes vs SQX-native layout" remains open pending JForex 4 verification (PR-4/demo).
- **Fixer is injected, not an LLM client**: the loop is the REQ-30 contract; real LLM wiring is deferred (later integration), consistent with design's "LLM-guided" wording.

### Notes / Gotchas

- Environment has **no JDK** (no `java`, no `javac`, no `QUANTLAB_JDK_HOME`); all tests simulate javac with fake executables and never depend on a JDK.
- `run_fix_loop` writes the fixer's amended text back to the source path before EVERY recompile; `run_javac` wipes the classes dir per invocation so stale classes never leak into a later package.
- Pre-existing failures NOT caused by PR-3 (confirmed failing at base `09ac069`): `tests/phase4/test_project_builder.py::TestBuildConfigMapCoverage::{test_all_buildconfig_fields_in_map, test_map_entries_have_valid_format_types}` — left untouched per strict-TDD rule.

## Remaining PRs (not in scope for this batch)

- [x] PR-5: Archive + Feedback (REQ-33..34, 40..41) — tasks 5.1-5.4 (see below)
- [ ] PR-6: Mobile + Orchestration (REQ-35..36, 01M, 37, 43..44) — tasks 6.1-6.4

## PR-4: Demo Deploy + Gates (REQ-31..32, 38) — COMPLETE

- [x] 4.1 DEMO/ARCHIVE gates into GATE_POLICIES+GATE_IDS, HOLD; RED: no auto-approve, question-tool (REQ-38)
- [x] 4.2 `demo_deploy.py` 14-day window, expiry block + reminder (REQ-31)
- [x] 4.3 `deployment_agent.py` real JAR + JCloud; dry-run mock, no network (REQ-32)

Commits: `4289c89` (gates), `af3f7ea` (demo window), `80d3ac9` (real JAR) on `feat/demo-deploy-gates` (stacked off `feat/compiler-pipeline`).

### What

- **4.1 (REQ-38)**: `sdk/quantlab/gates/models.py` — added `HUMAN_APPROVE_DEMO` (12h) and `HUMAN_APPROVE_ARCHIVE` (24h) to `DEFAULT_GATE_POLICIES` with `FallbackPolicy.HOLD`, fail-closed; `HUMAN_GATE_IDS` derives from `DEFAULT_GATE_POLICIES.keys()` so both auto-register. Both gates resolve via the existing `QuestionToolGateCallback` decision-file protocol (question tool) with stdin fallback. Orchestrator with no callback applies the HOLD fallback — never auto-approves. Also fixed a pre-existing bug: `GateDecisionAction` had no `ABORT` member so `GateDecision.is_terminal()` raised AttributeError on every call (REQ-38 "denial blocks the phase" depends on it) — additive enum member, zero behavior change elsewhere.
- **4.2 (REQ-31)**: new `sdk/quantlab/phase4/demo_deploy.py` — pure business-day arithmetic (`add_business_days`, weekends skipped, negative offsets), `DemoWindow` (14 business days, `reminder_at` 2 business days pre-expiry, `status() → ACTIVE/REMINDER_DUE/EXPIRED`), `RenewalReminder`, `DemoDeployer.deploy(artifact, account, now)` — ACTIVE deploys; REMINDER_DUE deploys AND dispatches the renewal reminder; EXPIRED **blocks** returning `DeploymentResult(status="BLOCKED_EXPIRED", pending_gate="HUMAN_APPROVE_DEMO")` and dispatches a reminder naming the gate — the deploy backend is never invoked (fail-closed). Rollback flag `QUANTLAB_DEMO_DRY_RUN` (unset → dry-run default on). Added additive `pending_gate: str = ""` field to `DeploymentResult`.
- **4.3 (REQ-32)**: `sdk/quantlab/agents/deployment_agent.py` — new `JCloudConfig` (account/server/symbols, `to_manifest`/`from_manifest`), pure `build_deployable_jar` (real ZIP: `META-INF/MANIFEST.MF` + `strategies/{name}.jfx` embedded + `jcloud.json` applied), `build_cfx_jar` (pipeline CFX path), `DeploymentAgent.package_jfx(jfx, account)` — dry-run → `DRY_RUN_SUCCESS` with mock JAR, **zero network** (no HTTP code exists on the path); live → local simulation `DEPLOYED` with instance ids. The `PK\x05\x06` placeholder stub is **gone** — `_package_for_jforex` now builds a real JAR embedding the CFX.

### Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `pytest tests/demo_deploy/ tests/gates/ -q` → **38 passed** (0.74s). Per unit: gates (4.1) 11 passed; demo window + deployer (4.2) 19 passed; deployment-agent JAR (4.3) 8 passed |
| Runtime harness command/scenario and exact result | Real `DemoDeployer` default path (no injected deploy_fn) → `DeploymentAgent.package_jfx` in dry-run: status `DRY_RUN_SUCCESS`, JAR is a real ZIP with `META-INF/MANIFEST.MF`, `strategies/DemoStrategy.jfx`, `jcloud.json` (`account/server/symbols` applied); expired window → `BLOCKED_EXPIRED` + `pending_gate=HUMAN_APPROVE_DEMO`. Zero network (no HTTP client invoked). Regression: `pytest sdk/tests/gates/ sdk/tests/test_pr4_deployment_agent.py -q` → 25 passed; `sdk/tests/test_pr4_integration.py test_pipeline_gate_interceptor.py test_pipeline_integration.py` → 30 passed; `tests/compiler/ tests/substrate/ tests/customproject/` → 115 passed, 4 skipped; `tests/phase4/ -k "jforex or deploy"` → 5 passed |
| Rollback boundary | `QUANTLAB_DEMO_DRY_RUN` unset/`1` → dry-run default on (live path only via explicit `0`). `DemoDeployer.deploy_fn`/`notifier_fn` are injected; all new code is additive (2 new policy entries, 1 enum member, 1 dataclass field, new module `phase4/demo_deploy.py`). Reverting `4289c89..80d3ac9` removes PR-4 without touching PR-1/2/3 |

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.1 | `tests/gates/test_demo_archive_gates.py` | Unit | ✅ 25 passed (gates+deployment) | ✅ Written (8 failed: missing gates, ESCALATE fallback) | ✅ Passed | ✅ 11 cases (HOLD fallback ×2, question-tool approve, denial, existing gates) | ✅ Clean |
| 4.2 | `tests/demo_deploy/test_demo_window.py` + `test_demo_deployer.py` | Unit | ✅ 25 passed | ✅ Written (ModuleNotFoundError) | ✅ Passed | ✅ 19 cases (weekend, month rollover, negative, boundaries, block, reminder-once) | ✅ Clean |
| 4.3 | `tests/demo_deploy/test_deployment_agent_jar.py` | Unit | ✅ 25 passed | ✅ Written (ImportError: JCloudConfig) | ✅ Passed | ✅ 8 cases (embed, manifest, config applied, dry-run no-network, live sim, stub gone) | ✅ Clean (1 test fixed: compared against .jfx bytes, not inner class) |

### Deviations from Design

- **`GateDecisionAction.ABORT` enum fix** (discovered pre-existing bug): `is_terminal()` referenced a nonexistent `GateDecisionAction.ABORT` and raised AttributeError on every call. Fixed additively because REQ-38 denial-blocking semantics depend on it. No production caller existed (verified by grep), so zero behavior change beyond the fix.
- **`DeploymentResult.pending_gate` field added** (design only specified the deploy result envelope): needed so `BLOCKED_EXPIRED` can name the required gate (`HUMAN_APPROVE_DEMO`) — additive field with default, existing consumers unaffected.
- **Live JCloud deploy stays a local simulation**: the SDK has no JCloud API client (verified: no HTTP deploy code); REQ-32 "deployable JAR" (real packaging) is fully implemented; live upload remains the documented stand-in consistent with the pre-existing `_deploy_live` simulation. Dry-run never touches network.
- **14-day window is a software deadline**: per exploration note, this enforces campaign validity (business-day arithmetic), not a Dukascopy renewal mechanism.

### Notes / Gotchas

- `DemoDeployer` keeps `phase4` free of a module-level `agents` dependency: `DeploymentAgent`/`DeploymentResult` are imported lazily inside methods (avoids a phase4 → agents → pipeline → phase4 cycle).
- `is_demo_dry_run` treats unset and empty env as dry-run `True`; only explicit `"0"`/`"false"` opts out.
- Pre-existing failures NOT caused by PR-4 (confirmed at base `09ac069`, PR-3 notes): `tests/phase4/test_project_builder.py::TestBuildConfigMapCoverage::{test_all_buildconfig_fields_in_map, test_map_entries_have_valid_format_types}` — untouched.
- Latent quirk (NOT changed, out of PR-4 scope): `GateDecision.is_approved()` returns `True` for `FALLBACK`, so the orchestrator's HOLD fallback action (`FALLBACK`) reads as approved to that helper. No production consumer uses `is_approved()` (grep-verified); PR-4 consumers gate on explicit `action == APPROVE`. Flag for PR-6 (notifiers/orchestration consumers) before they rely on `is_approved()`.

## PR-5: Archive + Feedback (REQ-33..34, 40..41) — COMPLETE

- [x] 5.1 `feedback.py` record()→FeedbackRecord at archive; RED: gates never bypassed (REQ-34)
- [x] 5.2 `stream_live()` feed; RED: STREAM_LOST hold, no transition (REQ-41, REQ-40)
- [x] 5.3 MetaGuardian live eval — drawdown>10%→DEFENSIVE + feedback (REQ-40)
- [x] 5.4 `campaign_archive.py` plan/stats/bundle; DEGRADING→replacement, ARCHIVE gate (REQ-33)

Commits: `1bf1b72` (feedback), `9295a76` (live feed + hold), `a5ec7d0` (live eval), `0ee36e0` (archive phase) on `feat/archive-feedback` (stacked off `feat/demo-deploy-gates`).

### What

- **5.1 (REQ-34)**: new `sdk/quantlab/guardian/feedback.py` — pure `record(campaign_id, signals)` → `FeedbackRecord` carrying degradation/drawdown/regime/cost signals, with `suggests_replacement()` and `next_cycle_inputs()` (reshapes signals for next-cycle generation, REQ-34 s1). The module imports NO gate machinery (`test_feedback_module_does_not_import_gate_machinery`), so feedback cannot bypass gates by construction; tests prove `HUMAN_GATE_IDS` is unchanged by record() and the archive gate still holds afterwards (REQ-34 s2).
- **5.2 (REQ-41/REQ-40)**: `sdk/quantlab/agents/autonomous_monitor.py` — `AutonomousMonitorDaemon.stream_live(campaign_id)` consumes the account feed and delivers every equity point to the MetaGuardian live evaluator (injectable `set_live_evaluator`) while heartbeat/metrics continue; `_on_point` now routes points through `_deliver_live_point`. On stream loss beyond `max_retries`, `_reconnect` enters a **STREAM_LOST hold** (`stream_state="STREAM_LOST"`, `live_eval_held=True`): the evaluator is never invoked, so no live-based transition occurs (fail-closed, REQ-40 s2). A fresh stream releases the hold. `status()` gains `stream_state`/`live_eval_held`.
- **5.3 (REQ-40)**: new `sdk/quantlab/guardian/live.py` — pure `max_drawdown(points)` (peak-to-trough fraction) and `evaluate_live(points, *, drawdown_threshold=0.10)` → `LiveEvaluation`. Drawdown strictly above 10% → `PortfolioState.DEFENSIVE`, `transitioned=True`, and a `FeedbackRecord` (degradation + drawdown) for the REQ-34 feedback loop; empty stream → `held=True` with `STREAM_LOST` reason, `state=None`, no transition. Integration test wires daemon feed → `evaluate_live` → DEFENSIVE + feedback (REQ-40 s1 through the REQ-41 feed).
- **5.4 (REQ-33 + REQ-38 s3)**: new `sdk/quantlab/phase4/campaign_archive.py` — `account_stats(points, start_equity)` (equity/drawdown/P&L over the demo window, reuses `guardian.live.max_drawdown`), `build_plan(...)` (DEGRADING Guardian state OR feedback-driven degradation → `REPLACE` with candidates from the campaign portfolio excluding the deployed strategy; else `MAINTAIN`), `ArchiveBundle` (plan + stats + feedback + artifacts, JSON-safe `to_dict()` for audit), and `ArchivePhase.run(campaign_id, ...)` which composes the plan, then consumes the **HUMAN_APPROVE_ARCHIVE** gate (PR-4 registration reused, NOT re-registered). Only explicit `decision.action == APPROVE` finalizes (`status="ARCHIVED"`); REJECT and the no-callback/HOLD fallback (`action=FALLBACK`) return `status="DENIED"` → campaign back to maintenance, `artifacts=[]`, `archived_at=None` (REQ-38 s3). The gate is consumed on explicit `action == APPROVE`, never `is_approved()` (PR-4 finding applied and covered by `test_fallback_hold_is_not_approval`).

### Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `pytest tests/campaign_archive/ tests/guardian/ -q` → **47 passed** (0.72s). Per unit: feedback (5.1) 8 passed; stream_live feed+hold (5.2) 7 passed; live eval (5.3) 9 passed; archive phase (5.4) 11 passed |
| Runtime harness command/scenario and exact result | Real composition: `AutonomousMonitorDaemon.stream_live` → injected `evaluate_live` evaluator over a 3-point feed `[100, 100, 88]` → `LiveEvaluation(state=DEFENSIVE, transitioned=True, feedback.campaign_id="camp-wired")`; STREAM_LOST feed (ConnectionError, `max_retries=0`) → `stream_state="STREAM_LOST"`, `live_eval_held=True`, evaluator never called, `STREAM_LOST` alert persisted. Archive: `ArchivePhase.run` with real `HumanGateOrchestrator` default (no callback) → HOLD fallback → `status="DENIED"` (never auto-archives). Regression: `tests/gates/ tests/demo_deploy/ tests/agents/test_autonomous_monitor.py tests/substrate/ sdk/tests/test_guardian/ sdk/tests/gates/ sdk/tests/test_readers.py` → 194 passed; `tests/phase4/ sdk/tests/phase4/` → 669 passed, 2 pre-existing failures (see Notes) |
| Rollback boundary | Feedback writes are additive records (new module `guardian/feedback.py`; no destructive change). Live feed/eval is opt-in: `AutonomousMonitorDaemon` defaults keep `_live_evaluator=None` (existing daemon loop behavior byte-identical — 44 daemon tests still pass) and STREAM_LOST hold only activates on max-retries exhaustion. DEGRADING→replacement is a plan recommendation, not an action. Reverting `1bf1b72..0ee36e0` removes all PR-5 code without touching PR-1..4 |

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 5.1 | `tests/guardian/test_feedback.py` | Unit | ✅ 97 passed (guardian+gates+demo_deploy+sdk guardian) | ✅ Written (ImportError: cannot import 'feedback') | ✅ Passed | ✅ 8 cases (2 signal sets, degradation True/False, next-cycle inputs, gates untouched ×3) | ✅ Clean |
| 5.2 | `tests/guardian/test_stream_live.py` | Unit | ✅ 97 passed | ✅ Written (6 AttributeErrors: missing methods) | ✅ Passed | ✅ 7 cases (feed delivery, heartbeat, hold release, hold guard, reconnect exhaustion, wired eval) | ✅ Clean |
| 5.3 | `tests/guardian/test_live_eval.py` | Unit | ✅ 97 passed | ✅ Written (ModuleNotFoundError: guardian.live) | ✅ Passed | ✅ 9 cases (drawdown math ×4, threshold > / = / <, empty hold, feedback loop) | ✅ Clean |
| 5.4 | `tests/campaign_archive/test_campaign_archive.py` | Unit | ✅ 97 passed | ✅ Written (ModuleNotFoundError: phase4.campaign_archive) | ✅ Passed | ✅ 11 cases (stats ×3, plan ×3, gate approve/deny/no-callback/fallback, to_dict audit) | ✅ Clean |

### Deviations from Design

- **`guardian/live.py` added as its own module** (design lists only `guardian/feedback.py` and `campaign_archive.py` in Slice 5): the live-eval pure function (REQ-40) needs a home; putting it in `feedback.py` would mix evaluation with records. Matches the module-per-concern convention of the guardian package.
- **`campaign_archive.py` placed in `sdk/quantlab/phase4/`** (design says "campaign_archive.py (new)" without a package; Slice 4's `demo_deploy.py` established `phase4/` for phase modules, and `ArchivePhase` is the archive-phase stage). It imports `quantlab.guardian.live/models/feedback` + `quantlab.gates.models` at module level — verified no import cycle (guardian/gates/readers do not import phase4/agents).
- **Equity-only live feed**: REQ-40 mentions equity, positions, and costs, but the existing feed model (`EquityPoint`) and `ResultReader.stream_live` carry equity only. Positions/costs remain future extensions (FeedbackSignals.cost field exists and defaults to 0.0); the drawdown logic is fully implemented on the equity curve.
- **`evaluate_live` drives its own portfolio-level state** rather than mutating `MetaGuardianOrchestrator.state`: the orchestrator's hysteresis state machine (backtest-derived) is left untouched; live evaluation is a separate pure signal that transitions to DEFENSIVE and records feedback. The 14-phase flow and human gates are unaffected (REQ-37 invariant intact).

### Notes / Gotchas

- **PR-4 finding applied**: `ArchivePhase` gates on `decision.action != GateDecisionAction.APPROVE` — never `is_approved()` (returns True for FALLBACK). Covered by `test_fallback_hold_is_not_approval` (HOLD fallback action `FALLBACK` → `status="DENIED"`).
- **STREAM_LOST hold is per-stream**: a fresh `stream_live()` releases the hold (evaluation resumes); the hold protects the *live* evaluation window only.
- Pre-existing failures NOT caused by PR-5 (confirmed at base `09ac069` and re-confirmed with the new module removed): `tests/phase4/test_project_builder.py::TestBuildConfigMapCoverage::{test_all_buildconfig_fields_in_map, test_map_entries_have_valid_format_types}` — untouched.
- Additional pre-existing failure (confirmed failing on the parent branch without PR-5 code): `tests/robustness/test_autonomous_monitor_health.py::TestAutonomousMonitorStoreHealthIntegration::test_circuit_breaker_used_for_store_writes` — `AttributeError: 'KnowledgeStore' object has no attribute '_circuit_breaker'` (test expects an internal attribute the store never had). Untouched per strict-TDD rule; flag for a future batch.

## PR-6: Mobile + Orchestration (REQ-35..36, 01M, 37, 43..44) — COMPLETE

- [x] 6.1 MobilePushNotifier + severity routing; RED: push fail logged, others deliver (REQ-35)
- [x] 6.2 24-7 daemon escalation on transitions + expiry, ack (REQ-36)
- [x] 6.3 `campaign.md` PHASES + flow assert; RED: dropped phase aborts (REQ-37)
- [x] 6.4 stages portfolio/compile/deploy/demo/archive; chained retest/optimize (REQ-43..44)

Commits: `49f6123`, `0739745`, `bbc86d6`, `31d66bd` on `feat/mobile-orchestration`.

### What

- **6.1 (REQ-35)**: `sdk/quantlab/gates/notifiers.py` — `MobilePushNotifier(endpoint, *, transport=None, headers=None, timeout=10.0)` POSTs JSON to the push endpoint with transport injection; failures are logged (not raised) at WARNING severity so a dead push endpoint never blocks monitoring. `sdk/quantlab/agents/autonomous_monitor.py`: `_SEVERITY_ROUTES["CRITICAL"]` now includes `"push"` (CRITICAL always pushes); `NotifierDispatcher` gains `push_on_warning` (default `False` — WARNING push is opt-in via `PUSH_ON_WARNING` env or `MonitorConfig.push_on_warning`); `_build_notifiers` maps `"push"` → `MobilePushNotifier`, `"console"` → `ConsoleNotifier`. RED: 11 tests in `tests/gates/test_notifiers.py` (push fail logged + others still deliver, CRITICAL routes to push, opt-in WARNING behavior).
- **6.2 (REQ-36)**: new `sdk/quantlab/agents/ops_surface.py` — `OpsSurface` 24-7 operations surface with `EscalationAlert` (campaign/severity/state/message/acked/timestamps), one-directional worsening escalation (`_ESCALATION_RANK`: NORMAL < VIGILANCE < DEFENSIVE < QUARANTINE), `demo_window_expired()`, `ack()`, `pending_alerts()`/`flush_pending()`, `on_transition` hook pushing `GUARDIAN_ESCALATION`; `demo_window_expired()` pushes `DEMO_WINDOW_EXPIRED`. `AutonomousMonitorDaemon` gains `ops_surface` (property + `set_ops_surface`) and `_deliver_live_point` escalates whenever `result.transitioned` and an ops surface is wired. RED: 13 tests in `tests/agents/test_ops_surface.py` (local `_make_mock_notifier` — `tests/agents` has no `__init__.py`).
- **6.3 (REQ-37)**: new `sdk/quantlab/campaign/flow.py` — `PHASES` tuple of the 14 phases (research → live-ops), `FlowIntegrityError`, and `assert_flow(phases)` fail-closed (wrong length/order/membership raises). `AI/opencode/agents/campaign.md` rewritten to the 14-phase lifecycle with an explicit "PHASES constant" block kept byte-identical to `quantlab.campaign.flow.PHASES` and instructions to run the flow-integrity assert. RED: 11 tests in `tests/campaign/test_flow_integrity.py` incl. doc-sync via `ast` (extracts the literal from campaign.md and compares to the code tuple).
- **6.4 (REQ-43..44, REQ-01 phases 9-13)**: five concrete stages in `sdk/quantlab/pipeline/stages/` — `portfolio_stage.py` (`PortfolioStage`: consumes `selected_strategies`, publishes normalized `portfolio_result` via injectable `optimize_fn`, default pure `PortfolioComposer.normalize_weights`), `compile_stage.py` (`CompileStage`: routes each strategy through the compiler pipeline, injectable `compile_fn`), `deploy_stage.py` (`DeployStage`: `DeploymentAgent.package_jfx`, dry-run default), `demo_stage.py` (`DemoStage`: `DemoDeployer.deploy` honouring the 14-day window, `BLOCKED_EXPIRED` → fail-closed with `pending_gate=HUMAN_APPROVE_DEMO`, `ctx.config.demo_now` pins the clock), `archive_stage.py` (`ArchiveStage`: `ArchivePhase.run(campaign_id)` → `archive_bundle`). `renderers.py` `_crosschecks_section` now emits `<MonteCarlo enabled simulations/>` (Retest, REQ-43) and `<Parameters enabled .../>` (Optimize, REQ-44) inside CrossChecks — disabled elements stay present so a harness change can never silently drop a cross-check. `StageRegistry` maps `portfolio`/`deploy` to the concrete orchestrated stages (superseding the legacy `PortfolioAgent`/`DeployAgentStage` wrappers) and adds `compile`/`demo`/`archive`. Chained `Filtering → Retest → Optimize` in ONE custom-project load (`Tasks/Task` order, CrossChecks carry WF+MC+params); standalone `Retester.run`/`Optimizer.run` signatures unchanged.

### Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `pytest tests/pipeline/stages/ -q` → **18 passed** (0.83s): orchestration contracts+behaviors (5 stages + full chain, 10 tests) and chained retest/optimize (8 tests). Per unit: 6.1 `pytest tests/gates/test_notifiers.py -q` → 11 passed; 6.2 `pytest tests/agents/test_ops_surface.py -q` → 13 passed; 6.3 `pytest tests/campaign/test_flow_integrity.py -q` → 11 passed |
| Runtime harness command/scenario and exact result | Chained one-load: `generate_cfx_archive` for Filtering→Retest→Optimize → `config.xml` contains `Tasks/Task` order Filtering, Retest, Optimize; `Retest-Task1.xml` `CrossChecks` carries `WalkForward enabled="true" cycles="12"` + `MonteCarlo enabled="true" simulations="500"`; `Optimize-Task1.xml` carries `Parameters enabled="true" maxOptimizations="100"`; MC/params absent → disabled elements emitted. Full chain: `Pipeline` of PortfolioStage→CompileStage→DeployStage→DemoStage→ArchiveStage with injectable fakes produces artifact keys in order `[selected_strategies, portfolio_result, compiled_strategies, deployment_result, demo_result, archive_bundle]`; expired demo window → `BLOCKED_EXPIRED`. Regression: `tests/pipeline/ tests/customproject/ tests/agents/ tests/gates/ tests/campaign/ tests/phase5/` → **314 passed, 6 skipped** (6.59s) |
| Rollback boundary | All PR-6 additions are additive: new modules (`ops_surface.py`, `campaign/flow.py`, the five stage modules) + new tests; the only modifications to existing files are `notifiers.py` (new class + route additions), `autonomous_monitor.py` (new params/properties, defaults preserve legacy behavior), `renderers.py` (CrossChecks gains MonteCarlo/Parameters — existing WalkForward assertions unchanged), `registry.py` (portfolio/deploy remap + compile/demo/archive keys). Reverting `49f6123..31d66bd` removes PR-6 without touching PR-1..5. Full suite: 19 failed + 11 errors vs **20 failed + 11 errors on pristine HEAD** — same pre-existing, order-dependent families (orchestrator interference, robustness knowledge-store, cfx reader, project_builder, prompt); no regression attributable to PR-6 |

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 6.1 | `tests/gates/test_notifiers.py` | Unit | ✅ 62 passed (gates + autonomous_monitor) | ✅ Written (AttributeError: MobilePushNotifier) | ✅ Passed | ✅ 11 cases (push POST payload, failure logged not raised, CRITICAL route, WARNING opt-in on/off) | ✅ Clean |
| 6.2 | `tests/agents/test_ops_surface.py` | Unit | ✅ 62 passed | ✅ Written (ModuleNotFoundError: agents.ops_surface) | ✅ Passed | ✅ 13 cases (rank ordering, worsening-only escalation, ack, expiry push, pending/flush, daemon wiring) | ✅ Clean |
| 6.3 | `tests/campaign/test_flow_integrity.py` | Unit | ✅ 89 passed (ops_surface + guardian + daemon) | ✅ Written (ModuleNotFoundError: campaign.flow) | ✅ Passed | ✅ 11 cases (14 phases exact, order, doc-sync ast, dropped phase aborts) | ✅ Clean |
| 6.4 | `tests/pipeline/stages/test_orchestration_stages.py` + `test_chained_retest_optimize.py` | Unit | ✅ 177 passed (pipeline/customproject/agents/gates/campaign) | ✅ Written (17 failed: ModuleNotFoundError ×5 stage modules + missing MonteCarlo/Parameters) | ✅ Passed | ✅ 18 cases (5 stage contracts, behaviors, full chain order, one-load chain, MC/params on/off, standalone signatures) | ✅ Clean |

### Deviations from Design

- **`PortfolioStage` does NOT publish `portfolio_cfx` into `ctx.artifacts`** (the chain test asserts exact artifact keys `[selected_strategies, portfolio_result, compiled_strategies, deployment_result, demo_result, archive_bundle]`; `portfolio_cfx` stays in the stage's return dict — compilation publishes .jfx artifacts later). Abstract anchor's `provides` list retained on the concrete class for contract compatibility.
- **Registry remap**: `portfolio`/`deploy` now map to the concrete orchestrated `PortfolioStage`/`DeployStage` (REQ-01 phases 9/11) instead of the legacy `PortfolioAgent`/`DeployAgentStage` wrappers. This follows the PR-3 precedent (concrete orchestrated stages registered by name) and the legacy wrapper classes/imports were removed (dead code after the remap).
- **`test_pipeline_registry.py::test_registry_initializes_with_all_stages` was stale** — it had failed on this branch since PR-3 (its exact-set assertion never included `analysis`/`config_review`/`retester`/`optimizer`/`dispatch`). Updated the expected set with the PR-3 keys + the five PR-6 keys; test now passes. Verified pre-existing on pristine HEAD.

### Notes / Gotchas

- **Strict-TDD for 6.4**: the one-load chain test (`test_chained_retest_optimize.py`) was written first and failed with `ModuleNotFoundError` for the five stage modules; the missing `<MonteCarlo>`/`<Parameters>` elements were the second RED failure. All GREEN after adding the modules and the renderer sections.
- **Annotation forms in signature tests**: `Retester.run`/`Optimizer.run` annotate `config` with a forward-reference string (e.g. `"RetesterConfig"`), not a class — the signature tests resolve both forms via `_annotation_name()`.
- **Pre-existing failures confirmed NOT caused by PR-6** (full suite on pristine HEAD: 20 failed + 11 errors; with PR-6: 19 failed + 11 errors): orchestrator cross-file interference, robustness knowledge-store circuit-breaker, cfx multi-file detection, project-builder map coverage, campaign-agent prompt. None import PR-6 modules; all fail identically without PR-6 code.
- **Stash gotcha**: `git stash push -u` + full-suite run regenerates `knowledge/index.yaml` and `knowledge/timeseries/monitor.db`, which then collide on `git stash pop` (untracked conflict). Worked around by verifying all tracked + new files restored, then dropping the stale stash. Avoid stashing `knowledge/` when running the full suite.




