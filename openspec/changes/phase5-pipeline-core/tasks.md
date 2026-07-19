# Tasks: Phase 5 — Pipeline Core & Campaign Orchestrator Refactor

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 2800–3500 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (pipeline core) → PR 2 (SQX stages) → PR 3 (orchestrator refactor) → PR 4 (CLI + tests) |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Pipeline core module (base, models, runner, stages) | PR 1 | Base branch = feature/phase5-pipeline-core; zero SQX imports |
| 2 | SQX-specific stages in phase4/stages/ | PR 2 | Depends on PR 1; internal to phase4 |
| 3 | CampaignOrchestrator refactor (internal delegation) | PR 3 | Depends on PR 2; public API unchanged |
| 4 | CLI pipeline subcommand + DaemonContext + tests | PR 4 | Depends on PR 1; integration tests |

---

## Phase 1: Pipeline Core Module (Foundation)

- [x] 1.1 Create `sdk/quantlab/pipeline/__init__.py` with public exports
- [x] 1.2 Create `sdk/quantlab/pipeline/base.py`: `Stage` ABC (name, requires, provides, execute), `Pipeline` dataclass with `.then()`, `PipelineContext` dataclass
- [x] 1.3 Create `sdk/quantlab/pipeline/models.py`: `StageStatus` enum, `StageResult`, `PipelineResult` dataclasses
- [x] 1.4 Create `sdk/quantlab/pipeline/runner.py`: `PipelineRunner.run()` sequential execution, per-stage timing, stop-on-first-error, SKIPPED remaining
- [x] 1.5 Create `sdk/quantlab/pipeline/stages.py`: 12 abstract base stages (ValidateStage, TranslateStage, DaemonStartStage, LoadConfigStage, RunCampaignStage, PollCampaignStage, CampaignStage, ExportStage, ReadStage, ComputeStatsStage, KnowledgeStoreStage, ReportStage) with requires/provides contracts
- [x] 1.6 Verify `pipeline/` has zero imports from `quantlab.phase4` or SQX domain (note: registry.py has deferred import inside StageRegistry.__init__ — forward reference for Phase 2)

## Phase 2: SQX-Specific Stage Implementations

> **Note**: All 13 SQX stage classes are implemented in a single `__init__.py` (not per-file).
> Extra stages `SQXLoadConfigStage`, `SQXRunCampaignStage`, `SQXPollCampaignStage` were
> split from `SQXCampaignStage` for finer granularity.

- [x] 2.1 Create `sdk/quantlab/phase4/stages/__init__.py` — contains all 13 SQX stage classes
- [x] 2.2 All stages in `__init__.py`: `SQXValidateStage` extends `ValidateStage`, license check
- [x] 2.3 `SQXTranslateStage` extends `TranslateStage`, DSL→CFX
- [x] 2.4 `SQXDaemonStartStage` extends `DaemonStartStage`, starts daemon
- [x] 2.5 `SQXCampaignStage` extends `CampaignStage`, load config, start project, poll
- [x] 2.6 `SQXExportStage` extends `ExportStage`, export results/databanks
- [x] 2.7 `SQXReadStage` extends `ReadStage`, parse CSV/XLSX
- [x] 2.8 `SQXComputeStatsStage` extends `ComputeStatsStage`, StatisticsEngine
- [x] 2.9 `SQXKnowledgeStoreStage` extends `KnowledgeStoreStage`, KnowledgeStore
- [x] 2.10 `SQXReportStage` extends `ReportStage`, generate report

## Phase 3: CampaignOrchestrator Refactor (Internal Delegation)

- [ ] 3.1 Modify `sdk/quantlab/phase4/campaign_orchestrator.py`: `run()` builds `Pipeline` from 9 SQX stages, delegates to `PipelineRunner`, maps `PipelineResult` → `CampaignResult`
- [ ] 3.2 Preserve all public exports: `CampaignOrchestrator`, `CampaignConfig`, `CampaignResult`, `CampaignPhase`, `PhaseStatus`, `PhaseResult`, `run_campaign` — signatures unchanged
- [ ] 3.3 Maintain progress callbacks at each phase transition with same `(phase, status, detail)` signature
- [ ] 3.4 Preserve dry-run path: bypass pipeline, simulate phases identically to pre-refactor
- [ ] 3.5 Update `sdk/quantlab/phase4/__init__.py` re-exports if needed (no public API change)

## Phase 4: Exception Hierarchy & DaemonContext

- [ ] 4.1 Modify `sdk/quantlab/tools/exceptions.py`: add `PipelineError(QuantLabError)`, `StageExecutionError(PipelineError)` with `stage_name` + `original_error`, `PipelineConfigError(PipelineError)`
- [ ] 4.2 Create `sdk/quantlab/cli/daemon.py`: `DaemonContext` async context manager wrapping `SQXDaemonManager` start/stop/health
- [ ] 4.3 Verify `DaemonContext` reduces CLI daemon boilerplate ≥60% (lines per command)

## Phase 5: CLI Pipeline Subcommand

- [ ] 5.1 Modify `sdk/quantlab/cli/main.py`: add `pipeline` subcommand with `run`/`status`/`list` subcommands
- [ ] 5.2 Implement `pipeline run <yaml>`: parse YAML → stage registry → build Pipeline → PipelineRunner → stream status
- [ ] 5.3 Implement `pipeline status <name>`: show run state + per-stage results
- [ ] 5.4 Implement `pipeline list`: show recent runs with timestamps + status
- [ ] 5.5 Add YAML stage registry mapping string type → Stage class

## Phase 6: Test Suite (Phase 5 Tests)

- [ ] 6.1 Create `tests/phase5/test_pipeline_base.py`: Stage ABC, Pipeline builder, Context, StageResult, PipelineResult
- [ ] 6.2 Create `tests/phase5/test_pipeline_runner.py`: sequential execution, timing, error stop, SKIPPED remaining
- [ ] 6.3 Create `tests/phase5/test_pipeline_stages.py`: 9 abstract base stages contracts (requires/provides)
- [ ] 6.4 Create `tests/phase5/test_phase4_stages.py`: 9 SQX-specific stage implementations
- [ ] 6.5 Create `tests/phase5/test_orchestrator_backcompat.py`: all 436 Phase 4 tests still pass unchanged
- [ ] 6.6 Create `tests/phase5/test_cli_pipeline.py`: `pipeline run/status/list` CLI commands
- [ ] 6.7 Create `tests/phase5/test_daemon_context.py`: DaemonContext async lifecycle, reduces boilerplate

---

## Dependency Graph (Topological Order)

```
1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6
                                    ↓
2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → 2.8 → 2.9 → 2.10
                                    ↓
3.1 → 3.2 → 3.3 → 3.4 → 3.5
                                    ↓
4.1 → 4.2 → 4.3
                                    ↓
5.1 → 5.2 → 5.3 → 5.4 → 5.5
                                    ↓
6.1 → 6.2 → 6.3 → 6.4 → 6.5 → 6.6 → 6.7
```

## Implementation Order

1. **Phase 1** (pipeline core) — independent, foundation for everything
2. **Phase 2** (SQX stages) — depends on Phase 1 base classes
3. **Phase 3** (orchestrator refactor) — depends on Phase 2 stages
4. **Phase 4** (exceptions + DaemonContext) — depends on Phase 1 exceptions, independent of Phase 3
5. **Phase 5** (CLI) — depends on Phase 1 + Phase 4
6. **Phase 6** (tests) — each test file depends on its corresponding implementation phase

---

## Next Step

**Decision required**: This change is estimated at **High** risk for 400-line budget (2800–3500 lines). Delivery strategy is `ask-on-risk`. The orchestrator must ask the user to confirm the chain strategy (`feature-branch-chain` recommended) before launching `sdd-apply`.

**Recommended PR chain (feature branch chain):**
- PR 1: `feature/phase5-pipeline-core` (base) ← Phase 1
- PR 2: `feature/phase5-sqx-stages` (base = PR 1) ← Phase 2
- PR 3: `feature/phase5-orchestrator-refactor` (base = PR 2) ← Phase 3
- PR 4: `feature/phase5-cli-and-tests` (base = PR 3) ← Phases 4, 5, 6