# Delta Spec — Results Analysis Stage

Deterministic AnalysisStage between statistics and review: parses `strategies.csv`, computes per-strategy metrics, applies overfit heuristics, selects strategies. New capability `strategy-analysis`; ADDED deltas to `result-reader` and `pipeline-core`; new spec content for `reviewer-agent` and `sqx-mock-server`.

## New Spec: strategy-analysis

### Requirement: Per-Strategy Metrics

The system MUST compute per-strategy metrics by reusing `StatisticsEngine.compute_all()` (`StatsResult`): profit factor, Sharpe, Sortino, max drawdown, MAR, recovery factor, expectancy, win rate, trade count. Metrics whose source columns are absent MUST be `None`, never a parse failure.

#### Scenario: Full metrics for 30 strategies

- GIVEN strategies.csv with 30 strategies and PF, Sharpe, win rate, trade-count columns
- WHEN the analysis engine computes metrics
- THEN each strategy has a metrics dict with those fields populated
- AND missing source columns yield None, not errors

### Requirement: Overfit Heuristics

The system MUST flag overfit-risk when any available heuristic triggers: (a) extreme PF/Sharpe with trade count below the minimum; (b) MC p10 curve breach when MC columns are present; (c) WF OOS/IS degradation ratio below threshold when wf cycles are present. Thresholds MUST come from `ResearchConfig`, and heuristics MUST be deterministic (no RNG, no LLM).

#### Scenario: Too-good-to-be-true

- GIVEN a strategy with PF 5.0 and only 5 trades
- WHEN heuristics run
- THEN the strategy is flagged overfit-risk and excluded from selection

#### Scenario: MC p10 breach

- GIVEN MC columns present and the p10 curve crossing zero
- WHEN heuristics run
- THEN the strategy is flagged overfit-risk

#### Scenario: WF degradation

- GIVEN wf cycles present with OOS/IS Sharpe ratio 0.5 (below 0.7)
- WHEN heuristics run
- THEN the strategy is flagged overfit-risk

#### Scenario: Thresholds from ResearchConfig

- GIVEN ResearchConfig sets min_trades=50 and oos_is_ratio=0.8
- WHEN heuristics run
- THEN configured thresholds apply instead of defaults

### Requirement: Strategy Selection

The system MUST score each strategy, apply thresholds, and produce `strategy_analysis` (per-strategy metrics dict), `strategy_verdicts` (per-strategy ACCEPT/ITERATE/REJECT), and `selected_strategies` (accepted strategy IDs/names).

#### Scenario: 8 of 30 selected

- GIVEN 30 strategies, 8 passing all thresholds
- WHEN selection runs
- THEN selected_strategies contains exactly 8 entries
- AND strategy_verdicts marks 8 ACCEPT and 22 REJECT

#### Scenario: Empty selection

- GIVEN no strategy passes the thresholds
- WHEN selection runs
- THEN selected_strategies is empty and a warning is emitted
- AND the portfolio stage still runs with an empty list

### Requirement: Graceful Degradation

The AnalysisStage MUST NOT hard-fail when strategies.csv is missing or unparseable: it SHALL emit a warning and produce empty `strategy_analysis`, `strategy_verdicts`, and `selected_strategies`, letting the pipeline continue.

#### Scenario: Missing strategies.csv

- GIVEN export_paths contains no strategies.csv
- WHEN the stage executes
- THEN a warning is logged and all three artifacts are empty
- AND review runs with its existing fallback (needs_review/NO_DATA)

#### Scenario: Unparseable strategies.csv

- GIVEN strategies.csv cannot be parsed (corrupt content)
- WHEN the stage executes
- THEN a warning is logged and the pipeline continues with empty results

## Delta: result-reader

### ADDED Requirements

#### Requirement: Strategies Databank Reading

The system MUST parse a strategies databank CSV via `STRATEGY_COLUMNS`, an alias-mapped column dict mirroring `TRADE_COLUMNS` (name, PF, Sharpe, trades, win rate, MC p10, WF IS/OOS). Unknown columns MUST be ignored; format variations SHALL resolve via aliases; parsing MUST never hard-fail on unknown or extra columns.

#### Scenario: Unknown columns tolerated

- GIVEN strategies.csv with unrecognized extra columns
- WHEN the reader parses it
- THEN known columns are mapped and unknown ones ignored without error

#### Scenario: Alias mapping

- GIVEN a column titled "Profit Factor" instead of "PF"
- WHEN the reader parses it
- THEN profit_factor is populated via the alias

## Delta: pipeline-core

### ADDED Requirements

#### Requirement: AnalysisStage Contract

The system MUST provide `AnalysisStage` (name `"analysis"`) with requires `["export_paths", "statistics"]` and provides `["strategy_analysis", "selected_strategies", "strategy_verdicts", "wf_cycles"]`, registered in `StageRegistry`.

#### Scenario: AnalysisStage I/O contract

- GIVEN AnalysisStage
- WHEN inspecting requires/provides
- THEN requires includes export_paths and statistics
- AND provides includes strategy_analysis, selected_strategies, strategy_verdicts, wf_cycles

#### Scenario: Registered as "analysis"

- GIVEN StageRegistry
- WHEN looking up "analysis"
- THEN the AnalysisStage class is returned

#### Requirement: Analysis Stage Wiring

`ResearchDirector` MUST insert the analysis stage between statistics and review; `generate_pipeline_config` MUST emit the analysis agent stage in that position. PortfolioStage MUST receive `selected_strategies` produced by the analysis stage.

#### Scenario: Stage order

- GIVEN a configured pipeline
- WHEN the stage list is built
- THEN order is statistics → analysis → review → portfolio

#### Scenario: Portfolio input satisfied

- GIVEN the analysis stage writes selected_strategies
- WHEN PortfolioStage executes
- THEN it consumes selected_strategies from the analysis stage

#### Requirement: ReviewStage Consumes Strategy Analysis

`ReviewStage.requires` SHALL include `strategy_analysis`; the review stage SHALL read the `strategy_analysis` and `wf_cycles` artifacts produced by analysis.

#### Scenario: ReviewStage contract updated

- GIVEN ReviewStage
- WHEN inspecting requires
- THEN requires includes strategy_analysis

## New Spec: reviewer-agent

### Requirement: Strategy Analysis Data Closure

ReviewerAgent MUST consume `strategy_analysis` and `wf_cycles` from context artifacts when present, running WF-degradation and benchmark checks on real data. When absent, it MUST keep the existing fallback (needs_review, NO_DATA verdicts).

#### Scenario: Real data available

- GIVEN artifacts include wf_cycles and strategy_analysis
- WHEN the reviewer runs
- THEN WF degradation is computed from wf_cycles instead of "No walk-forward data available"

#### Scenario: Fallback preserved

- GIVEN no strategy_analysis/wf_cycles in artifacts
- WHEN the reviewer runs
- THEN it returns needs_review with NO_DATA benchmark verdict as before

## New Spec: sqx-mock-server

### Requirement: Mock strategies.csv Emission

The mock SQX server MUST emit a realistic `strategies.csv` in the mock export directory alongside trades.csv/equity.csv, containing multiple strategies with the alias-mappable columns the reader and engine expect.

#### Scenario: Mock export includes strategies.csv

- GIVEN a completed mock campaign
- WHEN export files are generated
- THEN the export dir contains strategies.csv with more than one strategy row and known column names

## Acceptance Criteria

Same as proposal success criteria: analysis stage runs between stats and review; `strategies.csv` parses with unknown columns tolerated; `selected_strategies` provided before PortfolioStage (contract satisfied); ReviewerAgent wf/benchmark checks run on real data; mock round-trip and pipeline tests green.
