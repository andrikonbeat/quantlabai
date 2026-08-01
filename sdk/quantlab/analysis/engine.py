"""AnalysisEngine — per-strategy metrics and overfit heuristics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from quantlab.readers.models import StrategySummary
from quantlab.stats.engine import StatisticsEngine
from quantlab.stats.models import StatsResult
from quantlab.tools.exceptions import QuantLabError

from quantlab.analysis.models import StrategyAnalysis


@dataclass
class AnalysisThresholds:
    """Thresholds controlling overfit-heuristic behaviour.

    Attributes:
        min_trades: Strategies with fewer trades than this are vulnerable
            to "too-good-to-be-true" metrics.
        extreme_pf: Profit factors above this are considered extreme when
            combined with low trade counts.
        extreme_sharpe: Sharpe ratios above this are considered extreme when
            combined with low trade counts.
        oos_is_threshold: Minimum acceptable out-of-sample / in-sample Sharpe
            ratio. Values below this suggest overfitting.
        score_weights: Per-metric weights for the composite score. Must sum
            to 1.0.
        pf_weight: Weight for profit_factor in the composite score.
        sharpe_weight: Weight for sharpe_ratio.
        win_rate_weight: Weight for win_rate.
        mdd_weight: Weight for max_drawdown (inverted: lower is better).
        mar_weight: Weight for mar_ratio.
        recovery_weight: Weight for recovery_factor.
        expectancy_weight: Weight for expectancy_ratio.
    """

    min_trades: int = 50
    extreme_pf: float = 3.0
    extreme_sharpe: float = 2.0
    oos_is_threshold: float = 0.7
    pf_weight: float = 0.25
    sharpe_weight: float = 0.20
    win_rate_weight: float = 0.15
    mdd_weight: float = 0.15
    mar_weight: float = 0.10
    recovery_weight: float = 0.10
    expectancy_weight: float = 0.05

    def __post_init__(self) -> None:
        total = (
            self.pf_weight
            + self.sharpe_weight
            + self.win_rate_weight
            + self.mdd_weight
            + self.mar_weight
            + self.recovery_weight
            + self.expectancy_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Score weights must sum to 1.0, got {total:.10f}. "
                "Adjust one or more weights."
            )


class AnalysisEngine:
    """Compute per-strategy metrics and overfit heuristics.

    Maps ``StrategySummary`` fields into ``StatsResult`` (absent columns → ``None``).
    Uses ``StatisticsEngine`` statics for derived metrics when inputs are available.
    Applies deterministic, data-gated heuristics to flag overfit risk.

    Usage::

        engine = AnalysisEngine()
        analysis = engine.analyze(strategy_summary, thresholds)
    """

    def __init__(self) -> None:
        self._stats_engine = StatisticsEngine()

    def analyze(
        self,
        strategy: StrategySummary,
        thresholds: AnalysisThresholds | None = None,
    ) -> StrategyAnalysis:
        """Analyse a single strategy and return its analysis result.

        Args:
            strategy: Parsed strategy summary from the reader.
            thresholds: Override thresholds. Defaults to ``AnalysisThresholds()``.

        Returns:
            A ``StrategyAnalysis`` with metrics, flags, and composite score.
        """
        thresholds = thresholds or AnalysisThresholds()

        metrics = self._build_metrics(strategy)
        flags = self._apply_heuristics(strategy, metrics, thresholds)
        score = self._compute_score(metrics, thresholds)

        return StrategyAnalysis(
            name=strategy.strategy_name or "unknown",
            metrics=metrics,
            flags=flags,
            score=score,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_metrics(self, strategy: StrategySummary) -> StatsResult:
        """Map StrategySummary fields into a StatsResult.

        Columns absent from the CSV remain ``None``.
        """
        result = StatsResult()

        # Direct scalar mappings from StrategySummary
        result.profit_factor = strategy.profit_factor
        result.sharpe_ratio = strategy.sharpe_ratio
        result.win_rate = strategy.win_rate
        result.max_drawdown = strategy.max_drawdown
        result.total_trades = strategy.total_trades

        # Derived metrics via StatisticsEngine statics when inputs are available.
        # MAR requires CAGR + MDD; recovery requires net_profit + MDD.
        # StrategySummary does not carry CAGR or net_profit, so these remain None.
        if strategy.max_drawdown is not None:
            # No CAGR or net_profit available from StrategySummary; keep None.
            # The statics remain available if upstream later provides the inputs.
            pass

        return result

    def _apply_heuristics(
        self,
        strategy: StrategySummary,
        metrics: StatsResult,
        thresholds: AnalysisThresholds,
    ) -> list[str]:
        """Apply deterministic, data-gated overfit heuristics.

        A heuristic only triggers when its required data is present.
        """
        flags: list[str] = []

        # Heuristic A: extreme PF/Sharpe with total_trades below min_trades
        if (
            strategy.total_trades is not None
            and strategy.total_trades < thresholds.min_trades
        ):
            if (
                strategy.profit_factor is not None
                and strategy.profit_factor > thresholds.extreme_pf
            ):
                flags.append(
                    f"extreme_pf_low_trades: PF={strategy.profit_factor:.2f} "
                    f"with {strategy.total_trades} trades"
                )
            if (
                strategy.sharpe_ratio is not None
                and strategy.sharpe_ratio > thresholds.extreme_sharpe
            ):
                flags.append(
                    f"extreme_sharpe_low_trades: Sharpe={strategy.sharpe_ratio:.2f} "
                    f"with {strategy.total_trades} trades"
                )

        # Heuristic B: MC p10 curve breach
        if strategy.mc_p10 is not None and strategy.mc_p10 < 0:
            flags.append(
                f"mc_p10_breach: MC p10={strategy.mc_p10:.2f} crosses below zero"
            )

        # Heuristic C: WF OOS/IS degradation
        if (
            strategy.wf_is_sharpe is not None
            and strategy.wf_oos_sharpe is not None
            and strategy.wf_is_sharpe > 0
        ):
            oos_is_ratio = strategy.wf_oos_sharpe / strategy.wf_is_sharpe
            if oos_is_ratio < thresholds.oos_is_threshold:
                flags.append(
                    f"wf_degradation: OOS/IS={oos_is_ratio:.2f} "
                    f"below threshold {thresholds.oos_is_threshold:.2f}"
                )

        return flags

    def _compute_score(
        self,
        metrics: StatsResult,
        thresholds: AnalysisThresholds,
    ) -> float:
        """Compute a bounded weighted composite score (0–100).

        Each present metric is normalised to 0–1, then multiplied by its
        configured weight. Missing metrics contribute zero and are excluded
        from the weight denominator.
        """
        normalised = self._normalise_all(metrics)
        weighted_sum = 0.0
        active_weight_total = 0.0

        weighted_sum += normalised["profit_factor"] * thresholds.pf_weight
        if metrics.profit_factor is not None:
            active_weight_total += thresholds.pf_weight

        weighted_sum += normalised["sharpe_ratio"] * thresholds.sharpe_weight
        if metrics.sharpe_ratio is not None:
            active_weight_total += thresholds.sharpe_weight

        weighted_sum += normalised["win_rate"] * thresholds.win_rate_weight
        if metrics.win_rate is not None:
            active_weight_total += thresholds.win_rate_weight

        weighted_sum += normalised["max_drawdown"] * thresholds.mdd_weight
        if metrics.max_drawdown is not None:
            active_weight_total += thresholds.mdd_weight

        weighted_sum += normalised["mar_ratio"] * thresholds.mar_weight
        if metrics.mar_ratio is not None:
            active_weight_total += thresholds.mar_weight

        weighted_sum += normalised["recovery_factor"] * thresholds.recovery_weight
        if metrics.recovery_factor is not None:
            active_weight_total += thresholds.recovery_weight

        weighted_sum += normalised["expectancy_ratio"] * thresholds.expectancy_weight
        if metrics.expectancy_ratio is not None:
            active_weight_total += thresholds.expectancy_weight

        if active_weight_total > 0:
            return round((weighted_sum / active_weight_total) * 100.0, 2)
        return 0.0

    @staticmethod
    def _normalise_all(metrics: StatsResult) -> dict[str, float]:
        """Normalise every score-tracked metric to a 0–1 value.

        ``None`` inputs normalise to 0.0.
        """
        return {
            "profit_factor": AnalysisEngine._normalise_profit_factor(metrics.profit_factor),
            "sharpe_ratio": AnalysisEngine._normalise_sharpe_ratio(metrics.sharpe_ratio),
            "win_rate": AnalysisEngine._normalise_win_rate(metrics.win_rate),
            "max_drawdown": AnalysisEngine._normalise_max_drawdown(metrics.max_drawdown),
            "mar_ratio": AnalysisEngine._normalise_mar_ratio(metrics.mar_ratio),
            "recovery_factor": AnalysisEngine._normalise_recovery_factor(metrics.recovery_factor),
            "expectancy_ratio": AnalysisEngine._normalise_expectancy_ratio(metrics.expectancy_ratio),
        }

    @staticmethod
    def _normalise_profit_factor(pf: float | None) -> float:
        if pf is None:
            return 0.0
        # Cap at 5.0 for normalisation (PF 5+ = 1.0)
        return min(max(pf / 5.0, 0.0), 1.0)

    @staticmethod
    def _normalise_sharpe_ratio(sr: float | None) -> float:
        if sr is None:
            return 0.0
        # Cap at 3.0 for normalisation (Sharpe 3+ = 1.0)
        return min(max(sr / 3.0, 0.0), 1.0)

    @staticmethod
    def _normalise_win_rate(wr: float | None) -> float:
        if wr is None:
            return 0.0
        # Win rate is a decimal (0.0–1.0)
        return min(max(wr, 0.0), 1.0)

    @staticmethod
    def _normalise_max_drawdown(mdd: float | None) -> float:
        if mdd is None:
            return 0.0
        # MDD is a positive percentage; lower is better.
        # 0% → 1.0, 50%+ → 0.0
        return min(max(1.0 - (mdd / 50.0), 0.0), 1.0)

    @staticmethod
    def _normalise_mar_ratio(mar: float | None) -> float:
        if mar is None:
            return 0.0
        # Cap at 2.0 for normalisation (MAR 2+ = 1.0)
        return min(max(mar / 2.0, 0.0), 1.0)

    @staticmethod
    def _normalise_recovery_factor(rf: float | None) -> float:
        if rf is None:
            return 0.0
        # Cap at 5.0 for normalisation (RF 5+ = 1.0)
        return min(max(rf / 5.0, 0.0), 1.0)

    @staticmethod
    def _normalise_expectancy_ratio(er: float | None) -> float:
        if er is None:
            return 0.0
        # Cap at 2.0 for normalisation (ER 2+ = 1.0)
        return min(max(er / 2.0, 0.0), 1.0)
