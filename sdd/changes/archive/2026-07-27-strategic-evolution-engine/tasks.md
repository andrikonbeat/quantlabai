# Tasks: Strategic Evolution Engine

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 950–1200 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation) → PR 2 (Core) → PR 3 (Orchestrator + Tests) |
| Delivery strategy | auto-chain |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Foundation: config, models, fitness, MC stage | PR 1 | `pytest sdk/tests/evolution/test_config.py sdk/tests/evolution/test_fitness.py -v` | N/A — stateless models/weights only | Revert `sdk/quantlab/evolution/` + `monte_carlo_stage.py` + registry change |
| 2 | Core: pool, genetic, novelty, validator + their tests | PR 2 | `pytest sdk/tests/evolution/ -v -k "not orchestrator"` | N/A — unit-tested with mocks; validator needs SQX daemon which is CI-only | Revert pool/, genetic.py, novelty.py, validator.py |
| 3 | Orchestrator: trigger handling, cycle lifecycle, integration tests | PR 3 | `pytest sdk/tests/evolution/test_orchestrator.py -v` | `python -c "from quantlab.evolution import EvolutionOrchestrator; ..."` with MG signal fixture | Revert orchestrator.py + integration tests |

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Create `sdk/quantlab/evolution/__init__.py` — public API exports
- [x] 1.2 Create `sdk/quantlab/evolution/config.py` — `EvolutionConfig` Pydantic model (enabled, mode, schedule, concurrency, thresholds, weight_profile)
- [x] 1.3 Create `sdk/quantlab/evolution/models.py` — `EvolutionCandidate`, `CandidateStatus`, `EvolutionResult`, `EvolutionSignal`
- [x] 1.4 Create `sdk/quantlab/pipeline/stages/monte_carlo_stage.py` — `MonteCarloStage` wrapping Retester
- [x] 1.5 Modify `sdk/quantlab/pipeline/registry.py` — register `monte_carlo` stage in `StageRegistry._register_agent_stages()`

## Phase 2: Core Implementation

- [x] 2.1 Create `sdk/quantlab/evolution/fitness.py` — `FitnessFunction` wrapping HealthScoreCalculator with configurable weight profiles
- [x] 2.2 Create `sdk/quantlab/evolution/pool.py` — `CandidatePool` with JSON-filesystem persistence, add, promote, load_all, get_ready_for_promotion
- [x] 2.3 Create `sdk/quantlab/evolution/genetic.py` — `GeneticOptimizer` parsing CFX via CfxPatcher, delegating to Optimizer, scoring via FitnessFunction
- [x] 2.4 Create `sdk/quantlab/evolution/novelty.py` — `NoveltyGenerator` driving ResearchDirector DSL → BuilderAgent pipeline → short backtest
- [x] 2.5 Create `sdk/quantlab/evolution/validator.py` — `CandidateValidator` running PipelineRunner with backtest → walk-forward → Monte Carlo chain

## Phase 3: Integration / Wiring

- [x] 3.1 Create `sdk/quantlab/evolution/orchestrator.py` — `EvolutionOrchestrator` with scheduled poll + MG signal trigger, priority sorting, mode dispatch, concurrency limit
- [x] 3.2 Wire orchestrator lifecycle: generation (genetic/generative) → validation (PipelineRunner) → pool entry → MG pickup

## Phase 4: Testing

- [x] 4.1 Write unit tests for `EvolutionConfig` — defaults, mode enum, threshold bounds
- [x] 4.2 Write unit tests for `FitnessFunction` — mock StatsResult, verify weighted average
- [x] 4.3 Write unit tests for `GeneticOptimizer` — mock CfxPatcher, verify invalid mutations discarded
- [x] 4.4 Write unit tests for `CandidatePool` — temp dir persistence, survive restart
- [x] 4.5 Write unit tests for `EvolutionOrchestrator` — trigger handling, priority, concurrency, disabled toggle
- [x] 4.6 Write integration test for full validation pipeline — short backtest → WF → MC with known strategy CFX
- [x] 4.7 Write integration test for `NoveltyGenerator` — stub ResearchDirector, verify DSL → BuilderAgent flow

## Phase 5: Cleanup / Documentation

- [x] 5.1 Add module docstring and public `__all__` to `sdk/quantlab/evolution/__init__.py`
- [x] 5.2 Update pipeline `__init__.py` to re-export `MonteCarloStage`
- [x] 5.3 Ensure `evolution.enabled` toggle (default `false`) disables all trigger paths

### Implementation Order

Phase 1 first (no dependencies) → Phase 2 (depends on models + config) → Phase 3 (depends on all core components) → Phase 4 (depends on implementation) → Phase 5 (polish). Split across 3 stacked PRs: PR 1 = Phase 1 + FitnessFunction; PR 2 = Phase 2 + their tests; PR 3 = Phase 3 + Phase 4 + Phase 5.

### Next Step

Ready for implementation (sdd-apply) — auto-chain PR 1 once chain strategy is decided by user.
