# Statistics Engine — Delta Specification (Phase 5b-5e)

## Purpose

Extends the `StatisticsEngine` capability with new aggregate data models (`AggregateStats`, `RollingMetrics`, `BenchmarkComparison`) consumed by the new `StatisticsAggregator` class (Feature 5e). The `StatisticsEngine` class itself gains **no new methods** — aggregation is a separate stateless class.

---

## MODIFIED Requirements

### Requirement: New Models in stats.models

The system MUST add three new Pydantic models to `quantlab.stats.models`:

```python
class AggregateStats(BaseModel):
    """Aggregate statistics across multiple campaigns or WF cycles."""
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
    def from_values(cls, values: list[float]) -> "AggregateStats":
        """Compute all aggregate stats from a list of values."""
        ...

class RollingMetrics(BaseModel):
    """Rolling window metrics aligned to equity curve timestamps."""
    timestamps: list[datetime]
    rolling_sharpe: list[float | None]
    rolling_drawdown: list[float | None]
    window: int

class BenchmarkComparison(BaseModel):
    """Strategy vs benchmark comparison metrics."""
    alpha: float
    beta: float
    information_ratio: float
    tracking_error: float
    correlation: float
    up_capture: float
    down_capture: float
```

**Previously**: Only `StatsResult` existed (single-campaign metrics).

#### Scenario: AggregateStats computes correct percentiles
- GIVEN `values = [1.0, 1.5, 2.0, 2.5, 3.0]`
- WHEN `AggregateStats.from_values(values)` called
- THEN `percentile_25 == 1.5`, `percentile_75 == 2.5`, `median == 2.0`

#### Scenario: RollingMetrics first N-1 are None
- GIVEN 100 equity points, window=30
- WHEN `StatisticsAggregator.rolling_metrics()` called
- THEN `rolling_sharpe[:29]` all `None`, `[29:]` are floats

#### Scenario: BenchmarkComparison fields all populated
- GIVEN aligned strategy/benchmark returns
- WHEN `StatisticsAggregator.benchmark_compare()` called
- THEN all 7 fields present with correct types

---

### Requirement: StatisticsEngine Unchanged

The `StatisticsEngine` class in `quantlab.stats.engine` **MUST NOT** gain new public methods. All aggregation functionality lives in the new `StatisticsAggregator` class (Feature 5e, `quantlab.stats.aggregation`).

**Rationale**: Separation of concerns — `StatisticsEngine` computes single-result metrics; `StatisticsAggregator` computes cross-result statistics. Both can be used independently.

**Previously**: `StatisticsEngine` had `compute_all()`, `compute_sharpe()`, `compute_profit_factor()`, etc.

**Now**: Same methods. No additions.

#### Scenario: Existing StatisticsEngine tests pass unchanged
- GIVEN test suite for StatisticsEngine
- WHEN run after Feature 5e
- THEN all 20+ existing tests pass

---

### Requirement: StatsResult May Have Optional Extended Fields

The existing `StatsResult` model MAY optionally gain fields for forward-compatibility with aggregate output, but this is **not required** for Phase 5e.

```python
class StatsResult(BaseModel):
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    mar_ratio: float
    recovery_factor: float
    expectancy: float
    expectancy_ratio: float
    win_rate: float
    total_trades: int
    
    # OPTIONAL new fields (only if convenient for reporting):
    aggregate_stats: AggregateStats | None = None
    rolling_metrics: RollingMetrics | None = None
    benchmark_comparison: BenchmarkComparison | None = None
```

If added, they are populated by `StatisticsAggregator` when integrating with Reporting (5b), not by `StatisticsEngine`.

---

## Data Flow (New Aggregation Path)

```
CampaignResult / OptimizationResult
       │
       ├─► StatisticsAggregator.aggregate_campaigns()
       │       │
       │       ├─► Extract StatsResult from each campaign
       │       ├─► For each metric: collect list of values
       │       ├─► AggregateStats.from_values() per metric
       │       └─► Return dict[metric] → AggregateStats
       │
       ├─► StatisticsAggregator.aggregate_wf_cycles()
       │       │
       │       └─► Use cycle.out_of_sample_stats (StatsResult)
       │
       ├─► StatisticsAggregator.rolling_sharpe() / rolling_drawdown()
       │       │
       │       └─► pandas rolling on equity series
       │
       ├─► StatisticsAggregator.benchmark_compare()
       │       │
       │       └─► numpy/pandas on aligned returns
       │
       └─► StatisticsAggregator.monte_carlo_bands()
               │
               └─► Bootstrap resample trade profits
```

---

## Interface Specifications (Delta)

```python
# quantlab.stats.models (EXTENDED)
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

# StatsResult optionally extended (see above)

# quantlab.stats.engine (UNCHANGED)
class StatisticsEngine:
    def compute_all(self, trades, equity, returns, cagr, net_profit) -> StatsResult: ...
    def compute_sharpe(self, ...) -> float: ...
    def compute_profit_factor(self, ...) -> float: ...
    # ... all existing methods unchanged ...

# quantlab.stats.aggregation (NEW - Feature 5e, consumes these models)
class StatisticsAggregator:
    @staticmethod
    def aggregate_campaigns(campaign_results: list[CampaignResult], 
                            metrics: list[str] | None = None
    ) -> dict[str, AggregateStats]: ...

    @staticmethod
    def aggregate_wf_cycles(cycles: list[WalkForwardCycle],
                            metrics: list[str] | None = None
    ) -> dict[str, AggregateStats]: ...

    @staticmethod
    def rolling_sharpe(equity: list[EquityPoint], window: int, 
                       risk_free: float = 0.0, min_periods: int | None = None
    ) -> list[float | None]: ...

    @staticmethod
    def rolling_drawdown(equity: list[EquityPoint], window: int,
                         min_periods: int | None = None
    ) -> list[float | None]: ...

    @staticmethod
    def benchmark_compare(strategy_returns: list[float],
                          benchmark_returns: list[float],
                          periods_per_year: int = 252
    ) -> BenchmarkComparison: ...

    @staticmethod
    def monte_carlo_bands(trades: list[Trade],
                          n_simulations: int = 1000,
                          percentiles: list[float] = [10, 50, 90],
                          initial_equity: float = 100000.0,
                          seed: int | None = None
    ) -> dict[str, list[float]]: ...
```

---

## Acceptance Criteria (Delta)

| Criterion | Verification |
|-----------|--------------|
| `AggregateStats.from_values()` computes correct stats | Unit test: known input → assert all fields |
| `RollingMetrics` structure matches spec | Unit test: create instance, assert fields |
| `BenchmarkComparison` structure matches spec | Unit test: create instance, assert fields |
| `StatisticsEngine` has NO new public methods | Code review: class unchanged |
| All existing StatisticsEngine tests pass | Run test suite |
| New models importable from `quantlab.stats.models` | Unit test: `from quantlab.stats.models import AggregateStats` |
| `from_values()` handles edge cases (empty, single, NaN) | Unit tests for each |
| No new required dependencies | Check `pyproject.toml` |

---

## Migration Notes

- **No breaking changes** to `StatisticsEngine` or `StatsResult`
- **New models** added to `quantlab.stats.models` — safe additive change
- **Aggregation logic** in separate `StatisticsAggregator` (Feature 5e) — can be developed/tested independently
- **Reporting integration** (Feature 5b) will consume `AggregateStats` for cross-campaign reports
- **Knowledge Query integration** (Feature 5c) will use `AggregateStats` for lake-wide analytics

---

## Related Files Modified

| File | Change |
|------|--------|
| `sdk/quantlab/stats/models.py` | Add 3 new model classes |
| `sdk/quantlab/stats/__init__.py` | Export new models |
| `tests/test_stats_engine.py` | Verify no regression (existing tests pass) |
| `tests/test_stats_aggregation.py` | New tests for new models (Feature 5e) |