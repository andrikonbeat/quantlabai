# Design: Full Campaign Flow — Complete QuantLab Lifecycle

Implements REQ-22..44 + modified REQ-01/37..44 (spec authoritative). Binding constraint: all 14 flow phases + Guardian live flow remain, in order, each human-gated; simplification applies ONLY to code/infra. Slices land as chained PRs (auto-chain stacked-to-main, 400-line budget).

## Technical Approach

Extend the orchestrated harness in place over one unified execution substrate, delivered as 6 slices. Slice 1 (CustomProject DSL + multi-task CFX generator) ships first — it is the highest-unknown dependency (SQX schema acceptance) and unlocks retest/optimize chaining in one project load (REQ-27). Every slice is flag-gated; legacy paths stay operational until parity (REQ-28). Verified golden format from `assets/SQX_144_2953_linux_20260601/user/projects/{e2e-test,sqx_*}/project.cfx`:

```xml
<Project name="e2e-test" version="144.2953">
  <Tasks><Task type="Build" name="Build" showSettingsOverview="false" sampleName="Custom" active="true" taskXMLFile="Build-Task1.xml"/></Tasks>
  <Databanks><Databank name="Results" view="Default - Main data" syncType="Auto-sync never"/></Databanks>
</Project>
```

## Architecture Decisions

| # | Decision | Options | Tradeoff | Choice |
|---|----------|---------|----------|--------|
| AD-1 | CFX mapping | Extend existing `cfx/` models vs new module | Existing `CfxProject.tasks: dict` already multi-task, preserves insertion order; writer omits `<Databanks>` + per-task `type` | Extend `cfx/models.py` + `writer.py`; DSL layer in new `customproject/` package |
| AD-2 | Task rendering | Raw-XML strings vs typed sections | Typed sections match existing translator; catalog tasks need per-type sections | Per-task renderers reusing existing complex-section models + `unknown_sections` for catalog tasks |
| AD-3 | Single-task compat | Rewrite vs freeze `_write_config_archive` | Byte-identical output required by consumers (REQ-23) | Freeze `_write_config_archive`; multi-task only via `_write_project_archive` |
| AD-4 | Substrate | One `Executor` param'd by phase vs N runners | 3 overlapping paths today (CommandDispatcher, `cli_wrapper._dispatch_real`, CampaignOrchestrator); one runner = shared checkpoint/poll/export | New `substrate/` package; legacy paths flag-gated until parity (REQ-28) |
| AD-5 | JDK | Bundle vs external | `j64/` is JRE (no javac); bundling a JDK is heavy | External JDK via `QUANTLAB_JDK_HOME`, fail-closed if absent (REQ-29) |
| AD-6 | Gates | Reuse pattern vs new mechanism | 3 new gates mirror `HUMAN_APPROVE_CONFIG` fail-closed HOLD | Add `HUMAN_APPROVE_DEMO`/`HUMAN_APPROVE_ARCHIVE` to `DEFAULT_GATE_POLICIES` (`HUMAN_APPROVE_DEPLOY` already exists) |
| AD-7 | Golden validation | Compare bytes vs structural + real sqcli | Byte-compare brittle (names differ); structural + `sqcli -h` probe + real loadconfig is authoritative (REQ-24) | Structural validator + sqcli acceptance probe; deviating element named in `ValidationError` |

## Slice 1 — CustomProject DSL + Multi-Task CFX Generator (REQ-22..25, DEPTH)

### Module design (`sdk/quantlab/customproject/`, new)

```
customproject/
├── models.py      # DSL: CustomProject, CustomProjectTask, GoToTask, DatabankSpec, Filters
├── catalog.py     # 21-task catalog: type → renderer, required params, default taskXMLFile
├── renderers.py   # per-task renderer → BuildTask (typed sections + unknown_sections)
├── generator.py   # generate_cfx_archive(project) → CfxArchive(CfxProject) + task_files
└── validator.py   # golden structural validation + sqcli -h probe (REQ-24)
```

### DSL→CFX mapping

| DSL field | CFX element |
|-----------|-------------|
| ordered `tasks: list[CustomProjectTask]` | `<Tasks>` child order (dict preserves insertion order) |
| `task.type` | `Task@type` + task XML filename (`{Type}-{n}.xml`) |
| `task.name`, `task.active` | `Task@name`, `Task@active` |
| `task.taskXMLFile` (optional override) | `Task@taskXMLFile` + packaged file name |
| `source_databank`/`target_databank` | per-task `<Data>`/`<Databanks>` sections; registry `<Databanks><Databank name= view= syncType= position=>` |
| `filters` (Filtering task) | Filtering task XML `<Conditions>` + source/target databank attrs |
| `GoToTask.condition` | GoToTask task XML target + condition (loop `retest_failed` → Filtering) |
| `schema_version "144.2953"` | `Project@version` + `Task@version` |

Extend `CfxProject` (cfx/models.py): add `databanks: list[DatabankSpec]` and per-task `task_type`; keep `tasks: dict[str, BuildTask]` as the ordered seed. Extend `writer._write_project_archive` to emit `<Databanks>` + `showSettingsOverview="false"`/`sampleName="Custom"` + real `type` (currently hardcoded `"Build"`).

Walk-Forward renders inside Retest/Optimize `CrossChecks` (no standalone task, REQ-25). Unknown task types raise `TaskNotSupportedError` naming the type. `generate_cfx_archive(project: CustomProject)` is the single entry point.

### Data flow

```
CustomProject DSL → renderers → CfxProject(tasks, databanks)
  → CfxWriter._write_project_archive → .cfx ZIP (config.xml + per-task XML)
  → validator.validate (goldens: user/projects/*/project.cfx; sqcli -h probe)
  → sqcli -project action=loadconfig (acceptance) → dispatch
  ✗ deviation → ValidationError naming element → no dispatch (REQ-24 fail-closed)
```

### Testing & rollback

Unit: order round-trip, GoToTask loop, per-task databank isolation (REQ-22 scenarios); single-task byte-identity vs current generator (REQ-23). Integration: ZIP shape, taskXMLFile routing, `<Databanks>` completeness. E2E (real, gated): loadconfig acceptance on 4-task archive; deviation fails closed. Rollback: `QUANTLAB_CUSTOM_PROJECT=0` → old single-task generator path (project_builder) untouched.

## Slice 2 — Unified Execution Substrate (REQ-26..28, REQ-42)

### Module design (`sdk/quantlab/substrate/`, new)

```
substrate/
├── executor.py     # Executor.execute(phase: Phase, cfg: PhaseConfig) → PhaseResult
├── lifecycle.py    # daemon lifecycle state machine
├── events.py       # WatcherEvent flow (CampaignMonitor as event-detection, REQ-42)
├── poller.py       # status polling (interval/timeout from phase config)
└── exporter.py     # per-phase export (strategies.csv etc.)
```

`Phase = build | retest | optimize | portfolio`. Reuses `SQXDaemonManager`, `AsyncSQXClient`, `CheckpointManager` (phase4), `CampaignMonitor` signals (status text, `strategies.csv`). Flag `QUANTLAB_UNIFIED_SUBSTRATE=1`; legacy CommandDispatcher/`_dispatch_real`/CampaignOrchestrator stay behind flag until output parity proven (REQ-28). `SQX_FORCE_MOCK=1` honored for the 2790-test suite. Human gate between chained tasks holds execution until resolved (REQ-27).

### State machine

```
IDLE → LOADED → STARTED → RUNNING ──→ COMPLETED → EXPORTED
          │         │         │
          └─────────┴─────────┴→ checkpoint N (resume at N+1, REQ-26)
          │   stall/error → FAILED (WatcherEvent, halt for human)
```

Testing: mock parity via `SQX_FORCE_MOCK=1`; checkpoint resume (interrupt at N, re-run → N+1); legacy path byte-identical. Rollback: flag off.

## Slice 3 — Compiler Pipeline (REQ-29..30, REQ-39)

```
JForexDeployer.export_strategy (.java) → compiler/CompilerPipeline.compile(src)
  → javac (QUANTLAB_JDK_HOME; missing → CompilerConfigError, no partial .jfx)
  → .jfx package → jfx/artifact
  ✗ errors → fixloop.fix (LLM-guided, max_fix_iterations, per-iteration log)
    → recompile → bound exhausted → CompileError + full error history, not deployed
```

New `sdk/quantlab/compiler/`: `compiler.py`, `fixloop.py`, `jfx.py`. `jforex_deploy.py` gains a `.jfx` routing stage (REQ-39). Testing: happy compile, missing-JDK fail-closed, self-correcting fix loop, bound halt. Rollback: deploy keeps `.java`-only path when `QUANTLAB_COMPILER=0`.

## Slice 4 — Demo Deploy (REQ-31..32, REQ-38)

- `demo_deploy.py` (new): 14-business-day window — expiry check, renewal reminder scheduling, `HUMAN_APPROVE_DEMO` gate blocks renewal after expiry (fail-closed).
- `deployment_agent.py` (modify): replace placeholder JAR (`PK\x05\x06` stub) with real packaging — embed `.jfx` in deployable JAR, apply JCloud config (account, server, symbols); `dry_run=True` → mock package, zero network (REQ-32).
- Gates: add `HUMAN_APPROVE_DEMO` + `HUMAN_APPROVE_ARCHIVE` to `DEFAULT_GATE_POLICIES`/`HUMAN_GATE_IDS` with `FallbackPolicy.HOLD` (REQ-38); `HUMAN_APPROVE_DEPLOY` already exists (models.py:142). All resolvable via decision-file → `question` tool, stdin fallback.

Testing: dry-run mock package (no network), real packaging with .jfx embedded, window-expiry block. Rollback: `dry_run` default on; live path disabled until gates verified.

## Slice 5 — Archive + Guardian Feedback (REQ-33, REQ-34, REQ-40..41)

- `campaign_archive.py` (new): maintenance/replacement plan (portfolio candidates + Guardian degradation), account stats (equity/drawdown/P&L over demo window), artifact bundle; `HUMAN_APPROVE_ARCHIVE` holds plan for human confirmation (denial → back to maintenance).
- `guardian/feedback.py` (new): `record(campaign_id, signals)` — degradation/drawdown/regime/cost → feedback record attached at archive; feeds next-cycle generation inputs (REQ-34). Never bypasses gates.
- `agents/autonomous_monitor.py` (modify): add `stream_live(campaign_id)` → equity/positions to MetaGuardian (REQ-41); live drawdown >10% → DEFENSIVE transition (REQ-40); stream lost → STREAM_LOST hold, no live transition (fail-closed).

Data flow: `daemon stream_live → MetaGuardian eval → FeedbackRecord → archive bundle → next-cycle input`.

Testing: degradation triggers replacement recommendation; feedback record attached; STREAM_LOST fail-closed; gates hold. Rollback: feedback writes are additive records (no destructive change).

## Slice 6 — Mobile Notifications + Orchestration (REQ-35..36, REQ-01 M, REQ-37, REQ-43..44)

- `gates/notifiers.py` (modify): `MobilePushNotifier` registered in `NotifierDispatcher` (autonomous_monitor) alongside console/webhook/email/slack; severity routing CRITICAL→push, WARNING→push configurable; push failure logged WARNING, remaining channels deliver (REQ-35).
- 24-7 daemon: escalation on Guardian transitions (NORMAL→VIGILANCE→DEFENSIVE→QUARANTINE) + demo window expiry, ack via ops surface (REQ-36).
- `campaign.md` (modify): extend to 14 phases (research→…→archive→live-ops); add `PHASES` constant + flow-integrity assert at campaign start and after harness change (REQ-37) — dropped/reordered phase aborts before execution.
- `pipeline/stages/`: add portfolio/compile/deploy/demo/archive stages; Retester/Optimizer invocable as chained tasks (REQ-43..44) while `Retester.run(config, strategy_id, output_dir)` / `Optimizer.run(config)` standalone signatures stay unchanged.

Testing: CRITICAL reaches all channels; push failure degrades gracefully; overnight DEFENSIVE escalates + ack; 14-phase assert passes/aborts. Rollback: flag-gated stages + PHASES assert.

## Interfaces / Contracts

```python
# slice 1
generate_cfx_archive(project: CustomProject) -> CfxArchive      # REQ-23
validate_golden(archive: CfxArchive, sqx_root: Path) -> None     # raises ValidationError (REQ-24)

# slice 2
Executor.execute(phase: Phase, config: PhaseConfig) -> PhaseResult  # REQ-26

# slice 3
CompilerPipeline.compile(src: Path) -> JfxArtifact               # REQ-29

# slice 4-6
DemoDeployer.deploy(artifact: JfxArtifact, account: JCloudConfig) -> DeploymentResult
ArchivePhase.run(campaign: CampaignId) -> ArchiveBundle
guardian.feedback.record(campaign_id: str, signals: FeedbackSignals) -> FeedbackRecord
```

## Testing Strategy (2790-suite + new)

| Layer | What | Approach |
|-------|------|----------|
| Unit | DSL serialization, catalog coverage, gate policies, state machines | pytest per module, RED-first per task |
| Integration | ZIP shape vs goldens, substrate phases, compile loop, push routing | mock server (`SQX_FORCE_MOCK=1`) parity + golden comparison |
| E2E (gated) | real sqcli loadconfig acceptance, demo dry-run, 14-phase assert | real path behind flags, goldens from `assets/` samples |

Existing 2790 tests MUST keep passing on legacy paths (REQ-28) — mock parity is the guard.

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|----------|---------------|-----------------|-------------------|
| Documentation-like paths | N/A — no executable Markdown/scripts | — | — |
| Git repo selection | N/A — SDK code runs no git commands | — | — |
| Commit state | N/A — no git automation in scope | — | — |
| Push state | N/A — no git automation in scope | — | — |
| PR commands | N/A — PR automation is repo-level, not SDK code | — | — |
| **Subprocess: sqcli invocation** | **Applicable** — substrate spawns `sqcli` (`-project action=loadconfig/start/stop/status`, `-h` probe) | Resolve via `assets/.../sqcli` or `SQCLI_PATH` env; validate existence + `-h` exit before dispatch; mock server under `SQX_FORCE_MOCK` | 1 per selector: relative path, missing binary, env fallback, mock override |
| **Subprocess: javac (external JDK)** | **Applicable** — compiler spawns javac from `QUANTLAB_JDK_HOME` | Resolve `{JDK}/bin/javac`; fail-closed `CompilerConfigError` if absent; never fall back to `j64/` (JRE) | 1: missing JDK no partial .jfx; 1: non-executable javac |
| Executable-file classification | N/A — only `sqcli`/`javac` resolved as executables, covered above | — | — |

Safe behavior: each subprocess failure raises a typed error (ValidationError/CompilerConfigError/CompileError) and halts the phase; no silent fallback. Failure behavior: fail-closed per REQ-24/29/30. These rows propagate to tasks and RED tests unchanged.

## Migration / Rollout

Slices are flag-gated additive changes; no data migration. Golden sample projects archived at `assets/SQX_144_2953_linux_20260601/user/projects/` serve as validation baselines before generator changes. External JDK is a new prerequisite (env `QUANTLAB_JDK_HOME`), documented at apply time.

## PR Slice Boundaries (auto-chain, stacked-to-main, 400-line budget)

| PR | Slice | Reqs | Flag | Risk |
|----|-------|------|------|------|
| PR-1 | custom-project-generator | REQ-22..25 | `QUANTLAB_CUSTOM_PROJECT` | High (CFX dialect) — first, standalone |
| PR-2 | execution-substrate | REQ-26..28, 42 | `QUANTLAB_UNIFIED_SUBSTRATE` | Med (2790 parity) |
| PR-3 | compiler-pipeline + jforex-deploy | REQ-29..30, 39 | `QUANTLAB_COMPILER` | Med |
| PR-4 | demo-deploy + human gates | REQ-31..32, 38 | `dry_run` default | Med |
| PR-5 | archive + guardian-feedback | REQ-33..34, 40..41 | gates | Low |
| PR-6 | mobile-notifications + orchestration | REQ-35..36, 01M, 37, 43..44 | stages | Low |

Each PR targets the previous PR branch (stacked), final merges to main. Forecast: `Decision needed before apply: Yes`, `Chained PRs recommended: Yes`, `400-line budget risk: High` (6 slices likely exceed 400 lines total; per-PR kept under budget).

## Open Questions

- [ ] CFX writer's simplified `<Settings>` dialect vs SQX-native Param className — resolve empirically against sample tasks during slice 1 (RawXmlSection is the workaround).
- [ ] `.jfx` packaging layout: JAR-with-classes vs SQX-native layout — verify against JForex 4 requirements before slice 3 tasks.
- [ ] Live account feed transport for Dukascopy demo (JCloud API vs manual export) — confirm at slice 5 design review.
