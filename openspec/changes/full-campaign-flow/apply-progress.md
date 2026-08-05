# Apply Progress: Full Campaign Flow

Cumulative across batches. Latest batch: PR-4 Demo Deploy + Gates (REQ-31..32, 38).

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

- [ ] PR-5: Archive + Feedback (REQ-33..34, 40..41) — tasks 5.1-5.4
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

