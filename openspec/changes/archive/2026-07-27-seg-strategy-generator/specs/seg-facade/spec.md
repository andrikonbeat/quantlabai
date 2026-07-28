# seg-facade Specification

## Purpose

Unified entry point for strategy generation and evolution. The StrategyGenerator facade accepts user intent and orchestrates the full lifecycle: generate/evolve → backtest → validate → score → return ranked results.

## Requirements

### Requirement: Generate strategies from intent

The StrategyGenerator MUST accept user intent parameters and produce ranked, validated strategy candidates.

#### Scenario: Generate with full intent
- GIVEN intent with market, timeframe, risk_profile, and objective
- WHEN `StrategyGenerator.generate(intent)` is called
- THEN a list of ranked EvolutionCandidate objects is returned
- AND each candidate has a fitness_score ≥ 0

#### Scenario: Evolve existing strategy
- GIVEN a valid strategy_id from the pool
- WHEN `StrategyGenerator.evolve(strategy_id)` is called
- THEN new EvolutionCandidate objects are returned with parent_trace pointing to the original

### Requirement: Mode dispatch

The StrategyGenerator MUST dispatch to the correct engine based on evolution mode (GENETIC_ONLY, GENERATIVE_ONLY, FULL).

#### Scenario: FULL mode uses both engines
- GIVEN mode=FULL
- WHEN `StrategyGenerator.generate(intent)` is called
- THEN candidates from both GeneticOptimizer and NoveltyGenerator are included

### Requirement: Error handling

The StrategyGenerator MUST handle partial failures gracefully.

#### Scenario: One engine fails
- GIVEN mode=FULL where NoveltyGenerator fails
- WHEN `StrategyGenerator.generate(intent)` is called
- THEN candidates from GeneticOptimizer are still returned
- AND the error is recorded in the results metadata
