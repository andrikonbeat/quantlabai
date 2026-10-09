# Portfolio Composer Specification

## Purpose

Drive SQX Portfolio Composer's weight-optimization session over the HTTP API:
load strategies, run weight optimization, and save the resulting portfolio.

## Requirements

### PCO-REQ-01: Load strategies

The system SHALL load a list of strategy IDs into the SQX Portfolio Composer
session and record the successfully loaded IDs as the active session set.

#### Scenario: Load valid strategies

- GIVEN a running SQX daemon and strategy IDs that exist
- WHEN `load_strategies(["A", "B"])` is called
- THEN both IDs are loaded and `_loaded_strategy_ids == ["A", "B"]`

#### Scenario: Unknown strategy raises

- GIVEN a strategy ID SQX cannot resolve
- WHEN `load_strategies` is called with it
- THEN `StrategyNotFoundError` is raised
- AND the already-loaded strategies remain loaded (no rollback)

#### Scenario: Load failure raises

- GIVEN an HTTP failure while loading a strategy
- WHEN `load_strategies` is called
- THEN `PortfolioStrategyLoadError` is raised

### PCO-REQ-02: Clear session

The system SHALL provide a session reset that empties the tracked loaded-strategy
set (the HTTP API offers no per-strategy unload).

#### Scenario: Clear tracked session

- GIVEN a session with loaded strategies
- WHEN `clear_session()` is called
- THEN `_loaded_strategy_ids` is empty

### PCO-REQ-03: Parse and validate weights

The system SHALL parse an optimization result dict, validating that `weights`
exists, is a non-empty mapping of strategy ID to numeric weight, each weight is
within `[0, 1]`, and the sum is within 0.01 of 1.0.

#### Scenario: Valid weights parse

- GIVEN an optimization result with weights summing to 1.0
- WHEN `_parse_weights(result)` is called
- THEN a list of `(strategy_id, weight)` tuples is returned

#### Scenario: Missing weights key raises

- GIVEN a result dict without a `weights` key
- WHEN `_parse_weights` is called
- THEN `PortfolioOptimizationError` is raised

#### Scenario: Out-of-range weight raises

- GIVEN a weight above 1.0 or below 0
- WHEN `_parse_weights` is called
- THEN `PortfolioOptimizationError` is raised

#### Scenario: Bad sum raises

- GIVEN weights that do not sum to approximately 1.0
- WHEN `_parse_weights` is called
- THEN `PortfolioOptimizationError` is raised

### PCO-REQ-04: Optimize and save

The system SHALL run weight optimization against the loaded session and SHALL
support persisting the resulting portfolio weights via `save_portfolio`.

#### Scenario: Optimize loaded session

- GIVEN a session with loaded strategies
- WHEN `optimize_weights()` is called
- THEN a validated weight result is produced and normalised

#### Scenario: Empty session raises

- GIVEN no loaded strategies
- WHEN `optimize_weights()` is called
- THEN a typed `PortfolioOptimizationError` is raised