"""Tests for StatisticsAggregator — aggregation, rolling, benchmark, Monte Carlo."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantlab.phase4.optimizer import WalkForwardCycle
from quantlab.phase4.campaign_orchestrator import CampaignResult
from quantlab.readers.models import Trade, EquityPoint
from quantlab.stats.aggregation import StatisticsAggregator
from quantlab.stats.models import (
    AggregateStats,
    RollingMetrics,
    BenchmarkComparison,
)


# ── Fixtures ────────────────────────────────────────────────────────────────────


def _make_trades(profits: list[float]) -> list[Trade]:
    """Create a list of trades with given profits."""
    base_time = datetime(2024, 1, 1, 9, 0, 0)
    trades = []
    for i, p in enumerate(profits):
        trades.append(
            Trade(
                entry_time=base_time + timedelta(hours=i * 4),
                exit_time=base_time + timedelta(hours=i * 4 + 2),
                direction="LONG",
                lots=1.0,
                profit=p,
                drawdown=abs(min(p, 0)) * 0.5,
            )
        )
    return trades


def _make_equity(values: list[float]) -> list[EquityPoint]:
    """Create equity curve points."""
    base_time = datetime(2024, 1, 1, 9, 0, 0)
    return [
        EquityPoint(timestamp=base_time + timedelta(days=i), equity=v)
        for i, v in enumerate(values)
    ]


def _make_campaign_result(
    trades: list[Trade] | None = None,
    equity: list[EquityPoint] | None = None,
    stats: dict | None = None,
) -> CampaignResult:
    """Create a CampaignResult with optional trades/equity/stats."""
    return CampaignResult(
        campaign_name="test_campaign",
        trades=trades or [],
        equity=equity or [],
        statistics=stats or {},
    )


# ── AggregateStats Tests ───────────────────────────────────────────────────────


class TestAggregateStats:
    """Tests for AggregateStats model."""

    def test_creation(self):
        stats = AggregateStats(
            mean=1.5,
            median=1.4,
            std=0.3,
            min=1.0,
            max=2.0,
            p25=1.2,
            p75=1.8,
            count=10,
        )
        assert stats.mean == 1.5
        assert stats.count == 10

    def test_validation_requires_all_fields(self):
        with pytest.raises(Exception):
            AggregateStats(mean=1.0)  # Missing required fields


# ── StatisticsAggregator.aggregate_campaigns ───────────────────────────────────


class TestAggregateCampaigns:
    """Tests for aggregate_campaigns method."""

    def test_aggregate_single_campaign(self):
        """Aggregate stats from a single campaign."""
        trades = _make_trades([100, -50, 200, -30, 150])
        equity = _make_equity([10000, 10100, 10050, 10250, 10220, 10370])
        camp = _make_campaign_result(trades=trades, equity=equity)

        result = StatisticsAggregator.aggregate_campaigns([camp])

        # Should have all 6 metrics
        expected_metrics = {"sharpe", "profit_factor", "max_drawdown", "win_rate", "expectancy", "total_trades"}
        assert set(result.keys()) == expected_metrics

        # Each metric should be an AggregateStats
        for metric_name, stats in result.items():
            assert isinstance(stats, AggregateStats)
            assert stats.count == 1
            assert stats.mean == stats.median == stats.min == stats.max == stats.p25 == stats.p75

    def test_aggregate_multiple_campaigns(self):
        """Aggregate stats across multiple campaigns."""
        # Campaign 1: good performance
        trades1 = _make_trades([100, -50, 200, -30, 150])
        equity1 = _make_equity([10000, 10100, 10050, 10250, 10220, 10370])
        camp1 = _make_campaign_result(trades=trades1, equity=equity1)

        # Campaign 2: worse performance
        trades2 = _make_trades([50, -100, 80, -40, 60])
        equity2 = _make_equity([10000, 10050, 9950, 10030, 9990, 10050])
        camp2 = _make_campaign_result(trades=trades2, equity=equity2)

        result = StatisticsAggregator.aggregate_campaigns([camp1, camp2])

        # Count should be 2 for all metrics
        for stats in result.values():
            assert stats.count == 2
            assert stats.min <= stats.mean <= stats.max
            assert stats.p25 <= stats.median <= stats.p75

    def test_empty_list_returns_empty_dict(self):
        """Empty campaign list returns empty dict."""
        result = StatisticsAggregator.aggregate_campaigns([])
        assert result == {}

    def test_campaign_with_empty_trades(self):
        """Campaign with empty trades should still aggregate (metrics will be NaN or inf)."""
        camp = _make_campaign_result(trades=[], equity=_make_equity([10000, 10100]))
        result = StatisticsAggregator.aggregate_campaigns([camp])

        # Should still have metrics, but some may be inf/nan
        assert "profit_factor" in result
        assert "sharpe" in result


# ── StatisticsAggregator.aggregate_wf_cycles ───────────────────────────────────


class TestAggregateWFCycles:
    """Tests for aggregate_wf_cycles method."""

    def test_aggregate_wf_cycles_basic(self):
        """Aggregate OOS metrics from walk-forward cycles."""
        cycles = [
            WalkForwardCycle(
                cycle=1,
                in_sample_start="2020-01-01",
                in_sample_end="2020-06-30",
                out_sample_start="2020-07-01",
                out_sample_end="2020-12-31",
                metrics={"Sharpe": 1.5, "ProfitFactor": 1.8, "MaxDrawdown": 5.0, "WinRate": 0.6, "Expectancy": 25.0, "TotalTrades": 50},
            ),
            WalkForwardCycle(
                cycle=2,
                in_sample_start="2020-07-01",
                in_sample_end="2020-12-31",
                out_sample_start="2021-01-01",
                out_sample_end="2021-06-30",
                metrics={"Sharpe": 1.2, "ProfitFactor": 1.5, "MaxDrawdown": 8.0, "WinRate": 0.55, "Expectancy": 20.0, "TotalTrades": 45},
            ),
            WalkForwardCycle(
                cycle=3,
                in_sample_start="2021-01-01",
                in_sample_end="2021-06-30",
                out_sample_start="2021-07-01",
                out_sample_end="2021-12-31",
                metrics={"Sharpe": 1.8, "ProfitFactor": 2.0, "MaxDrawdown": 4.0, "WinRate": 0.65, "Expectancy": 30.0, "TotalTrades": 55},
            ),
        ]

        result = StatisticsAggregator.aggregate_wf_cycles(cycles)

        expected_metrics = {"sharpe", "profit_factor", "max_drawdown", "win_rate", "expectancy", "total_trades"}
        assert set(result.keys()) == expected_metrics

        for stats in result.values():
            assert stats.count == 3
            assert stats.min <= stats.median <= stats.max

        # Check specific values
        assert result["sharpe"].mean == pytest.approx((1.5 + 1.2 + 1.8) / 3)
        assert result["profit_factor"].mean == pytest.approx((1.8 + 1.5 + 2.0) / 3)

    def test_empty_cycles_returns_empty(self):
        """Empty cycle list returns empty dict."""
        result = StatisticsAggregator.aggregate_wf_cycles([])
        assert result == {}

    def test_single_cycle(self):
        """Single cycle returns stats with count=1."""
        cycles = [
            WalkForwardCycle(
                cycle=1,
                in_sample_start="2020-01-01",
                in_sample_end="2020-06-30",
                out_sample_start="2020-07-01",
                out_sample_end="2020-12-31",
                metrics={"Sharpe": 1.5, "ProfitFactor": 1.8},
            )
        ]
        result = StatisticsAggregator.aggregate_wf_cycles(cycles)
        assert result["sharpe"].count == 1
        assert result["sharpe"].mean == 1.5


# ── Rolling Sharpe Tests ───────────────────────────────────────────────────────


class TestRollingSharpe:
    """Tests for rolling_sharpe method."""

    def test_rolling_sharpe_basic(self):
        """Rolling Sharpe with window=5 on simple equity curve."""
        # Create equity with known returns
        equity = _make_equity([10000, 10100, 10200, 10150, 10250, 10300, 10400, 10350, 10450, 10500])
        window = 5

        result = StatisticsAggregator.rolling_sharpe(equity, window=window)

        assert isinstance(result, RollingMetrics)
        assert result.window == window
        assert result.metric_name == "rolling_sharpe"
        assert len(result.timestamps) == len(equity)
        assert len(result.values) == len(equity)

        # First window-1 values should be NaN
        for i in range(window - 1):
            assert result.values[i] is None or math.isnan(result.values[i]) if result.values[i] is not None else True

        # Values from window-1 onwards should be floats
        for i in range(window - 1, len(equity)):
            assert result.values[i] is not None
            assert isinstance(result.values[i], float)

    def test_rolling_sharpe_window_larger_than_data(self):
        """Window larger than data returns all NaN."""
        equity = _make_equity([10000, 10100, 10200])
        result = StatisticsAggregator.rolling_sharpe(equity, window=10)

        assert len(result.values) == 3
        for v in result.values:
            assert v is None or math.isnan(v) if v is not None else True

    def test_rolling_sharpe_empty_equity(self):
        """Empty equity raises ValueError."""
        with pytest.raises(ValueError, match="Empty equity"):
            StatisticsAggregator.rolling_sharpe([], window=5)

    def test_rolling_sharpe_single_point(self):
        """Single equity point raises ValueError (need at least 2 for returns)."""
        equity = _make_equity([10000])
        with pytest.raises(ValueError, match=r"[Aa]t least 2"):
            StatisticsAggregator.rolling_sharpe(equity, window=2)


# ── Rolling Drawdown Tests ─────────────────────────────────────────────────────


class TestRollingDrawdown:
    """Tests for rolling_drawdown method."""

    def test_rolling_drawdown_basic(self):
        """Rolling max drawdown over window."""
        equity = _make_equity([10000, 10100, 10200, 10000, 9900, 10050, 10200, 10100])
        window = 4

        result = StatisticsAggregator.rolling_drawdown(equity, window=window)

        assert isinstance(result, RollingMetrics)
        assert result.window == window
        assert result.metric_name == "rolling_drawdown"
        assert len(result.values) == len(equity)

        # First window-1 should be NaN
        for i in range(window - 1):
            assert result.values[i] is None or (isinstance(result.values[i], float) and math.isnan(result.values[i]))

        # Drawdowns should be >= 0
        for v in result.values:
            if v is not None and not math.isnan(v):
                assert v >= 0

    def test_rolling_drawdown_monotonic_equity(self):
        """Monotonically increasing equity has zero drawdown."""
        equity = _make_equity([10000, 10100, 10200, 10300, 10400])
        result = StatisticsAggregator.rolling_drawdown(equity, window=3)

        for v in result.values:
            if v is not None and not math.isnan(v):
                assert v == 0.0

    def test_rolling_drawdown_empty_equity(self):
        """Empty equity raises ValueError."""
        with pytest.raises(ValueError, match="Empty equity"):
            StatisticsAggregator.rolling_drawdown([], window=5)


# ── Rolling Metrics Generic Tests ──────────────────────────────────────────────


class TestRollingMetrics:
    """Tests for generic rolling_metrics method."""

    def test_rolling_metrics_multiple(self):
        """Compute multiple rolling metrics at once."""
        equity = _make_equity([10000, 10100, 10200, 10000, 9900, 10050, 10200, 10100, 10300, 10400])
        metrics = ["sharpe", "drawdown", "return", "volatility"]

        results = StatisticsAggregator.rolling_metrics(equity, window=5, metrics=metrics)

        assert set(results.keys()) == set(metrics)
        for name, result in results.items():
            assert isinstance(result, RollingMetrics)
            assert result.window == 5
            assert len(result.values) == len(equity)

    def test_rolling_metrics_unknown_raises(self):
        """Unknown metric name raises ValueError."""
        equity = _make_equity([10000, 10100, 10200])
        with pytest.raises(ValueError, match="Unknown metric"):
            StatisticsAggregator.rolling_metrics(equity, window=2, metrics=["unknown"])

    def test_rolling_metrics_empty_list(self):
        """Empty metrics list returns empty dict."""
        equity = _make_equity([10000, 10100])
        results = StatisticsAggregator.rolling_metrics(equity, window=2, metrics=[])
        assert results == {}


# ── Benchmark Comparison Tests ─────────────────────────────────────────────────


class TestBenchmarkCompare:
    """Tests for benchmark_compare method."""

    def test_benchmark_compare_known_values(self):
        """Test with synthetic data with known alpha/beta."""
        # Strategy: 10% excess return, beta=1.2
        # Benchmark: 8% return
        np.random.seed(42)
        bench_returns = np.random.normal(0.0008, 0.01, 252)  # ~8% annual, 1% daily vol
        strat_returns = bench_returns * 1.2 + np.random.normal(0.0002, 0.005, 252)  # beta=1.2, alpha~5%

        result = StatisticsAggregator.benchmark_compare(strat_returns.tolist(), bench_returns.tolist())

        assert isinstance(result, BenchmarkComparison)
        # Beta should be close to 1.2
        assert result.beta == pytest.approx(1.2, abs=0.2)
        # Alpha should be positive
        assert result.alpha > 0
        # Correlation should be high
        assert result.correlation > 0.5
        # Tracking error should be reasonable
        assert result.tracking_error > 0
        # Info ratio should be positive (positive alpha)
        assert result.information_ratio > 0

    def test_benchmark_compare_length_mismatch(self):
        """Mismatched return series lengths raises ValueError."""
        with pytest.raises(ValueError, match="length mismatch"):
            StatisticsAggregator.benchmark_compare([0.01, 0.02], [0.01])

    def test_benchmark_compare_empty_raises(self):
        """Empty return series raises ValueError."""
        with pytest.raises(ValueError, match="Empty return series"):
            StatisticsAggregator.benchmark_compare([], [])

    def test_benchmark_compare_zero_var_benchmark(self):
        """Zero variance benchmark returns NaN beta."""
        bench = [0.01] * 100  # constant returns
        strat = [0.01 + np.random.normal(0, 0.001) for _ in range(100)]
        result = StatisticsAggregator.benchmark_compare(strat, bench)
        assert math.isnan(result.beta) or result.beta == float("inf") or result.beta == float("-inf")


# ── Monte Carlo Bands Tests ────────────────────────────────────────────────────


class TestMonteCarloBands:
    """Tests for monte_carlo_bands method."""

    def test_monte_carlo_bands_deterministic(self):
        """Same seed produces identical results."""
        trades = _make_trades([100, -50, 200, -30, 150, -20, 80, -40, 120, -10])

        result1 = StatisticsAggregator.monte_carlo_bands(trades, n_simulations=100, seed=42)
        result2 = StatisticsAggregator.monte_carlo_bands(trades, n_simulations=100, seed=42)

        assert result1 == result2

    def test_monte_carlo_bands_percentiles(self):
        """Returns specified percentiles."""
        trades = _make_trades([100, -50, 200, -30, 150])
        percentiles = [10, 25, 50, 75, 90]

        result = StatisticsAggregator.monte_carlo_bands(trades, n_simulations=500, percentiles=percentiles, seed=42)

        assert set(result.keys()) == set(percentiles)
        # Percentiles should be ordered
        assert result[10] <= result[50] <= result[90]

    def test_monte_carlo_bands_default_percentiles(self):
        """Default percentiles are [10, 50, 90]."""
        trades = _make_trades([100, -50, 200, -30, 150])
        result = StatisticsAggregator.monte_carlo_bands(trades, n_simulations=100, seed=42)

        assert set(result.keys()) == {10, 50, 90}

    def test_monte_carlo_bands_single_trade(self):
        """Single trade works (trivial bootstrap)."""
        trades = _make_trades([100])
        result = StatisticsAggregator.monte_carlo_bands(trades, n_simulations=100, seed=42)

        # All simulations give the same result
        assert result[10] == result[50] == result[90] == 100.0

    def test_monte_carlo_bands_empty_raises(self):
        """Empty trades raises ValueError."""
        with pytest.raises(ValueError, match="Empty trades"):
            StatisticsAggregator.monte_carlo_bands([], n_simulations=100)

    def test_monte_carlo_bands_different_seeds_different_results(self):
        """Different seeds produce different results (with high probability)."""
        trades = _make_trades([100, -50, 200, -30, 150, -20, 80, -40, 120, -10])

        result1 = StatisticsAggregator.monte_carlo_bands(trades, n_simulations=500, seed=42)
        result2 = StatisticsAggregator.monte_carlo_bands(trades, n_simulations=500, seed=123)

        # Very unlikely to be identical with different seeds
        assert result1 != result2


# ── Integration / Edge Case Tests ──────────────────────────────────────────────


class TestIntegration:
    """Integration tests combining multiple methods."""

    def test_aggregate_then_rolling(self):
        """Aggregate campaigns then compute rolling on combined equity."""
        # Create multiple campaigns
        camps = []
        for i in range(3):
            base = 10000 + i * 100
            trades = _make_trades([100, -50, 200, -30, 150])
            equity = _make_equity([base + j * 50 for j in range(10)])
            camps.append(_make_campaign_result(trades=trades, equity=equity))

        # Aggregate
        agg = StatisticsAggregator.aggregate_campaigns(camps)
        assert all(s.count == 3 for s in agg.values())

        # Rolling on one campaign's equity
        roll = StatisticsAggregator.rolling_sharpe(camps[0].equity, window=5)
        assert len(roll.values) == 10

    def test_wf_cycles_to_aggregate(self):
        """Walk-forward cycles can be aggregated."""
        cycles = [
            WalkForwardCycle(
                cycle=i,
                in_sample_start="2020-01-01",
                in_sample_end="2020-06-30",
                out_sample_start="2020-07-01",
                out_sample_end="2020-12-31",
                metrics={"Sharpe": 1.0 + i * 0.1, "ProfitFactor": 1.5, "MaxDrawdown": 5.0, "WinRate": 0.6, "Expectancy": 25.0, "TotalTrades": 50},
            )
            for i in range(1, 6)
        ]

        result = StatisticsAggregator.aggregate_wf_cycles(cycles)
        assert result["sharpe"].count == 5
        assert result["sharpe"].mean == pytest.approx(1.3)  # (1.1+1.2+1.3+1.4+1.5)/5


# ── NaN/Edge Case Handling ─────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge case handling."""

    def test_aggregate_with_nan_stats(self):
        """Campaigns with NaN statistics handled gracefully."""
        camp1 = _make_campaign_result(stats={"sharpe": 1.5, "profit_factor": 2.0})
        camp2 = _make_campaign_result(stats={"sharpe": float("nan"), "profit_factor": 1.5})

        result = StatisticsAggregator.aggregate_campaigns([camp1, camp2])

        # Should handle NaN gracefully (numpy mean ignores NaN by default? No, it propagates)
        # Let's verify it doesn't crash
        assert "sharpe" in result

    def test_rolling_with_constant_equity(self):
        """Rolling metrics on constant equity."""
        equity = _make_equity([10000] * 10)
        result = StatisticsAggregator.rolling_sharpe(equity, window=3)

        # Sharpe of zero-return series should be 0 or inf depending on implementation
        for v in result.values:
            if v is not None and not math.isnan(v):
                assert v == 0.0 or math.isinf(v)

    def test_benchmark_compare_perfect_correlation(self):
        """Perfect correlation gives correlation=1."""
        returns = [0.01] * 100
        result = StatisticsAggregator.benchmark_compare(returns, returns)
        assert result.correlation == pytest.approx(1.0)
        assert result.beta == pytest.approx(1.0)
        assert result.alpha == pytest.approx(0.0)
        assert result.tracking_error == pytest.approx(0.0)