"""HealthScoreCalculator — pure computation layer for strategy health scoring.

Takes a ``StatsResult`` and optional weight config, normalises each metric
via piecewise-linear functions, computes a weighted average, and returns a
``HealthScore`` with per-metric breakdown.
"""

from __future__ import annotations

from typing import ClassVar

from quantlab.health.models import HealthScore, HealthState, HealthWeights
from quantlab.health.weights import (
    DEFAULT_WEIGHTS,
    normalize_expectancy_ratio,
    normalize_max_drawdown,
    normalize_profit_factor,
    normalize_recovery_factor,
    normalize_sharpe_ratio,
    normalize_sortino_ratio,
    normalize_win_rate,
)
from quantlab.stats.models import StatsResult


class HealthScoreCalculator:
    """Stateless calculator that transforms a ``StatsResult`` into a ``HealthScore``.

    Usage::

        calculator = HealthScoreCalculator()
        score = calculator.compute(stats_result, period="90d")
        print(f"Health: {score.state.value} ({score.overall_score:.1f})")

    Weights can be injected at construction time to override defaults::

        custom = HealthWeights(profit_factor=0.35, sharpe_ratio=0.10)
        calculator = HealthScoreCalculator(weights=custom)
    """

    WEIGHT_TOTAL: ClassVar[float] = 1.0

    def __init__(self, weights: HealthWeights | None = None) -> None:
        """Initialise the calculator with an optional weight configuration.

        Args:
            weights: Custom weight distribution. Defaults to ``HealthWeights()``
                when ``None``.
        """
        self._weights = weights or DEFAULT_WEIGHTS

    # ── Public API ──────────────────────────────────────────────────────────

    def compute(self, stats: StatsResult, period: str = "all") -> HealthScore:
        """Score a single ``StatsResult`` and return a ``HealthScore``.

        Each metric present in ``stats`` is normalised to a 0–1 score,
        multiplied by its configured weight, and aggregated into a weighted
        average scaled to 0–100.

        Missing (``None``) metrics contribute zero and are excluded from
        the weighted average denominator adjustment.

        Args:
            stats: A ``StatsResult`` with one or more computed metric values.
            period: Time window label to stamp on the result (pass-through).

        Returns:
            A ``HealthScore`` with the composite score, categorical state,
            and per-metric normalised scores.
        """
        normalized = self._normalize_all(stats)
        raw_metrics = self._get_raw_metrics(stats)
        weighted_sum = 0.0
        active_weight_total = 0.0

        for metric, weight in self._iter_metric_weights():
            norm_score = normalized[metric]
            weighted_sum += norm_score * weight
            # Only count the weight when the metric has a non-None raw value.
            # Missing metrics contribute 0 to the sum but don't claim weight
            # in the denominator — effectively redistributing weight among
            # the metrics that are actually present.
            if raw_metrics[metric] is not None:
                active_weight_total += weight

        if active_weight_total > 0:
            overall = (weighted_sum / active_weight_total) * 100.0
        else:
            overall = 0.0

        return HealthScore(
            overall_score=round(overall, 2),
            state=self.map_score_to_state(overall),
            metric_scores=normalized,
            period=period,
        )

    # ── Per-metric normalisation (delegates to ``weights`` module) ──────────

    @staticmethod
    def normalize_profit_factor(pf: float | None) -> float:
        """Normalise Profit Factor to 0–1. See ``weights.normalize_profit_factor``."""
        return normalize_profit_factor(pf)

    @staticmethod
    def normalize_sharpe_ratio(sr: float | None) -> float:
        return normalize_sharpe_ratio(sr)

    @staticmethod
    def normalize_sortino_ratio(sr: float | None) -> float:
        return normalize_sortino_ratio(sr)

    @staticmethod
    def normalize_max_drawdown(mdd: float | None) -> float:
        return normalize_max_drawdown(mdd)

    @staticmethod
    def normalize_recovery_factor(rf: float | None) -> float:
        return normalize_recovery_factor(rf)

    @staticmethod
    def normalize_win_rate(wr: float | None) -> float:
        return normalize_win_rate(wr)

    @staticmethod
    def normalize_expectancy_ratio(er: float | None) -> float:
        return normalize_expectancy_ratio(er)

    # ── State mapping ───────────────────────────────────────────────────────

    @staticmethod
    def map_score_to_state(score: float) -> HealthState:
        """Map a 0–100 score to the corresponding ``HealthState`` band.

        Args:
            score: Overall health score (0–100).

        Returns:
            The matching ``HealthState`` enum member.
        """
        if score >= 90:
            return HealthState.EXCELLENT
        if score >= 75:
            return HealthState.STABLE
        if score >= 60:
            return HealthState.OBSERVATION
        if score >= 45:
            return HealthState.DEGRADING
        if score >= 30:
            return HealthState.REPLACEMENT_RECOMMENDED
        return HealthState.IMMEDIATE_WITHDRAWAL

    # ── Internal helpers ────────────────────────────────────────────────────

    def _iter_metric_weights(self) -> list[tuple[str, float]]:
        """Return (metric_name, weight) pairs from the config."""
        w = self._weights
        return [
            ("profit_factor", w.profit_factor),
            ("sharpe_ratio", w.sharpe_ratio),
            ("sortino_ratio", w.sortino_ratio),
            ("max_drawdown", w.max_drawdown),
            ("recovery_factor", w.recovery_factor),
            ("win_rate", w.win_rate),
            ("expectancy_ratio", w.expectancy_ratio),
        ]

    def _get_raw_metrics(self, stats: StatsResult) -> dict[str, float | None]:
        """Return the raw (pre-normalisation) metric values from a ``StatsResult``."""
        return {
            "profit_factor": stats.profit_factor,
            "sharpe_ratio": stats.sharpe_ratio,
            "sortino_ratio": stats.sortino_ratio,
            "max_drawdown": stats.max_drawdown,
            "recovery_factor": stats.recovery_factor,
            "win_rate": stats.win_rate,
            "expectancy_ratio": stats.expectancy_ratio,
        }

    def _normalize_all(self, stats: StatsResult) -> dict[str, float]:
        """Normalise every health-tracked metric to a 0–1 score.

        Uses the raw values from ``stats``; ``None`` inputs normalise to
        0.0. Every health metric always appears in the returned dict.
        """
        normalizers = {
            "profit_factor": normalize_profit_factor,
            "sharpe_ratio": normalize_sharpe_ratio,
            "sortino_ratio": normalize_sortino_ratio,
            "max_drawdown": normalize_max_drawdown,
            "recovery_factor": normalize_recovery_factor,
            "win_rate": normalize_win_rate,
            "expectancy_ratio": normalize_expectancy_ratio,
        }

        result: dict[str, float] = {}
        for name, raw_value in self._get_raw_metrics(stats).items():
            result[name] = normalizers[name](raw_value)
        return result
