"""Tests for AnalysisEngine — metrics mapping and overfit heuristics."""

from __future__ import annotations

import pytest

from quantlab.analysis.engine import AnalysisEngine, AnalysisThresholds
from quantlab.analysis.models import StrategyAnalysis
from quantlab.readers.models import StrategySummary


class TestAnalysisThresholds:
    """Tests for AnalysisThresholds defaults and validation."""

    def test_defaults(self) -> None:
        """GIVEN no custom thresholds
        WHEN creating AnalysisThresholds
        THEN sensible defaults are set.
        """
        t = AnalysisThresholds()
        assert t.min_trades == 50
        assert t.extreme_pf == 3.0
        assert t.extreme_sharpe == 2.0
        assert t.oos_is_threshold == 0.7

    def test_weights_must_sum_to_one(self) -> None:
        """GIVEN weights that do not sum to 1.0
        WHEN creating AnalysisThresholds
        THEN a ValueError is raised.
        """
        with pytest.raises(ValueError, match="must sum to 1.0"):
            AnalysisThresholds(pf_weight=0.5, sharpe_weight=0.5)


class TestAnalysisEngineMetrics:
    """Tests for metric mapping from StrategySummary to StatsResult."""

    def setup_method(self) -> None:
        self.engine = AnalysisEngine()

    def test_absent_columns_map_to_none(self) -> None:
        """GIVEN a StrategySummary with no optional metrics
        WHEN the engine analyses it
        THEN all StatsResult fields are None (except total_trades if provided).
        """
        strategy = StrategySummary(strategy_name="Empty")
        analysis = self.engine.analyze(strategy)

        assert analysis.metrics.profit_factor is None
        assert analysis.metrics.sharpe_ratio is None
        assert analysis.metrics.win_rate is None
        assert analysis.metrics.max_drawdown is None
        assert analysis.metrics.mar_ratio is None
        assert analysis.metrics.recovery_factor is None
        assert analysis.metrics.expectancy_ratio is None

    def test_present_columns_map_to_metrics(self) -> None:
        """GIVEN a StrategySummary with PF, Sharpe, win_rate, max_drawdown, trades
        WHEN the engine analyses it
        THEN the corresponding StatsResult fields are populated.
        """
        strategy = StrategySummary(
            strategy_name="Good",
            profit_factor=2.5,
            sharpe_ratio=1.8,
            win_rate=0.62,
            max_drawdown=8.5,
            total_trades=200,
        )
        analysis = self.engine.analyze(strategy)

        assert analysis.metrics.profit_factor == 2.5
        assert analysis.metrics.sharpe_ratio == 1.8
        assert analysis.metrics.win_rate == 0.62
        assert analysis.metrics.max_drawdown == 8.5
        assert analysis.metrics.total_trades == 200

    def test_missing_wf_cycles_keeps_metrics_none(self) -> None:
        """GIVEN no walk-forward data
        WHEN the engine analyses it
        THEN WF-related heuristics are skipped and metrics remain None.
        """
        strategy = StrategySummary(
            strategy_name="NoWF",
            profit_factor=1.5,
            sharpe_ratio=1.0,
        )
        analysis = self.engine.analyze(strategy)

        assert analysis.metrics.profit_factor == 1.5
        assert analysis.flags == []


class TestAnalysisEngineHeuristics:
    """Tests for deterministic overfit heuristics."""

    def setup_method(self) -> None:
        self.engine = AnalysisEngine()

    def test_extreme_pf_with_low_trades_flagged(self) -> None:
        """GIVEN a strategy with PF 5.0 and only 5 trades
        WHEN heuristics run
        THEN the strategy is flagged for extreme PF with low trades.
        """
        strategy = StrategySummary(
            strategy_name="TooGood",
            profit_factor=5.0,
            sharpe_ratio=0.5,
            total_trades=5,
        )
        analysis = self.engine.analyze(strategy)

        assert any("extreme_pf_low_trades" in f for f in analysis.flags)

    def test_extreme_sharpe_with_low_trades_flagged(self) -> None:
        """GIVEN a strategy with Sharpe 2.9 and only 5 trades
        WHEN heuristics run
        THEN the strategy is flagged for extreme Sharpe with low trades.
        """
        strategy = StrategySummary(
            strategy_name="TooGood",
            profit_factor=1.2,
            sharpe_ratio=2.9,
            total_trades=5,
        )
        analysis = self.engine.analyze(strategy)

        assert any("extreme_sharpe_low_trades" in f for f in analysis.flags)

    def test_mc_p10_breach_flagged(self) -> None:
        """GIVEN MC p10 is -1.2 (below zero)
        WHEN heuristics run
        THEN the strategy is flagged for MC p10 breach.
        """
        strategy = StrategySummary(
            strategy_name="MCBreach",
            profit_factor=2.65,
            sharpe_ratio=1.1,
            total_trades=540,
            mc_p10=-1.2,
        )
        analysis = self.engine.analyze(strategy)

        assert any("mc_p10_breach" in f for f in analysis.flags)

    def test_wf_degradation_flagged(self) -> None:
        """GIVEN wf OOS/IS Sharpe ratio is 0.5 (below 0.7)
        WHEN heuristics run
        THEN the strategy is flagged for walk-forward degradation.
        """
        strategy = StrategySummary(
            strategy_name="WFBad",
            profit_factor=1.0,
            sharpe_ratio=0.87,
            total_trades=890,
            wf_is_sharpe=0.95,
            wf_oos_sharpe=0.47,
        )
        analysis = self.engine.analyze(strategy)

        assert any("wf_degradation" in f for f in analysis.flags)

    def test_threshold_overrides(self) -> None:
        """GIVEN custom thresholds (min_trades=100, extreme_pf=4.0)
        WHEN analysing a strategy with 150 trades and PF 4.5
        THEN the heuristic does NOT fire because trades exceed min_trades override.
        """
        thresholds = AnalysisThresholds(min_trades=100, extreme_pf=4.0)
        strategy = StrategySummary(
            strategy_name="EdgeCase",
            profit_factor=4.5,
            total_trades=150,
        )
        analysis = self.engine.analyze(strategy, thresholds=thresholds)

        assert not any("extreme_pf_low_trades" in f for f in analysis.flags)

    def test_no_flags_when_healthy(self) -> None:
        """GIVEN a healthy strategy with adequate trades and metrics
        WHEN heuristics run
        THEN no flags are raised.
        """
        strategy = StrategySummary(
            strategy_name="Healthy",
            profit_factor=2.0,
            sharpe_ratio=1.5,
            total_trades=500,
            mc_p10=1.5,
            wf_is_sharpe=1.2,
            wf_oos_sharpe=1.1,
        )
        analysis = self.engine.analyze(strategy)

        assert analysis.flags == []

    def test_heuristics_are_data_gated(self) -> None:
        """GIVEN a strategy missing the fields required for a heuristic
        WHEN heuristics run
        THEN no exception is raised and the heuristic is skipped.
        """
        # No mc_p10, no wf data, trades > min_trades, PF not extreme
        strategy = StrategySummary(
            strategy_name="Sparse",
            profit_factor=1.2,
            total_trades=100,
        )
        analysis = self.engine.analyze(strategy)

        assert analysis.flags == []


class TestAnalysisEngineScore:
    """Tests for bounded weighted composite score."""

    def setup_method(self) -> None:
        self.engine = AnalysisEngine()

    def test_score_is_between_zero_and_hundred(self) -> None:
        """GIVEN a strategy with typical metrics
        WHEN a score is computed
        THEN it falls in the 0–100 range.
        """
        strategy = StrategySummary(
            strategy_name="Typical",
            profit_factor=2.0,
            sharpe_ratio=1.5,
            win_rate=0.6,
            max_drawdown=10.0,
            total_trades=300,
        )
        analysis = self.engine.analyze(strategy)
        assert 0.0 <= analysis.score <= 100.0

    def test_higher_metrics_produce_higher_score(self) -> None:
        """GIVEN two strategies, one with stronger metrics
        WHEN both are scored
        THEN the stronger strategy has a higher score.
        """
        weak = StrategySummary(
            strategy_name="Weak",
            profit_factor=1.0,
            sharpe_ratio=0.5,
            win_rate=0.4,
            max_drawdown=25.0,
            total_trades=100,
        )
        strong = StrategySummary(
            strategy_name="Strong",
            profit_factor=3.0,
            sharpe_ratio=2.0,
            win_rate=0.7,
            max_drawdown=5.0,
            total_trades=500,
        )

        weak_score = self.engine.analyze(weak).score
        strong_score = self.engine.analyze(strong).score

        assert strong_score > weak_score
