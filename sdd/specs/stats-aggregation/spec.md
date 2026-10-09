# Statistics Aggregation Specification

## Purpose

Provides cross-campaign and cross-WF-cycle statistical aggregation, rolling window metrics, benchmark comparison, and Monte Carlo percentile bands. Pure functions over data lists — stateless, testable, reusable. Integrates with Reporting (5b) for aggregate reports and Knowledge Query (5c) for historical data.

---

## Requirements

### Requirement: AggregateStats Model

The system MUST define `AggregateStats` model for summary statistics across a population of campaigns or WF cycles:

```python
class AggregateStats(BaseModel):
    count: int
    mean: float
    median: float
    std: float
    min: float
    max: float
    percentile_25: float
    percentile_75: float
    skew: float | None = None
    kurtosis: float | None = None
```

Applies to: Sharpe, Profit Factor, Win Rate, Max Drawdown, Net Profit, Expectancy, Total Trades.

#### Scenario: AggregateStats computes correct percentiles
- GIVEN values `[1.0, 1.5, 2.0, 2.5, 3.0]`
- WHEN `AggregateStats.from_values(values)` called
- THEN `percentile_25 == 1.5`, `percentile_75 == 2.5`, `median == 2.0`

#### Scenario: Single value edge case
- GIVEN `[1.5]`
- WHEN aggregated
- THEN `mean == median == min == max == 1.5`, `std == 0.0`

---

### Requirement: RollingMetrics Model

The system MUST define `RollingMetrics` for time-series rolling calculations:

```python
class RollingMetrics(BaseModel):
    timestamps: list[datetime]  # aligned with equity points
    rolling_sharpe: list[float | None]  # None for windows < min_periods
    rolling_drawdown: list[float | None]
    window: int
```

#### Scenario: Rolling Sharpe with 30-day window
- GIVEN daily equity for 100 days, window=30
- WHEN `rolling_sharpe(equity, 30)` called
- THEN first 29 values are `None`, values 30-99 are floats

---

### Requirement: BenchmarkComparison Model

The system MUST define `BenchmarkComparison` for strategy vs benchmark analysis:

```python
class BenchmarkComparison(BaseModel):
    strategy_returns: list[float]
    benchmark_returns: list[float]
    alpha: float  # annualized excess return
    beta: float   # covariance / benchmark variance
    information_ratio: float  # alpha / tracking_error
    tracking_error: float     # std of (strategy - benchmark)
    correlation: float
    up_capture: float         # avg strategy return when bench > 0 / avg bench return when bench > 0
    down_capture: float       # avg strategy return when bench < 0 / avg bench return when bench < 0
```

#### Scenario: Benchmark comparison computes all metrics
- GIVEN strategy returns `[0.01, -0.005, 0.02]`, benchmark `[0.008, -0.003, 0.015]`
- WHEN `benchmark_compare()` called
- THEN all fields populated, `beta ≈ 1.2`, `correlation > 0.9`

---

### Requirement: StatisticsAggregator.aggregate_campaigns

The system MUST provide:

```python
class StatisticsAggregator:
    @staticmethod
    def aggregate_campaigns(
        campaign_results: list[CampaignResult],
        metrics: list[str] | None = None  # default: ["sharpe", "profit_factor", "win_rate", "max_drawdown", "net_profit"]
    ) -> dict[str, AggregateStats]:
        """Returns dict of metric_name -> AggregateStats across all campaigns."""
```

Extracts metrics from `campaign.statistics` (StatsResult) or recomputes from trades/equity if missing.

#### Scenario: Aggregate across 10 campaigns
- GIVEN 10 CampaignResult objects with statistics
- WHEN `aggregate_campaigns(results)` called
- THEN returns dict with 5 AggregateStats (one per default metric)

#### Scenario: Custom metric list
- GIVEN `metrics=["sharpe", "sortino", "expectancy"]`
- WHEN called
- THEN only those 3 metrics in output dict

#### Scenario: Missing statistics recomputed from trades
- GIVEN campaign has `trades` and `equity` but no `statistics`
- WHEN aggregated
- THEN `StatisticsEngine.compute_all()` called internally, metrics derived

---

### Requirement: StatisticsAggregator.aggregate_wf_cycles

The system MUST provide:

```python
    @staticmethod
    def aggregate_wf_cycles(
        cycles: list[WalkForwardCycle],  # from phase4.optimizer.OptimizationResult
        metrics: list[str] | None = None
    ) -> dict[str, AggregateStats]:
        """Aggregate metrics across WF cycles. Uses cycle.out_of_sample_stats."""
```

`WalkForwardCycle` has: `cycle_id`, `in_sample_stats`, `out_of_sample_stats` (both `StatsResult`).

#### Scenario: Aggregate OOS stats across 5 WF cycles
- GIVEN `OptimizationResult` with 5 cycles
- WHEN `aggregate_wf_cycles(result.cycles)` called
- THEN returns AggregateStats for OOS Sharpe, PF, etc. across cycles

---

### Requirement: Rolling Sharpe and Drawdown

The system MUST provide pure functions using `pandas` for rolling calculations:

```python
    @staticmethod
    def rolling_sharpe(
        equity: list[EquityPoint],  # EquityPoint(timestamp, equity)
        window: int,                # number of periods (e.g., 252 for daily)
        risk_free: float = 0.0,
        min_periods: int | None = None
    ) -> list[float | None]:
        """Returns list aligned with equity points. First (window-1) are None."""
    
    @staticmethod
    def rolling_drawdown(
        equity: list[EquityPoint],
        window: int,
        min_periods: int | None = None
    ) -> list[float | None]:
        """Returns drawdown % at each point over rolling window. None for < min_periods."""
```

Uses `pandas.Series.rolling().apply()` for efficiency. `EquityPoint` from `readers.models`.

#### Scenario: Rolling Sharpe on daily equity
- GIVEN 500 daily EquityPoints, window=252
- WHEN `rolling_sharpe(equity, 252)` called
- THEN returns 500 values, first 251 are None, rest are annualized Sharpe

#### Scenario: Rolling drawdown matches peak-to-trough
- GIVEN equity curve with known peak/trough
- WHEN `rolling_drawdown(equity, 100)` called
- THEN max value matches expected max drawdown over 100-period windows

---

### Requirement: Benchmark Comparison

The system MUST provide:

```python
    @staticmethod
    def benchmark_compare(
        strategy_returns: list[float],   # daily/period returns
        benchmark_returns: list[float],  # same length, aligned
        periods_per_year: int = 252
    ) -> BenchmarkComparison:
        """Compute alpha, beta, IR, tracking error, capture ratios."""
```

Requires equal-length aligned return series. Raises `ValueError` if lengths differ or NaN present.

#### Scenario: Alpha/beta computed correctly
- GIVEN strategy returns = benchmark * 1.2 + 0.0001 (small alpha)
- WHEN `benchmark_compare()` called
- THEN `beta ≈ 1.2`, `alpha > 0` (annualized)

#### Scenario: Capture ratios
- GIVEN benchmark has both positive and negative periods
- WHEN computed
- THEN `up_capture > 1` if strategy outperforms in up markets

---

### Requirement: Monte Carlo Bands

The system MUST provide:

```python
    @staticmethod
    def monte_carlo_bands(
        trades: list[Trade],          # Trade objects with profit
        n_simulations: int = 1000,
        percentiles: list[float] = [10, 50, 90],
        initial_equity: float = 100000.0
    ) -> dict[str, list[float]]:
        """
        Returns dict: percentile -> equity curve (list of equity values per trade).
        Uses bootstrap resampling of trade profits with replacement.
        """
```

Algorithm: For each simulation, resample `len(trades)` profits with replacement, compute cumulative equity. Return percentile curves at each trade index.

#### Scenario: Monte Carlo produces percentile bands
- GIVEN 100 trades, n_simulations=1000, percentiles=[10, 50, 90]
- WHEN `monte_carlo_bands()` called
- THEN returns `{"p10": [...], "p50": [...], "p90": [...]}` each length 101 (initial + 100 trades)

#### Scenario: Deterministic with seed
- GIVEN same trades, same seed
- WHEN called twice
- THEN identical results (use `random.seed()` internally)

---

## Data Flow

```
CampaignResult / OptimizationResult / Knowledge Lake query
       │
       ├─► StatisticsAggregator.aggregate_campaigns()
       │       │
       │       ├─► Extract StatsResult from each campaign
       │       ├─► Compute AggregateStats per metric
       │       └─► Return dict[metric] -> AggregateStats
       │
       ├─► StatisticsAggregator.aggregate_wf_cycles()
       │       │
       │       └─► Extract OOS StatsResult from each cycle
       │
       ├─► StatisticsAggregator.rolling_sharpe/drawdown()
       │       │
       │       └─► pandas rolling apply on equity series
       │
       ├─► StatisticsAggregator.benchmark_compare()
       │       │
       │       └─► numpy/pandas stats on aligned returns
       │
       └─► StatisticsAggregator.monte_carlo_bands()
               │
               └─► Bootstrap resample trade profits → percentile curves
```

---

## Interface Specifications

```python
# quantlab.stats.models (extended)
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class AggregateStats(BaseModel):
    count: int
    mean: float
    median: float
    std: float
    min: float
    max: float
    percentile_25: float
    percentile_75: float
    skew: float | None = None
    kurtosis: float | None = None

    @classmethod
    def from_values(cls, values: list[float]) -> "AggregateStats": ...

class RollingMetrics(BaseModel):
    timestamps: list[datetime]
    rolling_sharpe: list[float | None]
    rolling_drawdown: list[float | None]
    window: int

class BenchmarkComparison(BaseModel):
    alpha: float
    beta: float
    information_ratio: float
    tracking_error: float
    correlation: float
    up_capture: float
    down_capture: float

# quantlab.stats.aggregation
class StatisticsAggregator:
    @staticmethod
    def aggregate_campaigns(
        campaign_results: list[CampaignResult],
        metrics: list[str] | None = None
    ) -> dict[str, AggregateStats]: ...

    @staticmethod
    def aggregate_wf_cycles(
        cycles: list[WalkForwardCycle],
        metrics: list[str] | None = None
    ) -> dict[str, AggregateStats]: ...

    @staticmethod
    def rolling_sharpe(
        equity: list[EquityPoint],
        window: int,
        risk_free: float = 0.0,
        min_periods: int | None = None
    ) -> list[float | None]: ...

    @staticmethod
    def rolling_drawdown(
        equity: list[EquityPoint],
        window: int,
        min_periods: int | None = None
    ) -> list[float | None]: ...

    @staticmethod
    def rolling_metrics(
        equity: list[EquityPoint],
        window: int,
        risk_free: float = 0.0
    ) -> RollingMetrics:
        """Convenience: returns both rolling_sharpe and rolling_drawdown in one call."""

    @staticmethod
    def benchmark_compare(
        strategy_returns: list[float],
        benchmark_returns: list[float],
        periods_per_year: int = 252
    ) -> BenchmarkComparison: ...

    @staticmethod
    def monte_carlo_bands(
        trades: list[Trade],
        n_simulations: int = 1000,
        percentiles: list[float] = [10, 50, 90],
        initial_equity: float = 100000.0,
        seed: int | None = None
    ) -> dict[str, list[float]]: ...
```

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| `aggregate_campaigns` returns AggregateStats for 5 default metrics | Unit test: 10 mock campaigns, assert dict keys and types |
| `aggregate_wf_cycles` uses OOS stats | Unit test: cycles with known OOS values, assert mean matches |
| `rolling_sharpe` first N-1 are None | Unit test: 100 points, window=30 → first 29 None |
| `rolling_drawdown` matches manual calc | Unit test: known equity curve, compare to pandas rolling max |
| `benchmark_compare` alpha/beta match expected | Unit test: synthetic returns with known alpha/beta |
| `monte_carlo_bands` returns correct structure | Unit test: assert dict keys, list lengths |
| Monte Carlo deterministic with seed | Unit test: same seed → identical output |
| No new required dependencies | Check `pyproject.toml` — only `pandas` (already in deps) |
| All methods are static, stateless | Code review: no `self` or class state used |
| Works with CampaignResult from Knowledge Lake | Integration: query campaigns (5c), aggregate, assert results |

---

## Non-Functional Requirements

- **Performance**: `aggregate_campaigns(1000 campaigns)` < 1s; `monte_carlo_bands(1000 trades, 1000 sims)` < 3s
- **Numerical precision**: Use `float64` (pandas/numpy default); `decimal` for financial aggregates if needed later
- **Dependencies**: `pandas` (existing), `numpy` (transitive), `statistics` (stdlib), `random` (stdlib)
- **Testability**: Pure functions → easy unit testing with synthetic data
- **Thread safety**: Stateless, no shared mutable state