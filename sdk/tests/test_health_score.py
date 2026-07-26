"""Tests for the Health Score System — normalisation, scoring, and edge cases."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from quantlab.health.calculator import HealthScoreCalculator
from quantlab.health.models import HealthRecord, HealthScore, HealthState, HealthWeights
from quantlab.health.weights import (
    DEFAULT_WEIGHTS,
    normalize_expectancy_ratio,
    normalize_max_drawdown,
    normalize_metric,
    normalize_profit_factor,
    normalize_recovery_factor,
    normalize_sharpe_ratio,
    normalize_sortino_ratio,
    normalize_win_rate,
)
from quantlab.stats.models import StatsResult

calculator = HealthScoreCalculator()


# ── HealthState boundary tests ──────────────────────────────────────────────


class TestHealthStateBoundaries:
    """Verify every transition point between the six health bands."""

    def test_100_excellent(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(100.0) == HealthState.EXCELLENT

    def test_95_excellent(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(95.0) == HealthState.EXCELLENT

    def test_90_boundary_excellent(self) -> None:
        """Score of 90 maps to EXCELLENT (inclusive upper band)."""
        assert HealthScoreCalculator.map_score_to_state(90.0) == HealthState.EXCELLENT

    def test_89_boundary_stable(self) -> None:
        """Score of 89 maps to STABLE (just below EXCELLENT)."""
        assert HealthScoreCalculator.map_score_to_state(89.0) == HealthState.STABLE

    def test_80_stable(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(80.0) == HealthState.STABLE

    def test_75_boundary_stable(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(75.0) == HealthState.STABLE

    def test_74_boundary_observation(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(74.0) == HealthState.OBSERVATION

    def test_60_boundary_observation(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(60.0) == HealthState.OBSERVATION

    def test_59_boundary_degrading(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(59.0) == HealthState.DEGRADING

    def test_45_boundary_degrading(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(45.0) == HealthState.DEGRADING

    def test_44_boundary_replacement(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(44.0) == HealthState.REPLACEMENT_RECOMMENDED

    def test_30_boundary_replacement(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(30.0) == HealthState.REPLACEMENT_RECOMMENDED

    def test_29_boundary_withdrawal(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(29.0) == HealthState.IMMEDIATE_WITHDRAWAL

    def test_0_withdrawal(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(0.0) == HealthState.IMMEDIATE_WITHDRAWAL

    def test_negative_clamps_to_withdrawal(self) -> None:
        assert HealthScoreCalculator.map_score_to_state(-5.0) == HealthState.IMMEDIATE_WITHDRAWAL


# ── HealthScore model validation ────────────────────────────────────────────


class TestHealthScoreModel:
    """Verify Pydantic model constraints on HealthScore."""

    def test_valid_health_score_creation(self) -> None:
        score = HealthScore(
            overall_score=82.0,
            state=HealthState.STABLE,
            metric_scores={"sharpe_ratio": 0.85, "profit_factor": 0.78},
            period="90d",
        )
        assert score.overall_score == 82.0
        assert score.state == HealthState.STABLE
        assert score.metric_scores["sharpe_ratio"] == 0.85
        assert score.period == "90d"

    def test_score_above_100_raises(self) -> None:
        with pytest.raises(ValidationError):
            HealthScore(
                overall_score=150.0,
                state=HealthState.EXCELLENT,
                metric_scores={},
            )

    def test_score_below_0_raises(self) -> None:
        with pytest.raises(ValidationError):
            HealthScore(
                overall_score=-10.0,
                state=HealthState.IMMEDIATE_WITHDRAWAL,
                metric_scores={},
            )

    def test_default_period_is_all(self) -> None:
        score = HealthScore(
            overall_score=50.0,
            state=HealthState.DEGRADING,
            metric_scores={"pf": 0.5},
        )
        assert score.period == "all"


# ── HealthWeights validation ────────────────────────────────────────────────


class TestHealthWeights:
    """Verify weight validation and default distribution."""

    def test_default_weights_sum_to_one(self) -> None:
        w = HealthWeights()
        total = w.profit_factor + w.sharpe_ratio + w.sortino_ratio + w.max_drawdown + w.recovery_factor + w.win_rate + w.expectancy_ratio
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_default_weights_match_spec(self) -> None:
        w = HealthWeights()
        assert w.profit_factor == 0.25
        assert w.sharpe_ratio == 0.20
        assert w.sortino_ratio == 0.10
        assert w.max_drawdown == 0.20
        assert w.recovery_factor == 0.10
        assert w.win_rate == 0.05
        assert w.expectancy_ratio == 0.10

    def test_custom_weights_override(self) -> None:
        w = HealthWeights(profit_factor=0.35, sharpe_ratio=0.10)
        assert w.profit_factor == 0.35
        assert w.sharpe_ratio == 0.10

    def test_custom_weights_sum_validation(self) -> None:
        """Weights that don't sum to 1.0 raise ValueError."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            HealthWeights(profit_factor=1.0, sharpe_ratio=0.0)  # only 1.0 total

    def test_weights_model_is_frozen(self) -> None:
        w = HealthWeights()
        with pytest.raises(ValidationError):
            w.profit_factor = 0.5  # type: ignore[misc]

    def test_module_constant_default(self) -> None:
        assert DEFAULT_WEIGHTS == HealthWeights()


# ── Normalisation function tests ────────────────────────────────────────────


class TestNormalizeProfitFactor:
    """Piecewise-linear normalisation for Profit Factor."""

    def test_pf_zero(self) -> None:
        assert normalize_profit_factor(0.0) == 0.0

    def test_pf_one(self) -> None:
        # (1.0, 0.3)
        assert normalize_profit_factor(1.0) == pytest.approx(0.3)

    def test_pf_one_point_five(self) -> None:
        # (1.5, 0.6)
        assert normalize_profit_factor(1.5) == pytest.approx(0.6)

    def test_pf_two(self) -> None:
        # (2.0, 0.8)
        assert normalize_profit_factor(2.0) == pytest.approx(0.8)

    def test_pf_three(self) -> None:
        # (3.0, 0.95)
        assert normalize_profit_factor(3.0) == pytest.approx(0.95)

    def test_pf_mid_interpolation(self) -> None:
        # Between 1.0 and 1.5: 0.3 + (0.6-0.3)*(0.25/0.5) = 0.3 + 0.15 = 0.45
        assert normalize_profit_factor(1.25) == pytest.approx(0.45)

    def test_pf_above_max(self) -> None:
        assert normalize_profit_factor(5.0) == pytest.approx(0.95)

    def test_pf_infinity(self) -> None:
        assert normalize_profit_factor(math.inf) == pytest.approx(0.95)

    def test_pf_none(self) -> None:
        assert normalize_profit_factor(None) == 0.0

    def test_pf_negative(self) -> None:
        # Clamp to first breakpoint
        assert normalize_profit_factor(-1.0) == 0.0


class TestNormalizeSharpeRatio:
    """Piecewise-linear normalisation for Sharpe Ratio."""

    def test_sharpe_zero(self) -> None:
        assert normalize_sharpe_ratio(0.0) == pytest.approx(0.3)

    def test_sharpe_one(self) -> None:
        assert normalize_sharpe_ratio(1.0) == pytest.approx(0.6)

    def test_sharpe_two(self) -> None:
        assert normalize_sharpe_ratio(2.0) == pytest.approx(0.85)

    def test_sharpe_three(self) -> None:
        assert normalize_sharpe_ratio(3.0) == pytest.approx(0.95)

    def test_sharpe_interpolation(self) -> None:
        # Between 1.0 and 2.0: 0.6 + (0.85-0.6)*(0.5/1.0) = 0.6 + 0.125 = 0.725
        assert normalize_sharpe_ratio(1.5) == pytest.approx(0.725)

    def test_sharpe_infinity(self) -> None:
        assert normalize_sharpe_ratio(math.inf) == pytest.approx(0.95)

    def test_sharpe_none(self) -> None:
        assert normalize_sharpe_ratio(None) == 0.0


class TestNormalizeSortinoRatio:
    """Piecewise-linear normalisation for Sortino Ratio."""

    def test_sortino_zero(self) -> None:
        assert normalize_sortino_ratio(0.0) == pytest.approx(0.2)

    def test_sortino_one(self) -> None:
        assert normalize_sortino_ratio(1.0) == pytest.approx(0.5)

    def test_sortino_two(self) -> None:
        assert normalize_sortino_ratio(2.0) == pytest.approx(0.8)

    def test_sortino_three(self) -> None:
        assert normalize_sortino_ratio(3.0) == pytest.approx(0.95)

    def test_sortino_none(self) -> None:
        assert normalize_sortino_ratio(None) == 0.0


class TestNormalizeMaxDrawdown:
    """Piecewise-linear normalisation for Max Drawdown (percentage)."""

    def test_mdd_zero(self) -> None:
        assert normalize_max_drawdown(0.0) == pytest.approx(1.0)

    def test_mdd_five(self) -> None:
        assert normalize_max_drawdown(5.0) == pytest.approx(0.9)

    def test_mdd_ten(self) -> None:
        assert normalize_max_drawdown(10.0) == pytest.approx(0.7)

    def test_mdd_twenty(self) -> None:
        assert normalize_max_drawdown(20.0) == pytest.approx(0.4)

    def test_mdd_thirty(self) -> None:
        assert normalize_max_drawdown(30.0) == pytest.approx(0.1)

    def test_mdd_fifty(self) -> None:
        assert normalize_max_drawdown(50.0) == pytest.approx(0.0)

    def test_mdd_interpolation(self) -> None:
        # Between 5 and 10: 0.9 + (0.7-0.9)*(2/5) = 0.9 - 0.08 = 0.82
        assert normalize_max_drawdown(7.0) == pytest.approx(0.82)

    def test_mdd_above_fifty(self) -> None:
        assert normalize_max_drawdown(60.0) == pytest.approx(0.0)

    def test_mdd_none(self) -> None:
        assert normalize_max_drawdown(None) == 0.0


class TestNormalizeRecoveryFactor:
    """Piecewise-linear normalisation for Recovery Factor."""

    def test_rf_zero(self) -> None:
        assert normalize_recovery_factor(0.0) == pytest.approx(0.0)

    def test_rf_one(self) -> None:
        assert normalize_recovery_factor(1.0) == pytest.approx(0.3)

    def test_rf_two(self) -> None:
        assert normalize_recovery_factor(2.0) == pytest.approx(0.6)

    def test_rf_five(self) -> None:
        assert normalize_recovery_factor(5.0) == pytest.approx(0.85)

    def test_rf_ten(self) -> None:
        assert normalize_recovery_factor(10.0) == pytest.approx(0.95)

    def test_rf_none(self) -> None:
        assert normalize_recovery_factor(None) == 0.0

    def test_rf_infinity(self) -> None:
        assert normalize_recovery_factor(math.inf) == pytest.approx(0.95)


class TestNormalizeWinRate:
    """Piecewise-linear normalisation for Win Rate (percentage)."""

    def test_wr_zero(self) -> None:
        assert normalize_win_rate(0.0) == pytest.approx(0.0)

    def test_wr_fifty(self) -> None:
        # Linear: 50/80 * 0.95 = 0.59375
        assert normalize_win_rate(50.0) == pytest.approx(0.59375)

    def test_wr_eighty(self) -> None:
        assert normalize_win_rate(80.0) == pytest.approx(0.95)

    def test_wr_hundred(self) -> None:
        assert normalize_win_rate(100.0) == pytest.approx(0.95)

    def test_wr_above_max(self) -> None:
        assert normalize_win_rate(200.0) == pytest.approx(0.95)

    def test_wr_none(self) -> None:
        assert normalize_win_rate(None) == 0.0


class TestNormalizeExpectancyRatio:
    """Piecewise-linear normalisation for Expectancy Ratio."""

    def test_er_zero(self) -> None:
        assert normalize_expectancy_ratio(0.0) == pytest.approx(0.0)

    def test_er_half(self) -> None:
        assert normalize_expectancy_ratio(0.5) == pytest.approx(0.3)

    def test_er_one(self) -> None:
        assert normalize_expectancy_ratio(1.0) == pytest.approx(0.6)

    def test_er_two(self) -> None:
        assert normalize_expectancy_ratio(2.0) == pytest.approx(0.85)

    def test_er_five(self) -> None:
        assert normalize_expectancy_ratio(5.0) == pytest.approx(0.95)

    def test_er_none(self) -> None:
        assert normalize_expectancy_ratio(None) == 0.0

    def test_er_infinity(self) -> None:
        assert normalize_expectancy_ratio(math.inf) == pytest.approx(0.95)


class TestNormalizeMetricDispatcher:
    """Verify the metric-name dispatcher routes correctly."""

    def test_known_metric(self) -> None:
        assert normalize_metric("profit_factor", 2.0) == normalize_profit_factor(2.0)

    def test_unknown_metric_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown metric"):
            normalize_metric("nonexistent", 1.0)


# ── Calculator integration tests ────────────────────────────────────────────


class TestHealthScoreCalculator:
    """Integration tests for ``HealthScoreCalculator.compute()``."""

    def test_full_stats_result(self) -> None:
        """GIVEN a StatsResult with all metrics populated
        WHEN the calculator scores it
        THEN a HealthScore is returned with valid 0–100 score and metric_scores.
        """
        stats = StatsResult(
            profit_factor=2.0,
            sharpe_ratio=1.5,
            sortino_ratio=1.5,
            max_drawdown=8.0,
            recovery_factor=6.0,
            win_rate=65.0,
            expectancy_ratio=1.5,
        )
        result = calculator.compute(stats, period="all")
        assert isinstance(result, HealthScore)
        assert 0.0 <= result.overall_score <= 100.0
        assert result.state in HealthState
        assert len(result.metric_scores) == 7
        assert result.period == "all"

    def test_known_stats_yields_expected_score(self) -> None:
        """Manually verify weighted average calculation.

        Stats: PF=2.5, Sharpe=1.8
        Normalised: PF(2.5) → interpolated between (2.0,0.8) and (3.0,0.95) = 0.875
                    Sharpe(1.8) → interpolated between (1.0,0.6) and (2.0,0.85) = 0.80
        Weighted sum = 0.875*0.25 + 0.80*0.20 = 0.21875 + 0.16 = 0.37875
        All others missing → active_weight_total = 0.45
        Overall = (0.37875 / 0.45) * 100 = 84.17
        """
        stats = StatsResult(profit_factor=2.5, sharpe_ratio=1.8)
        result = calculator.compute(stats, period="90d")
        assert result.period == "90d"
        assert result.overall_score == pytest.approx(84.17, abs=0.05)

    def test_all_none_metrics_returns_zero(self) -> None:
        """GIVEN a StatsResult where all fields are None
        WHEN the calculator scores it
        THEN overall_score is 0 and state is IMMEDIATE_WITHDRAWAL.
        """
        stats = StatsResult()
        result = calculator.compute(stats)
        assert result.overall_score == 0.0
        assert result.state == HealthState.IMMEDIATE_WITHDRAWAL
        # All metric scores should be 0 when all inputs are None
        for val in result.metric_scores.values():
            assert val == 0.0

    def test_infinity_metrics_capped(self) -> None:
        """GIVEN a StatsResult with profit_factor=inf and max_drawdown=0
        WHEN the calculator scores it
        THEN profit_factor contributes max normalised score (0.95).
        """
        stats = StatsResult(profit_factor=math.inf, max_drawdown=0.0)
        # PF inf → 0.95; MDD 0 → 1.0
        # Weighted: (0.95*0.25 + 1.0*0.20) / 0.45 * 100 = (0.2375 + 0.20) / 0.45 * 100 = 97.22
        result = calculator.compute(stats)
        assert result.metric_scores["profit_factor"] == pytest.approx(0.95)
        assert result.metric_scores["max_drawdown"] == pytest.approx(1.0)
        assert result.overall_score == pytest.approx(97.22, abs=0.05)

    def test_partial_metrics_skip_missing(self) -> None:
        """GIVEN a StatsResult with only profit_factor
        WHEN the calculator scores it
        THEN missing metrics are excluded and active weights are renormalised.
        """
        stats = StatsResult(profit_factor=1.5)
        result = calculator.compute(stats)
        # PF(1.5) → 0.6, weight=0.25, active_total=0.25
        # Overall = (0.6*0.25 / 0.25) * 100 = 60.0
        assert result.overall_score == pytest.approx(60.0)
        assert len(result.metric_scores) == 7  # all seven keys present

    def test_custom_weights_affect_score(self) -> None:
        """GIVEN custom HealthWeights with profit_factor=0.35 and sharpe_ratio=0.10
        WHEN the calculator uses these weights
        THEN the computed score reflects the custom weighting.
        """
        custom_weights = HealthWeights(profit_factor=0.35, sharpe_ratio=0.10)
        cal = HealthScoreCalculator(weights=custom_weights)
        stats = StatsResult(profit_factor=2.0, sharpe_ratio=1.0)
        result = cal.compute(stats)
        # PF(2.0) → 0.8, weight=0.35 → 0.28
        # Sharpe(1.0) → 0.6, weight=0.10 → 0.06
        # active_total = 0.45
        # Overall = (0.28 + 0.06) / 0.45 * 100 = 75.56
        default_cal = HealthScoreCalculator()
        default_result = default_cal.compute(stats)
        assert result.overall_score == pytest.approx(75.56, abs=0.05)
        # Verify custom differs from default
        assert result.overall_score != default_result.overall_score

    def test_period_label_pass_through(self) -> None:
        """Period label is stamped on the result as-is."""
        stats = StatsResult(profit_factor=1.5)
        for period in ("30d", "90d", "1y", "all"):
            result = calculator.compute(stats, period=period)
            assert result.period == period

    def test_high_quality_strategy_excellent(self) -> None:
        """A very strong strategy scores EXCELLENT."""
        stats = StatsResult(
            profit_factor=3.5,
            sharpe_ratio=2.5,
            sortino_ratio=3.0,
            max_drawdown=3.0,
            recovery_factor=15.0,
            win_rate=85.0,
            expectancy_ratio=3.0,
        )
        result = calculator.compute(stats)
        assert result.state == HealthState.EXCELLENT

    def test_poor_strategy_withdrawal(self) -> None:
        """A very weak strategy scores IMMEDIATE_WITHDRAWAL."""
        stats = StatsResult(
            profit_factor=0.5,
            sharpe_ratio=-0.5,
            sortino_ratio=-1.0,
            max_drawdown=45.0,
            recovery_factor=0.1,
            win_rate=15.0,
            expectancy_ratio=0.0,
        )
        result = calculator.compute(stats)
        assert result.state == HealthState.IMMEDIATE_WITHDRAWAL


# ── HealthRecord tests ──────────────────────────────────────────────────────


class TestHealthRecord:
    """Verify HealthRecord model creation and defaults."""

    def test_create_record(self) -> None:
        score = HealthScore(overall_score=82.0, state=HealthState.STABLE, metric_scores={"pf": 0.8})
        record = HealthRecord(strategy_id="strat-alpha", score=score)
        assert record.strategy_id == "strat-alpha"
        assert record.score.overall_score == 82.0
        assert record.metadata == {}

    def test_record_with_metadata(self) -> None:
        score = HealthScore(overall_score=45.0, state=HealthState.DEGRADING, metric_scores={})
        record = HealthRecord(
            strategy_id="strat-beta",
            score=score,
            metadata={"campaign": "camp-001", "alert_sent": True},
        )
        assert record.metadata["campaign"] == "camp-001"
