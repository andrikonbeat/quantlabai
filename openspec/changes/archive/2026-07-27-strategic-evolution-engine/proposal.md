# Proposal: Strategic Evolution Engine

## Intent

Without the SEE, QuantLab AI detects degradation (via MetaGuardian) but has no mechanism to self-heal: degraded strategies accumulate, replacement candidates don't exist, and the portfolio drifts toward obsolescence. The SEE closes the loop — MetaGuardian detects → SEE evolves → MetaGuardian validates.

## Scope

### In Scope
- New `sdk/quantlab/evolution/` module with:
  - `EvolutionOrchestrator` — scheduling, priority, candidate lifecycle
  - `GeneticOptimizer` — parameter evolution on existing strategies via CFX mutation
  - `NoveltyGenerator` — de novo strategy generation via ResearchDSL + Builder pipeline
  - `CandidateValidator` — full validation pipeline (backtest → walk-forward → Monte Carlo)
  - `FitnessFunction` — composable Health Score (reuses Change 1) with configurable weights
- Dual trigger: fixed schedule configurable (e.g. weekly) + event-driven from MetaGuardian (DEGRADING / REPLACEMENT_PENDING)
- Configurable evolution modes (genetic, generative, or both)
- Candidate pool with configurable minimum fitness threshold for promotion

### Out of Scope
- MetaGuardian integration (already scoped in Change 4) — SEE emits candidates, MG evaluates via its cycle
- Real-time strategy switching — promotion = candidate becomes active on next MG evaluate()
- Human-in-the-loop approval (future)
- Portfolio-level correlation/diversification optimization — SEE optimises individual strategies

## Capabilities

### New Capabilities
- `strategic-evolution-engine`: Core evolution module with orchestrator, genetic optimizer, novelty generator, candidate validator, and fitness function

### Modified Capabilities
- None — SEE is a standalone capability; MetaGuardian signals are defined in the MG spec (Change 4) and consumed by SEE as input, not spec change

## Approach

1. **Dual trigger** — `EvolutionOrchestrator` polls schedule + listens for MG signals
2. **Prioritisation** — strategies flagged by MG as DEGRADING/REPLACEMENT_PENDING get priority; idle strategies selected by age or performance
3. **Genetic mode** — Parse CFX parameters, mutate ranges, run OptimizerAutomation lifecycle, score candidates via FitnessFunction
4. **Generative mode** — ResearchDirector emits DSL config, Builder generates CFX, short backtest → score → iterate
5. **Validation** — surviving candidates run full PipelineRunner chain (backtest → WF → Monte Carlo)
6. **Promotion** — candidates above minimum fitness threshold enter pool; MG picks them up on next evaluate()

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/evolution/` | New | Entire SEE module |
| `sdk/quantlab/pipeline/` | Modified | New SEE-specific validation stage (Monte Carlo) |
| `sdk/quantlab/guardian/` | Modified | MetaGuardian emits signals consumed by SEE |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Genetic optimisation overfits to past data | High | Mandatory walk-forward + Monte Carlo validation; minimum out-of-sample threshold |
| Generative mode produces low-quality strategies | Medium | Configurable fitness threshold; sub-threshold candidates discarded |
| SEE scheduling conflicts with pipeline load | Low | Respect PipelineRunner capacity; configurable max concurrent evolutions |
| CFX mutation breaks essential strategy logic | Medium | Contract validation on mutated CFX before running optimisation |

## Rollback Plan

- Disable SEE via config toggle (`evolution.enabled: false`)
- Existing candidate pool persists but is not evaluated
- MG continues without new candidates; strategies remain in their current state
- Manual cleanup of candidate pool files if needed

## Dependencies

- **Health Score System (Change 1)**: FitnessFunction uses HealthScoreCalculator
- **MetaGuardian (Change 4)**: Receives DEGRADING/REPLACEMENT_PENDING signals
- **PipelineRunner (Feature 5)**: Runs validation stages
- **OptimizerAutomation (Feature 5e)**: Genetic mode uses Optimizer lifecycle
- **Research DSL + Translator (Feature 3)**: Generative mode uses DSL generation
- **StatisticsEngine (Feature 5d)**: Computes StatsResult for fitness evaluation
- **SQX Translator / CFX Editor**: CFX parsing and mutation for genetic mode

## Success Criteria

- [ ] SEE generates ≥1 valid candidate per cycle when strategies are degrading
- [ ] Genetic mode produces candidates with improved Health Score over baseline
- [ ] Novelty candidates pass full validation pipeline (backtest → WF → Monte Carlo)
- [ ] MG signals correctly trigger SEE evolution events
- [ ] Config toggle disables SEE without side effects
