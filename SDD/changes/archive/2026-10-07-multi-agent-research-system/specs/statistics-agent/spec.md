# Statistics Agent Specification

## Purpose

Computes campaign statistics via StatisticsEngine, aggregates cross-campaign metrics via StatisticsAggregator, executes Monte Carlo bands for robustness validation, and detects performance degradation and regime changes.

---

## Requirements

### Requirement: Per-Campaign Statistics Computation

The system MUST compute comprehensive statistics from SQX export data (trades, equity curve) using StatisticsEngine.

#### Scenario: Full statistics computed from exports
- GIVEN export_paths from BuilderAgent containing trades.csv and equity.csv
- WHEN StatisticsAgent.compute_statistics() called
- THEN StatsResult with: sharpe, sortino, profit_factor, win_rate, max_drawdown, expectancy, total_trades, net_profit, MAR, Calmar
- AND all metrics use float64 precision

#### Scenario: Missing exports handled gracefully
- GIVEN export_paths missing equity.csv
- WHEN StatisticsAgent.compute_statistics() called
- THEN StatisticsError raised with missing file details

### Requirement: Cross-Campaign Aggregation

The system MUST aggregate statistics across multiple campaigns using StatisticsAggregator.aggregate_campaigns().

#### Scenario: Aggregate across 10 campaigns
- GIVEN 10 CampaignResult objects with statistics
- WHEN StatisticsAgent.aggregate_campaigns() called
- THEN dict with AggregateStats for each metric (sharpe, pf, win_rate, mdd, net_profit)
- AND AggregateStats includes count, mean, median, std, min, max, p25, p75

#### Scenario: Custom metric list
- GIVEN metrics=["sharpe", "sortino", "expectancy"]
- WHEN StatisticsAgent.aggregate_campaigns(metrics=...) called
- THEN only those 3 metrics in output dict

### Requirement: Monte Carlo Robustness Bands

The system MUST execute Monte Carlo bootstrap resampling of trade profits to generate percentile equity curves.

#### Scenario: Monte Carlo bands for robustness
- GIVEN 200 trades from campaign, n_simulations=1000, percentiles=[10, 50, 90]
- WHEN StatisticsAgent.monte_carlo_bands() called
- THEN returns dict: p10→list[101], p50→list[101], p90→list[101] (initial + 100 trades)
- AND deterministic with seed: same seed → identical results

#### Scenario: Monte Carlo detects overfitting
- GIVEN strategy with Sharpe=2.5 but MC p10 curve shows negative equity at trade 50
- WHEN StatisticsAgent.assess_robustness() called
- THEN robustness_flag = "OVERFIT_RISK", rationale includes "MC p10 below zero at 50% trades"

### Requirement: Degradation Detection and Regime Change Alerts

The system MUST compute rolling metrics and detect statistically significant degradation or regime shifts.

#### Scenario: Rolling Sharpe degradation alert
- GIVEN equity curve, window=60 periods
- WHEN StatisticsAgent.compute_rolling_metrics() called
- THEN RollingMetrics with rolling_sharpe, rolling_drawdown aligned to timestamps

#### Scenario: Regime change detected via rolling metrics
- GIVEN rolling_sharpe drops from 1.8 to 0.4 over 20 periods, rolling_drawdown spikes >2x
- WHEN StatisticsAgent.detect_regime_change() called
- THEN RegimeAlert: type="REGIME_SHIFT", confidence=0.85, from_regime="trending", to_regime="choppy"
- AND alert includes suggested action: "Reduce position size, widen stops"

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| StatisticsEngine computes all 10+ metrics | Unit test: known trades/equity → assert metric values |
| AggregateStats percentiles correct | Unit test: [1,2,3,4,5] → p25=2, p75=4 |
| Monte Carlo deterministic with seed | Unit test: same seed → identical output |
| Rolling metrics align with timestamps | Unit test: len(rolling_sharpe) == len(equity) |
| Regime alert includes actionable recommendation | Unit test: assert alert.action in ["reduce_size", "widen_stops", "pause"] |

---

## Non-Functional Requirements

- **Performance**: aggregate_campaigns(1000 campaigns) < 1s; monte_carlo(1000 trades, 1000 sims) < 3s
- **Dependencies**: statistics-engine, stats-aggregation, pandas, numpy
- **Numerical precision**: float64 throughout; decimal for financial aggregates if needed
- **Testability**: Pure functions — inject equity/trades, assert outputs