# Portfolio Composer Specification

## Purpose

HTTP-based portfolio weight optimization using StrategyQuant's `recompute` and `savePortfolio` endpoints. Loads strategies into an SQX session, optimizes weights against a fitness metric, and exports the result as a portfolio CFX file.

## Requirements

### Requirement: Load Strategies into SQX Session

The system MUST load a list of strategy IDs into the current SQX HTTP session via the appropriate API.

#### Scenario: Load strategies adds all to session

- GIVEN a list of 5 valid strategy IDs
- WHEN `PortfolioComposer.load_strategies(strategy_ids)` is called
- THEN each strategy ID is sent to the SQX load endpoint
- AND all 5 strategies appear in the session strategy list

#### Scenario: Load invalid strategy ID raises StrategyNotFoundError

- GIVEN a list containing 1 invalid strategy ID
- WHEN `load_strategies()` is called
- THEN StrategyNotFoundError is raised with the invalid ID
- AND no strategies are loaded (atomic operation)

#### Scenario: Load strategies with empty list is no-op

- GIVEN an empty strategy list
- WHEN `load_strategies([])` is called
- THEN no HTTP calls are made and method returns successfully

### Requirement: Optimize Weights via recompute

The system MUST invoke the SQX `recompute` endpoint with a fitness metric to optimize portfolio weights.

#### Scenario: Optimize weights returns weight dictionary

- GIVEN 3 strategies loaded in session
- WHEN `PortfolioComposer.optimize_weights(fitness_metric="NetProfit")` is called
- THEN the `recompute` endpoint is invoked with the metric
- AND a dictionary `{strategy_id: weight}` is returned with weights summing to 1.0

#### Scenario: Optimize with custom metric uses provided metric

- GIVEN strategies loaded
- WHEN `optimize_weights(fitness_metric="SharpeRatio")` is called
- THEN the `recompute` request includes `fitness=SharpeRatio`

#### Scenario: Optimize with no strategies loaded raises error

- GIVEN no strategies loaded in session
- WHEN `optimize_weights()` is called
- THEN PortfolioEmptyError is raised

### Requirement: Save Portfolio CFX

The system MUST persist the optimized portfolio as a CFX file via the `savePortfolio` HTTP endpoint.

#### Scenario: Save portfolio exports CFX file

- GIVEN optimized weights exist from `optimize_weights()`
- WHEN `PortfolioComposer.save_portfolio(name="MyPortfolio", output_dir="/tmp/out")` is called
- THEN `savePortfolio` endpoint is called with name and weights
- AND a `{name}.cfx` file is written to output_dir
- AND the CFX contains the portfolio weights and strategy references

#### Scenario: Save with duplicate name overwrites

- GIVEN a portfolio CFX already exists at output path
- WHEN `save_portfolio()` is called with same name
- THEN the existing file is overwritten with new weights

#### Scenario: Save without prior optimization raises error

- GIVEN `load_strategies()` was called but `optimize_weights()` was not
- WHEN `save_portfolio()` is called
- THEN PortfolioNotOptimizedError is raised

### Requirement: End-to-End Portfolio Creation

The system SHOULD provide a convenience method that chains load → optimize → save.

#### Scenario: Create portfolio end-to-end

- GIVEN strategy IDs ["strat1", "strat2", "strat3"]
- WHEN `PortfolioComposer.create_portfolio(strategy_ids, fitness="NetProfit", name="MyPortfolio", output_dir="/tmp")` is called
- THEN strategies are loaded, weights optimized, and portfolio CFX saved
- AND the method returns the path to the created CFX file

#### Scenario: Create portfolio with custom metric and weight constraints

- GIVEN strategy IDs and fitness="SortinoRatio"
- WHEN `create_portfolio()` is called with `min_weight=0.1, max_weight=0.6`
- THEN optimization uses these constraints
- AND returned weights respect min/max bounds

### Requirement: Dry-Run Mode

The system MUST support dry-run mode for testing without SQX server.

#### Scenario: Dry-run creates mock portfolio CFX

- GIVEN PortfolioComposer with dry_run=True
- WHEN `create_portfolio(["s1", "s2"], "NetProfit", "Test", "/tmp")` is called
- THEN no HTTP calls are made
- AND a mock CFX file is created at `/tmp/Test.cfx`
- AND the CFX contains mock weights for the provided strategies