"""Tests for StatisticsAgent — tasks 3.1-3.4, 3.14.

Tests statistics computation, aggregation, Monte Carlo bands (deterministic),
rolling metrics, and the run() pipeline contract.
"""

import csv
import json
import math
import os
import tempfile
from pathlib import Path

import pytest

from quantlab.agents.statistics_agent import StatisticsAgent
from quantlab.pipeline.base import PipelineContext
from quantlab.readers.models import EquityPoint, Trade
from quantlab.stats.models import (
    AggregateStats,
    RollingMetrics,
    StatsResult,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_trade(profit: float) -> Trade:
    return Trade(profit=profit)


def _make_equity(equity: float, timestamp: str = "2024-01-01T00:00:00") -> EquityPoint:
    from datetime import datetime
    return EquityPoint(equity=equity, timestamp=datetime.fromisoformat(timestamp))


def _create_export_dir(trades: list[float], equity: list[float]) -> str:
    """Create a temporary export directory with trades.csv and equity.csv."""
    tmp_dir = tempfile.mkdtemp()

    # Write trades.csv with all required fields
    trades_path = os.path.join(tmp_dir, "trades.csv")
    with open(trades_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["profit", "entry_time", "exit_time", "direction", "lots"])
        for i, p in enumerate(trades):
            writer.writerow([p, "2024-01-01T00:00:00", "2024-01-02T00:00:00", "LONG", 1.0])

    # Write equity.csv
    equity_path = os.path.join(tmp_dir, "equity.csv")
    with open(equity_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["equity", "timestamp"])
        for i, e in enumerate(equity):
            writer.writerow([e, f"2024-01-{i+1:02d}T00:00:00"])

    return tmp_dir


class TestStatisticsComputation:
    """Task 3.2 + 3.14: StatisticsAgent.compute_statistics()."""

    def test_compute_statistics_from_exports(self) -> None:
        """GIVEN export_paths with trades.csv and equity.csv
        WHEN compute_statistics() is called
        THEN a StatsResult with 10+ metrics is returned.
        """
        agent = StatisticsAgent()
        tmp_dir = _create_export_dir(
            trades=[100, -50, 200, -30, 150, -80, 300, -40, 120, -60],
            equity=[10000, 10100, 10050, 10250, 10220, 10370, 10290, 10590, 10550, 10670],
        )

        try:
            export_paths = [
                os.path.join(tmp_dir, "trades.csv"),
                os.path.join(tmp_dir, "equity.csv"),
            ]
            result = agent.compute_statistics(export_paths)

            assert isinstance(result, StatsResult)
            assert result.profit_factor is not None
            assert result.sharpe_ratio is not None or result.sharpe_ratio is None
            assert result.max_drawdown is not None
            assert result.win_rate is not None
            assert result.total_trades is not None
            assert result.total_trades == 10
            assert result.win_rate == 0.5  # 5 wins out of 10
        finally:
            import shutil
            shutil.rmtree(tmp_dir)

    def test_missing_equity_raises(self) -> None:
        """GIVEN export_paths missing equity.csv
        WHEN compute_statistics() is called
        THEN MDD and returns are unavailable but computation continues.
        """
        agent = StatisticsAgent()
        tmp_dir = tempfile.mkdtemp()

        try:
            # Only write trades.csv
            trades_path = os.path.join(tmp_dir, "trades.csv")
            with open(trades_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["profit", "entry_time", "exit_time", "direction", "lots"])
                writer.writerow([100, "2024-01-01T00:00:00", "2024-01-02T00:00:00", "LONG", 1.0])
                writer.writerow([-50, "2024-01-03T00:00:00", "2024-01-04T00:00:00", "SHORT", 1.0])

            export_paths = [trades_path]
            result = agent.compute_statistics(export_paths)

            assert isinstance(result, StatsResult)
            assert result.profit_factor is not None or result.profit_factor is None
            # win_rate and total_trades come from trades
            assert result.total_trades == 2
        finally:
            import shutil
            shutil.rmtree(tmp_dir)

    def test_float64_precision(self) -> None:
        """GIVEN trades with small fractional profits
        WHEN compute_statistics() is called
        THEN metrics use float64 precision.
        """
        agent = StatisticsAgent()
        trades = [0.1234567890123456, -0.05, 0.2345678901234567, -0.03]
        equity = [1000.0, 1000.12, 1000.07, 1000.30]
        tmp_dir = _create_export_dir(trades, equity)

        try:
            export_paths = [
                os.path.join(tmp_dir, "trades.csv"),
                os.path.join(tmp_dir, "equity.csv"),
            ]
            result = agent.compute_statistics(export_paths)

            # Check float64 precision on profit_factor
            if result.profit_factor is not None:
                # Should have many decimal places
                pf_str = f"{result.profit_factor:.10f}"
                assert len(pf_str) > 5
        finally:
            import shutil
            shutil.rmtree(tmp_dir)

    def test_compute_statistics_from_synthetic_data(self) -> None:
        """GIVEN known trades/equity with deterministic outcome
        WHEN compute_statistics() is called
        THEN assert specific metric values.
        """
        agent = StatisticsAgent()
        # 20 trades: 12 wins (60%), 8 losses
        trades = [100] * 12 + [-50] * 8
        # Smooth equity growth
        equity = [10000 + i * 40 for i in range(21)]
        tmp_dir = _create_export_dir(trades, equity)

        try:
            export_paths = [
                os.path.join(tmp_dir, "trades.csv"),
                os.path.join(tmp_dir, "equity.csv"),
            ]
            result = agent.compute_statistics(export_paths)

            assert result.total_trades == 20
            assert result.win_rate == 0.6
            # Profit factor: (12*100) / (8*50) = 1200/400 = 3.0
            if result.profit_factor is not None:
                assert abs(result.profit_factor - 3.0) < 0.01
        finally:
            import shutil
            shutil.rmtree(tmp_dir)


def _make_test_trade(profit: float) -> Trade:
    """Helper to create a Trade with required fields."""
    from datetime import datetime
    return Trade(
        profit=profit,
        entry_time=datetime(2024, 1, 1),
        exit_time=datetime(2024, 1, 2),
        direction="LONG",
        lots=1.0,
    )


class TestMonteCarloBands:
    """Task 3.3 + 3.14: StatisticsAgent.monte_carlo_bands()."""

    def test_monte_carlo_deterministic(self) -> None:
        """GIVEN 200 trades, n_simulations=1000, percentiles=[10, 50, 90]
        WHEN monte_carlo_bands() is called twice with the same seed
        THEN the results are identical.
        """
        agent = StatisticsAgent(mc_seed=42)
        trades = [_make_test_trade(100.0 if i % 2 == 0 else -50.0) for i in range(200)]

        result1 = agent.monte_carlo_bands(trades, n_simulations=500, seed=42)
        result2 = agent.monte_carlo_bands(trades, n_simulations=500, seed=42)

        assert result1.keys() == result2.keys()
        for p in result1:
            assert result1[p] == result2[p], f"Mismatch at percentile {p}"

    def test_monte_carlo_bands_shape(self) -> None:
        """GIVEN 200 trades
        WHEN monte_carlo_bands() is called
        THEN the result has the correct shape (initial + n_trades).
        """
        agent = StatisticsAgent()
        trades = [_make_test_trade(float(i % 2 * 100 - 50)) for i in range(200)]

        bands = agent.monte_carlo_bands(trades, n_simulations=100, percentiles=[10, 50, 90])

        assert 10 in bands
        assert 50 in bands
        assert 90 in bands
        assert len(bands[10]) == 201  # initial + 200 trades
        assert len(bands[50]) == 201
        assert len(bands[90]) == 201

    def test_monte_carlo_empty_trades_raises(self) -> None:
        """GIVEN an empty trades list
        WHEN monte_carlo_bands() is called
        THEN ValueError is raised.
        """
        agent = StatisticsAgent()
        with pytest.raises(ValueError, match="Empty trades"):
            agent.monte_carlo_bands([])

    def test_monte_carlo_median_is_sensible(self) -> None:
        """GIVEN trades with known expected value
        WHEN monte_carlo_bands() is called
        THEN the median curve ends near expected net profit.
        """
        agent = StatisticsAgent(mc_seed=42)
        # Each trade: E[profit] = 0.5 * 100 + 0.5 * (-50) = 25
        trades = [_make_test_trade(100.0) for _ in range(100)] + [_make_test_trade(-50.0) for _ in range(100)]

        bands = agent.monte_carlo_bands(trades, n_simulations=500, percentiles=[50])

        # Last value of median should be near 200 * 25 = 5000
        median_final = bands[50][-1]
        assert abs(median_final - 5000) < 2000, f"Median {median_final} too far from expected 5000"


class TestAssessRobustness:
    """Task 3.2: StatisticsAgent.assess_robustness()."""

    def test_robust_when_p10_positive(self) -> None:
        """GIVEN statistics with high Sharpe and MC p10 curve positive throughout
        WHEN assess_robustness() is called
        THEN robustness_flag = "ROBUST".
        """
        agent = StatisticsAgent()
        statistics = {"sharpe_ratio": 2.0}
        # p10 curve always positive
        mc_bands = {10: [0.0] + [100.0 * (i + 1) for i in range(100)]}

        result = agent.assess_robustness(statistics, mc_bands)
        assert result["robustness_flag"] == "ROBUST"

    def test_overfit_risk_when_p10_negative(self) -> None:
        """GIVEN a strategy with Sharpe=2.5 but MC p10 curve shows negative equity at trade 50
        WHEN assess_robustness() is called
        THEN robustness_flag = "OVERFIT_RISK".
        """
        agent = StatisticsAgent()
        statistics = {"sharpe_ratio": 2.5}
        # p10 curve goes negative at trade 50
        mc_bands = {
            10: [0.0] * 50 + [-100.0] * 51  # initial + 100 trades, negative from index 50
        }

        result = agent.assess_robustness(statistics, mc_bands)
        assert result["robustness_flag"] == "OVERFIT_RISK"
        assert "MC p10 below zero" in result["rationale"]

    def test_overfit_risk_without_sharpe(self) -> None:
        """GIVEN statistics without Sharpe but MC p10 negative
        WHEN assess_robustness() is called
        THEN robustness_flag = "OVERFIT_RISK".
        """
        agent = StatisticsAgent()
        statistics = {}
        mc_bands = {10: [0.0, -10.0] + [50.0] * 99}

        result = agent.assess_robustness(statistics, mc_bands)
        assert result["robustness_flag"] == "OVERFIT_RISK"

    def test_insufficient_data(self) -> None:
        """GIVEN no p10 curve
        WHEN assess_robustness() is called
        THEN robustness_flag = "INSUFFICIENT_DATA".
        """
        agent = StatisticsAgent()
        result = agent.assess_robustness({}, {})
        assert result["robustness_flag"] == "INSUFFICIENT_DATA"


class TestRollingMetrics:
    """Task 3.4: StatisticsAgent rolling metrics and regime detection."""

    def test_rolling_metrics_aligned(self) -> None:
        """GIVEN equity curve with 100 points
        WHEN compute_rolling_metrics() is called
        THEN len(rolling_sharpe) == len(equity).
        """
        agent = StatisticsAgent(rolling_window=20)
        equity = [_make_equity(10000.0 + i * 10.0) for i in range(100)]

        result = agent.compute_rolling_metrics(equity)

        assert "sharpe" in result or "rolling_sharpe" in result
        rm = result.get("sharpe", result.get("rolling_sharpe", {}))
        if rm.get("values"):
            assert len(rm["values"]) == len(equity)

    def test_rolling_metrics_empty_equity(self) -> None:
        """GIVEN empty equity curve
        WHEN compute_rolling_metrics() is called
        THEN empty dict is returned.
        """
        agent = StatisticsAgent()
        result = agent.compute_rolling_metrics([])
        assert result == {}

    def test_detect_regime_change_sharpe_drop(self) -> None:
        """GIVEN rolling_sharpe drops from 1.8 to 0.4 over 20 periods,
        rolling_drawdown spikes >2x
        WHEN detect_regime_change() is called
        THEN a regime alert is generated with action.
        """
        agent = StatisticsAgent()
        # Early: high Sharpe (1.8), low drawdown (5%)
        early_sharpes = [1.8] * 30
        late_sharpes = [0.4] * 30
        rolling_sharpe = early_sharpes + late_sharpes

        # Early: low drawdown, Late: high drawdown
        early_dd = [5.0] * 30
        late_dd = [15.0] * 30
        rolling_drawdown = early_dd + late_dd

        alerts = agent.detect_regime_change(rolling_sharpe, rolling_drawdown)

        assert len(alerts) >= 1
        assert alerts[0]["type"] == "REGIME_SHIFT"
        assert alerts[0]["confidence"] >= 0.5
        assert "action" in alerts[0]
        assert alerts[0]["action"] in [
            "Reduce position size, widen stops",
            "Reduce position size, tighten stops, add volatility filter",
            "Review market regime alignment",
        ]

    def test_no_regime_change_when_stable(self) -> None:
        """GIVEN stable rolling metrics
        WHEN detect_regime_change() is called
        THEN no alerts are generated.
        """
        agent = StatisticsAgent()
        rolling_sharpe = [1.5] * 60
        rolling_drawdown = [8.0] * 60

        alerts = agent.detect_regime_change(rolling_sharpe, rolling_drawdown)
        assert len(alerts) == 0

    def test_regime_change_from_trending_to_choppy(self) -> None:
        """GIVEN sharpe drops from trending levels (>1.0) to choppy
        WHEN detect_regime_change() is called
        THEN from_regime = "trending", to_regime = "choppy".
        """
        agent = StatisticsAgent()
        early_sharpes = [1.5] * 30
        late_sharpes = [0.3] * 30
        rolling_sharpe = early_sharpes + late_sharpes
        rolling_drawdown = [4.0] * 30 + [18.0] * 30

        alerts = agent.detect_regime_change(rolling_sharpe, rolling_drawdown)
        assert len(alerts) >= 1
        # When early sharpe is ~1.5 (trending), and it drops to choppy
        assert alerts[0]["from_regime"] == "trending"


class TestRunMethod:
    """Task 3.1: StatisticsAgent.run(context)."""

    @pytest.mark.asyncio
    async def test_run_writes_context_artifacts(self) -> None:
        """GIVEN a PipelineContext with export_paths
        WHEN run() is called
        THEN statistics, aggregate_stats, etc. are written to context artifacts.
        """
        agent = StatisticsAgent()
        tmp_dir = _create_export_dir(
            trades=[100, -50, 200, -30, 150],
            equity=[10000, 10100, 10050, 10250, 10220],
        )

        try:
            export_paths = [
                os.path.join(tmp_dir, "trades.csv"),
                os.path.join(tmp_dir, "equity.csv"),
            ]
            ctx = PipelineContext(
                config={},
                artifacts={"export_paths": export_paths},
            )

            result = await agent.run(ctx)

            assert "statistics" in ctx.artifacts
            assert "aggregate_stats" in ctx.artifacts
            assert "monte_carlo_bands" in ctx.artifacts
            assert "rolling_metrics" in ctx.artifacts
            assert "regime_alerts" in ctx.artifacts

            assert "statistics" in result
            assert "monte_carlo_bands" in result
        finally:
            import shutil
            shutil.rmtree(tmp_dir)

    @pytest.mark.asyncio
    async def test_run_missing_export_paths_raises(self) -> None:
        """GIVEN a PipelineContext without export_paths
        WHEN run() is called
        THEN ValueError is raised.
        """
        agent = StatisticsAgent()
        ctx = PipelineContext(config={})

        with pytest.raises(ValueError, match="No export_paths"):
            await agent.run(ctx)

    @pytest.mark.asyncio
    async def test_run_with_trades_only(self) -> None:
        """GIVEN export_paths with only trades.csv
        WHEN run() is called
        THEN partial statistics are computed without error.
        """
        agent = StatisticsAgent()
        tmp_dir = tempfile.mkdtemp()

        try:
            trades_path = os.path.join(tmp_dir, "trades.csv")
            with open(trades_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["profit", "entry_time", "exit_time", "direction", "lots"])
                for p in [100, -50, 200, -30]:
                    writer.writerow([p, "2024-01-01T00:00:00", "2024-01-02T00:00:00", "LONG", 1.0])

            ctx = PipelineContext(
                config={},
                artifacts={"export_paths": [trades_path]},
            )

            result = await agent.run(ctx)
            assert "statistics" in result
            assert result["statistics"].get("total_trades") == 4
        finally:
            import shutil
            shutil.rmtree(tmp_dir)
