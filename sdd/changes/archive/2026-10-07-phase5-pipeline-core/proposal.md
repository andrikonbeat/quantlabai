# Proposal: Phase 5 — Pipeline Core & Campaign Orchestrator Refactor

## Intent

Extract a reusable, SQX-agnostic pipeline framework from the monolithic `CampaignOrchestrator`. Currently the orchestrator bakes 11 sequential phases into a single class with inline phase implementations — no composition, no reuse, no CLI-driven workflow. This change decouples pipeline execution from domain logic so users can compose, run, and monitor arbitrary workflows programmatically and from the CLI.

## Scope

### In Scope
- `sdk/quantlab/pipeline/` module: `Stage` ABC, `Pipeline` dataclass, `PipelineContext`, `PipelineRunner`, `StageResult`/`PipelineResult` models
- 9 built-in abstract stages extracted from `CampaignPhase`: Validate, Translate, DaemonStart, Campaign, Export, Read, ComputeStats, KnowledgeStore, Report
- `CampaignOrchestrator` refactor: internally builds `Pipeline` from its `CampaignPhase` stages, delegates to `PipelineRunner`. Public API 100% backward compatible
- CLI `pipeline` subcommand: `run <pipeline.yaml>`, `status <name>`, `list`
- Shared `DaemonContext` helper to eliminate repeated daemon lifecycle boilerplate across CLI commands

### Out of Scope
- Reporting module (HTML/JSON/charts) — deferred
- Knowledge Lake query/search extensions — deferred
- Cross-campaign statistics aggregation — deferred

## Capabilities

### New Capabilities
- `pipeline-core`: Generic pipeline execution framework — `Stage` ABC, `Pipeline` composition via `.then()`, `PipelineRunner` with sequential execution, context passthrough, per-stage timing, and error isolation

### Modified Capabilities
- `campaign-orchestrator`: Refactored to compose internally from `pipeline-core` stages. All public exports (`CampaignOrchestrator`, `CampaignConfig`, `CampaignResult`, `CampaignPhase`, `PhaseStatus`, `PhaseResult`, `run_campaign`) remain identical
- `sqx-cli-wrapper`: Add `pipeline` subcommand with `run`/`status`/`list`; extract `DaemonContext` to reduce boilerplate

## Approach

1. **`pipeline/` module** — pure Python stdlib with zero SQX/phase4 imports
   - `Stage(ABC)`: `name: str`, `requires: list[str]`, `provides: list[str]`, `async execute(ctx: PipelineContext) -> Any`
   - `Pipeline`: ordered list of stages, fluent `.then(stage)` builder
   - `PipelineContext`: shared `config: dict`, `artifacts: dict`, `metadata: dict`, `error: Exception | None`
   - `PipelineRunner`: iterates stages, catches per-stage errors, records `StageResult` with timing
   - `StageResult`: `stage_name, status, duration, error, output`
   - `PipelineResult`: `stages: list[StageResult]`, `total_duration, is_successful, error`

2. **Built-in stages** — each is a `Stage` subclass in `stages.py`, SQX-agnostic with clear I/O

3. **CampaignOrchestrator refactor** — `run()` builds `Pipeline([ValidateStage, TranslateStage, ...])` → `PipelineRunner.run(pipeline, ctx)` → maps `PipelineResult` back to `CampaignResult`

4. **CLI additions** — `pipeline run <yaml>` parses YAML into stage list, creates runner, streams status; `DaemonContext` helper wraps `SQXDaemonManager` lifecycle

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/pipeline/` | New | 5 files: `__init__.py`, `base.py`, `stages.py`, `runner.py`, `models.py` |
| `sdk/quantlab/phase4/campaign_orchestrator.py` | Modified | Internal rewrite — public API unchanged |
| `sdk/quantlab/cli/main.py` | Modified | +`pipeline` subcommand, +`DaemonContext` helper |
| `tests/phase4/` | Unchanged | Must still pass all 436 tests unchanged |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Refactor breaks existing tests | Low | Keep public API identical; add integration tests before refactor |
| Over-general pipeline framework | Low | Keep Stage interface minimal — 3 properties + 1 method |
| CLI regression from daemon refactor | Low | Extract helper first, test separately, then apply to existing commands |

## Rollback Plan
- Revert `campaign_orchestrator.py` to pre-refactor state
- Remove `sdk/quantlab/pipeline/` directory entirely
- Revert `cli/main.py` pipeline additions and daemon helper
- Verify all 436 Phase 4 tests pass

## Dependencies
- None — pure Python stdlib (`abc`, `dataclasses`, `asyncio`, `enum`)

## Success Criteria
- [ ] All 436 Phase 4 tests pass unchanged
- [ ] `CampaignOrchestrator.run()` returns `CampaignResult` identical to pre-refactor structure
- [ ] `pipeline/` module has zero `import quantlab.phase4` or `import quantlab.` SQX-domain references
- [ ] `PipelineRunner` produces per-stage `StageResult` with accurate timing and error capture
- [ ] CLI `pipeline run <yaml>` executes arbitrary stage sequences from a YAML config
- [ ] CLI daemon boilerplate reduced by ≥60% (measured by lines per command)
