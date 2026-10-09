# Delta for Strategic Evolution Engine

## ADDED Requirements

### Requirement: Evolution Orchestrator

The system MUST provide an EvolutionOrchestrator with dual-trigger support (scheduled + MG event).

#### Scenario: Scheduled cycle

- GIVEN a configured schedule interval (e.g., weekly)
- WHEN the interval elapses
- THEN a new evolution cycle initiates

#### Scenario: MetaGuardian event trigger

- GIVEN a DEGRADING or REPLACEMENT_PENDING signal from MetaGuardian
- WHEN received
- THEN the signaled strategy becomes a priority evolution target

#### Scenario: Priority and concurrency limits

- GIVEN flagged and idle strategies
- WHEN selecting targets
- THEN flagged ones are processed first
- AND concurrency does not exceed max_concurrent_evolutions

### Requirement: Genetic Optimizer

The system MUST evolve strategies through CFX parameter mutation via GeneticOptimizer.

#### Scenario: Parameter mutation

- GIVEN a CFX strategy with numeric parameters
- WHEN the optimizer runs
- THEN it parses CFX parameters, mutates configured ranges
- AND generates candidates through the OptimizerAutomation lifecycle

#### Scenario: Contract validation before mutation

- GIVEN a CFX strategy marked for mutation
- WHEN the optimizer validates contract integrity
- THEN mutations that break essential strategy structure are discarded

#### Scenario: Baseline improvement gate

- GIVEN a baseline Health Score
- WHEN candidates are generated
- THEN those below a configurable fitness threshold are discarded

### Requirement: Novelty Generator

The system MUST create de novo strategies via Research DSL and Builder through NoveltyGenerator.

#### Scenario: DSL to strategy generation

- GIVEN a Research DSL configuration from ResearchDirector
- WHEN processed
- THEN Translator converts DSL to CFX
- AND Builder produces a runnable strategy

#### Scenario: Iterative refinement

- GIVEN a candidate below threshold after short backtest
- WHEN refinement is allowed
- THEN the generator MAY iterate up to a configurable max_attempts

### Requirement: Fitness Function

The system MUST score candidates using Health Score with configurable weights via FitnessFunction.

#### Scenario: Composite fitness score

- GIVEN a candidate with StatsResult from StatisticsEngine
- WHEN scored
- THEN Health Score components are computed
- AND weighted averaging produces a 0–100 fitness score

#### Scenario: Custom weight profile

- GIVEN a configured weight profile overriding defaults
- WHEN scoring
- THEN the custom profile is applied

### Requirement: Candidate Validator

The system MUST run full pipeline validation (backtest → walk-forward → Monte Carlo) before promotion.

#### Scenario: Full pipeline passes

- GIVEN a candidate that passed early-stage filtering
- WHEN the validator runs
- THEN PipelineRunner executes backtest → walk-forward → Monte Carlo
- AND returns a pass/fail report per stage

#### Scenario: Stage failure rejection

- GIVEN a candidate failing any validation stage
- WHEN the stage fails
- THEN the candidate is rejected
- AND is NOT eligible for pool entry

### Requirement: Candidate Pool

The system MUST maintain a validated candidate pool with configurable minimum fitness threshold for promotion.

#### Scenario: Qualified candidate promoted

- GIVEN a validated candidate with fitness >= threshold
- WHEN added to the pool
- THEN MetaGuardian picks it up on the next evaluate() cycle

#### Scenario: Sub-threshold rejection

- GIVEN a validated candidate with fitness < threshold
- WHEN evaluated for pool entry
- THEN the candidate is NOT added
- AND reason is logged

#### Scenario: Pool survives restart

- GIVEN existing candidates in the pool
- WHEN the system restarts
- THEN the pool is loaded from persistence
- AND candidates remain available for evaluation

### Requirement: Configuration

The system MUST support configuration to enable/disable evolution, select mode, and control concurrency.

#### Scenario: Evolution disabled

- GIVEN evolution.enabled=false
- WHEN any trigger fires
- THEN no cycle starts
- AND existing pool persists unchanged

#### Scenario: Mode selection — genetic only

- GIVEN evolution.mode="genetic"
- WHEN a cycle runs
- THEN GeneticOptimizer runs
- AND NoveltyGenerator is skipped

#### Scenario: Mode selection — generative only

- GIVEN evolution.mode="generative"
- WHEN a cycle runs
- THEN NoveltyGenerator runs
- AND GeneticOptimizer is skipped
