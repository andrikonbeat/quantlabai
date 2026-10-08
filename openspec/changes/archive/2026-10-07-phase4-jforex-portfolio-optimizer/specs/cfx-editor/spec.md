# Delta for CFX Editor

## ADDED Requirements

### Requirement: Portfolio CFX Section Writers

The system MUST provide Pydantic models and writer methods for Portfolio-specific CFX sections: `AutomaticPortfolioBuilder`, `PortfolioSettings`.

#### Scenario: AutomaticPortfolioBuilder model encodes genetic parameters

- GIVEN a CFX being built for Portfolio Master
- WHEN `CfxWriter.set_automatic_portfolio_builder(generations=50, population=100, fitness="NetProfit")` is called
- THEN the model includes `<AutomaticPortfolioBuilder>` with Generations=50, PopulationSize=100, FitnessFunction="NetProfit"
- AND writer produces valid XML for this section

#### Scenario: PortfolioSettings model encodes portfolio constraints

- GIVEN a CFX with portfolio configuration
- WHEN `CfxWriter.set_portfolio_settings(min_strategies=2, max_strategies=10, rebalance="Monthly")` is called
- THEN the model includes `<PortfolioSettings>` with MinStrategies=2, MaxStrategies=10, RebalancingPeriod="Monthly"

#### Scenario: Read portfolio CFX extracts builder settings

- GIVEN a valid Portfolio Master CFX file
- WHEN `CfxReader.read_portfolio_cfx(path)` is called
- THEN a PortfolioCfxModel is returned with AutomaticPortfolioBuilder and PortfolioSettings populated

### Requirement: Optimizer CFX Section Writers

The system MUST provide models and writers for Optimizer CFX sections: `Optimization`, `Parameters`, `WalkForward`, `Databanks`.

#### Scenario: Optimization section encodes method and objective

- GIVEN an optimizer CFX being built
- WHEN `CfxWriter.set_optimization(method="Genetic", objective="SharpeRatio", walkforward_cycles=10)` is called
- THEN `<Optimization>` section includes Method="Genetic", ObjectiveFunction="SharpeRatio", WalkForwardCycles=10

#### Scenario: Parameters section encodes GA parameters

- GIVEN optimizer config with population=100, generations=50, crossover=0.8, mutation=0.1
- WHEN `CfxWriter.set_optimization_parameters(population=100, generations=50, crossover=0.8, mutation=0.1)` is called
- THEN `<Parameters>` section includes all four parameters with correct values

#### Scenario: WalkForward section encodes WF settings

- GIVEN config with walkforward_cycles=5, oot_ratio=0.3
- WHEN `CfxWriter.set_walkforward(cycles=5, oot_ratio=0.3)` is called
- THEN `<WalkForward>` section includes Cycles=5, OutOfSampleRatio=0.3

#### Scenario: Databanks section lists symbols

- GIVEN databanks=["EURUSD_H1", "GBPUSD_H1"]
- WHEN `CfxWriter.set_databanks(databanks)` is called
- THEN `<Databanks>` section includes both symbols

#### Scenario: Read optimizer CFX extracts all sections

- GIVEN a valid Optimizer CFX file
- WHEN `CfxReader.read_optimizer_cfx(path)` is called
- THEN an OptimizerCfxModel is returned with Optimization, Parameters, WalkForward, Databanks populated

### Requirement: Retester CFX Section Writers

The system MUST provide models and writers for Retester CFX sections: `Rankings` (acceptance), `CrossChecks` (MC/WF), `Data`.

#### Scenario: Rankings section encodes acceptance criteria

- GIVEN retester config with min_trades=30, confidence=0.95
- WHEN `CfxWriter.set_rankings(min_trades=30, confidence_level=0.95)` is called
- THEN `<Rankings>` section includes MinTrades=30, ConfidenceLevel=0.95

#### Scenario: CrossChecks section enables MC and WF

- GIVEN config with mc_runs=100, wf_cycles=5, mc_percentile=95
- WHEN `CfxWriter.set_crosschecks(mc_runs=100, wf_cycles=5, mc_percentile=95)` is called
- THEN `<CrossChecks>` includes MonteCarlo enabled with Runs=100, Percentile=95, WalkForward enabled with Cycles=5

#### Scenario: Data section lists databanks

- GIVEN databanks=["EURUSD_H1", "GBPUSD_H1"]
- WHEN `CfxWriter.set_retester_data(databanks)` is called
- THEN `<Data>` section lists both databanks with correct paths

#### Scenario: Read retester CFX extracts all sections

- GIVEN a valid Retester CFX file
- WHEN `CfxReader.read_retester_cfx(path)` is called
- THEN a RetesterCfxModel is returned with Rankings, CrossChecks, Data populated

## MODIFIED Requirements

### Requirement: Domain Modification Methods

The system SHOULD provide domain methods — `set_market()`, `add_timeframe()`, `enable_block()`, `disable_block()`, `set_genetic()`, `set_date_range()`, `add_ranking_condition()`, `enable_crosscheck()`, **`set_automatic_portfolio_builder()`**, **`set_portfolio_settings()`**, **`set_optimization()`**, **`set_optimization_parameters()`**, **`set_walkforward()`**, **`set_databanks()`**, **`set_rankings()`**, **`set_crosschecks()`**, **`set_retester_data()`** — that modify underlying models without manual XML construction. (Previously: 8 methods; now 16 methods)

#### Scenario: New portfolio methods work correctly

- GIVEN a CFX loaded into CfxPatcher
- WHEN applying `[set_automatic_portfolio_builder(50, 100, "NetProfit"), set_portfolio_settings(2, 10, "Monthly")]`
- THEN both modifications are validated and the resulting models reflect all changes
(Previously: only original 8 methods were supported)

#### Scenario: New optimizer methods work correctly

- GIVEN a CFX loaded into CfxPatcher
- WHEN applying `[set_optimization("Genetic", "SharpeRatio", 10), set_optimization_parameters(100, 50, 0.8, 0.1), set_walkforward(5, 0.3), set_databanks(["EURUSD_H1"])]`
- THEN all four modifications are validated and the resulting models reflect all changes
(Previously: only original 8 methods were supported)

#### Scenario: New retester methods work correctly

- GIVEN a CFX loaded into CfxPatcher
- WHEN applying `[set_rankings(30, 0.95), set_crosschecks(100, 5, 95), set_retester_data(["EURUSD_H1"])]`
- THEN all three modifications are validated and the resulting models reflect all changes
(Previously: only original 8 methods were supported)

### Requirement: CfxPatcher High-Level API

The system MUST provide a CfxPatcher that accepts sequential modification instructions for LLM-driven editing. Each instruction MUST be validated before application; invalid instructions MUST raise ValidationError without applying partial changes. (Previously: 8 instruction types; now 16 instruction types including portfolio, optimizer, retester methods)

#### Scenario: Invalid portfolio builder parameters rejected

- GIVEN a CfxPatcher with loaded CFX
- WHEN an instruction `set_automatic_portfolio_builder(generations=0)` is applied
- THEN a ValidationError is raised and no instruction in the sequence is applied
(Previously: only original instruction types were validated)

#### Scenario: Invalid optimizer parameters rejected

- GIVEN a CfxPatcher with loaded CFX
- WHEN an instruction `set_optimization(method="InvalidMethod")` is applied
- THEN a ValidationError is raised listing valid methods: ["Genetic", "BruteForce", "Random"]
(Previously: only original instruction types were validated)

#### Scenario: Invalid retester parameters rejected

- GIVEN a CfxPatcher with loaded CFX
- WHEN an instruction `set_crosschecks(mc_runs=5)` is applied
- THEN a ValidationError is raised: "mc_runs must be >= 10"
(Previously: only original instruction types were validated)

## REMOVED Requirements

None.

## RENAMED Requirements

None.