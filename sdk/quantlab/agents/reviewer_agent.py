"""ReviewerAgent — adversarial reviewer that evaluates campaign results against acceptance criteria.

Performs walk-forward degradation detection, Monte Carlo overfitting checks,
benchmark comparison, and generates structured iteration proposals.

Implements the ``ReviewStage.execute()`` contract for pipeline integration.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import ReviewStage
from quantlab.stats.aggregation import StatisticsAggregator
from quantlab.stats.models import BenchmarkComparison

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────────

WF_DEGRADATION_THRESHOLD = 0.7  # OOS/IS ratio below this = overfitting
MC_BREACH_SEVERITY_HIGH = "HIGH"
MC_BREACH_SEVERITY_MEDIUM = "MEDIUM"


class ReviewDecision(str):
    """Review decision type."""
    APPROVE = "APPROVE"
    ACCEPT = "ACCEPT"      # Alias for APPROVE for spec compatibility
    ITERATE = "ITERATE"
    REJECT = "REJECT"


class ReviewerAgent(ReviewStage):
    """Adversarial reviewer that evaluates campaign results against criteria.

    All evaluation methods are deterministic — no learning, no random state.
    Accepts criteria from ``ResearchConfig.acceptance_criteria`` or from
    a default set embedded in the config.

    Args:
        sharpe_threshold: Minimum Sharpe ratio (default 1.5).
        max_drawdown_threshold: Maximum drawdown percentage (default 15.0).
        min_profit_factor: Minimum profit factor (default 1.5).
        min_win_rate: Minimum win rate (default 0.50).
        min_trades: Minimum number of trades (default 100).
        wf_degradation_threshold: OOS/IS ratio threshold (default 0.7).
    """

    def __init__(
        self,
        sharpe_threshold: float = 1.5,
        max_drawdown_threshold: float = 15.0,
        min_profit_factor: float = 1.5,
        min_win_rate: float = 0.50,
        min_trades: int = 100,
        wf_degradation_threshold: float = WF_DEGRADATION_THRESHOLD,
    ) -> None:
        self._sharpe_threshold = sharpe_threshold
        self._max_drawdown_threshold = max_drawdown_threshold
        self._min_profit_factor = min_profit_factor
        self._min_win_rate = min_win_rate
        self._min_trades = min_trades
        self._wf_degradation_threshold = wf_degradation_threshold
        self._aggregator = StatisticsAggregator()

    # ── Task 3.6: Acceptance Criteria Evaluation ────────────────────────────────

    def evaluate(
        self,
        statistics: dict[str, Any],
        aggregate_stats: Optional[dict[str, Any]] = None,
        monte_carlo_bands: Optional[dict[int, list[float]]] = None,
    ) -> dict[str, Any]:
        """Evaluate campaign statistics against acceptance criteria.

        Checks: Sharpe ratio, max drawdown, profit factor, win rate, total trades.

        Args:
            statistics: Dict with computed stats (from ``StatsResult.model_dump()``).
            aggregate_stats: Optional aggregate stats across campaigns.
            monte_carlo_bands: Optional MC bands for additional checks.

        Returns:
            Dict with:
                - ``review_decision``: ``"ACCEPT"``, ``"ITERATE"``, or ``"REJECT"``
                - ``failed_checks``: list of failed check names
                - ``iteration_proposal``: structured proposal if decision is not ACCEPT
                - ``check_results``: dict of individual check results
        """
        # Extract metrics from statistics dict (handle both camelCase and snake_case)
        sharpe = statistics.get("sharpe_ratio") or statistics.get("sharpe", 0.0)
        mdd = statistics.get("max_drawdown") or statistics.get("max_dd", 0.0)
        profit_factor = statistics.get("profit_factor") or statistics.get("pf", 0.0)
        win_rate = statistics.get("win_rate") or statistics.get("winrate", 0.0)
        total_trades = statistics.get("total_trades") or statistics.get("trades", 0)
        net_profit = statistics.get("net_profit", 0.0)

        # Handle None values
        sharpe = sharpe or 0.0
        mdd = mdd or 0.0
        profit_factor = profit_factor or 0.0
        win_rate = win_rate or 0.0
        total_trades = total_trades or 0
        net_profit = net_profit or 0.0

        # Run each check
        check_results: dict[str, bool] = {}
        failed_checks: list[str] = []

        # Sharpe check
        check_results["sharpe"] = sharpe >= self._sharpe_threshold
        if not check_results["sharpe"]:
            failed_checks.append("sharpe")

        # Max drawdown check (mdd is a percentage like 10.0 for 10%)
        check_results["max_drawdown"] = mdd <= self._max_drawdown_threshold
        if not check_results["max_drawdown"]:
            failed_checks.append("max_drawdown")

        # Profit factor check
        check_results["profit_factor"] = profit_factor >= self._min_profit_factor
        if not check_results["profit_factor"]:
            failed_checks.append("profit_factor")

        # Win rate check
        check_results["win_rate"] = win_rate >= self._min_win_rate
        if not check_results["win_rate"]:
            failed_checks.append("win_rate")

        # Trades count check
        check_results["total_trades"] = total_trades >= self._min_trades
        if not check_results["total_trades"]:
            failed_checks.append("total_trades")

        # Determine decision
        # ITERATE when up to 3 checks fail (still worth refining)
        # REJECT when 4+ checks fail (fundamentally unsound)
        if not failed_checks:
            decision = ReviewDecision.ACCEPT
            iteration_proposal = None
        elif len(failed_checks) <= 3:
            decision = ReviewDecision.ITERATE
            iteration_proposal = self.generate_iteration_proposal(
                failed_checks=failed_checks,
                statistics=statistics,
            )
        else:
            decision = ReviewDecision.REJECT
            iteration_proposal = self.generate_iteration_proposal(
                failed_checks=failed_checks,
                statistics=statistics,
            )

        result: dict[str, Any] = {
            "review_decision": decision,
            "failed_checks": failed_checks,
            "check_results": check_results,
            "iteration_proposal": iteration_proposal,
        }

        # Include aggregate and MC checks if provided
        if aggregate_stats:
            result["aggregate_assessment"] = self._assess_aggregates(aggregate_stats)

        if monte_carlo_bands:
            mc_check = self.check_mc_overfitting(
                live_equity=None,
                monte_carlo_bands=monte_carlo_bands,
            )
            result["mc_overfit_flag"] = mc_check.get("mc_overfit_flag", False)

        return result

    def _assess_aggregates(self, aggregate_stats: dict[str, Any]) -> dict[str, Any]:
        """Assess aggregate statistics across campaigns.

        Args:
            aggregate_stats: Dict of metric -> AggregateStats dict.

        Returns:
            Dict with aggregate assessment.
        """
        assessment: dict[str, Any] = {}
        for metric, agg in aggregate_stats.items():
            if isinstance(agg, dict):
        # Check if mean meets threshold for this metric
                mean_val = agg.get("mean", 0)
                if metric == "sharpe":
                    assessment[metric] = mean_val >= self._sharpe_threshold
                elif metric == "profit_factor":
                    assessment[metric] = mean_val >= self._min_profit_factor
                elif metric == "win_rate":
                    assessment[metric] = mean_val >= self._min_win_rate
                elif metric == "max_drawdown":
                    assessment[metric] = mean_val <= self._max_drawdown_threshold
        return assessment

    # ── Task 3.7: Walk-Forward Degradation Detection ────────────────────────────

    def check_wf_overfitting(
        self,
        is_metrics: list[float],
        oos_metrics: list[float],
        metric_name: str = "sharpe",
    ) -> dict[str, Any]:
        """Check walk-forward optimization for in-sample vs out-of-sample degradation.

        Computes the degradation ratio = mean(OOS) / mean(IS).
        A ratio below ``wf_degradation_threshold`` (default 0.7) flags overfitting.

        Args:
            is_metrics: List of in-sample metric values per cycle.
            oos_metrics: List of out-of-sample metric values per cycle.
            metric_name: Name of the metric being compared (default "sharpe").

        Returns:
            Dict with:
                - ``overfitting_flag``: bool
                - ``degradation_ratio``: float
                - ``mean_is``: float
                - ``mean_oos``: float
                - ``iteration_proposal``: str (if overfitting detected)
        """
        if not is_metrics or not oos_metrics:
            return {
                "overfitting_flag": False,
                "degradation_ratio": float("nan"),
                "mean_is": float("nan"),
                "mean_oos": float("nan"),
                "error": "Empty metric lists — cannot compute degradation",
            }

        if len(is_metrics) != len(oos_metrics):
            logger.warning(
                "IS/OOS metric length mismatch: IS=%d, OOS=%d",
                len(is_metrics), len(oos_metrics),
            )

        mean_is = sum(is_metrics) / len(is_metrics)
        mean_oos = sum(oos_metrics) / len(oos_metrics)

        degradation_ratio = mean_oos / mean_is if mean_is > 0 else float("nan")
        overfitting_flag = degradation_ratio < self._wf_degradation_threshold

        result: dict[str, Any] = {
            "overfitting_flag": overfitting_flag,
            "degradation_ratio": round(degradation_ratio, 4) if not math.isnan(degradation_ratio) else None,
            "mean_is": round(mean_is, 4),
            "mean_oos": round(mean_oos, 4),
            "metric": metric_name,
            "threshold": self._wf_degradation_threshold,
        }

        if overfitting_flag:
            result["iteration_proposal"] = (
                f"Walk-forward {metric_name} degradation detected: "
                f"IS={mean_is:.2f}, OOS={mean_oos:.2f}, "
                f"ratio={degradation_ratio:.2f} < {self._wf_degradation_threshold}. "
                "Reduce parameter space, increase OOS window, add regularization."
            )

        return result

    # ── Task 3.7: Monte Carlo Overfitting Check ─────────────────────────────────

    def check_mc_overfitting(
        self,
        live_equity: Optional[list[float]],
        monte_carlo_bands: dict[int, list[float]],
    ) -> dict[str, Any]:
        """Check if live/backtest equity breaches MC percentile bands.

        When ``live_equity`` is provided (from monitoring), compares it against
        the MC p10/p50/p90 bands. When None, inspects the backtest equity from
        MC bands for overfitting signals (p10 curve dropping below zero).

        Args:
            live_equity: Optional list of live equity values.
            monte_carlo_bands: Dict with percentile -> equity curve values.

        Returns:
            Dict with ``mc_overfit_flag``, ``breach_trade``, ``severity``.
        """
        p10_curve = monte_carlo_bands.get(10, [])
        p50_curve = monte_carlo_bands.get(50, [])
        p90_curve = monte_carlo_bands.get(90, [])

        if not p10_curve:
            return {
                "mc_overfit_flag": False,
                "error": "No MC p10 band available",
            }

        if live_equity:
            # Compare live equity against MC bands
            min_len = min(len(live_equity), len(p10_curve))
            for i in range(min_len):
                if live_equity[i] < p10_curve[i]:
                    # Early breach (first 50% of equity curve) = HIGH severity
                    # Late breach (last 50%) = MEDIUM severity
                    if i < len(live_equity) * 0.5:
                        severity = MC_BREACH_SEVERITY_HIGH
                    else:
                        severity = MC_BREACH_SEVERITY_MEDIUM

                    return {
                        "mc_overfit_flag": True,
                        "breach_trade": i,
                        "severity": severity,
                        "live_equity_at_breach": live_equity[i],
                        "p10_at_breach": p10_curve[i],
                    }

            return {
                "mc_overfit_flag": False,
                "breach_trade": None,
                "severity": None,
            }
        else:
            # Backtest check: inspect p10 curve for signs of overfitting
            negative_indices = [i for i, v in enumerate(p10_curve) if v < 0]
            if negative_indices:
                first_neg = negative_indices[0]
                severity = MC_BREACH_SEVERITY_HIGH
                if first_neg > len(p10_curve) * 0.7:
                    severity = MC_BREACH_SEVERITY_MEDIUM

                return {
                    "mc_overfit_flag": True,
                    "breach_trade": first_neg,
                    "severity": severity,
                    "p10_curve": p10_curve[:5],  # First 5 values for context
                    "note": "Backtest MC p10 crosses zero — potential overfitting",
                }

            return {
                "mc_overfit_flag": False,
                "breach_trade": None,
                "severity": None,
            }

    # ── Task 3.7: Benchmark Comparison ───────────────────────────────────────────

    @staticmethod
    def _has_alpha(alpha: float) -> bool:
        """Check if alpha is a meaningful positive value (not nan)."""
        return alpha is not None and not (isinstance(alpha, float) and math.isnan(alpha))

    def compare_benchmark(
        self,
        strategy_returns: list[float],
        benchmark_returns: list[float],
        risk_free_rate: float = 0.0,
    ) -> dict[str, Any]:
        """Compare strategy returns against a benchmark.

        Delegates to ``StatisticsAggregator.benchmark_compare()`` and returns
        a verdict and suggested actions.

        Args:
            strategy_returns: List of strategy period returns.
            benchmark_returns: List of benchmark period returns (same length).
            risk_free_rate: Risk-free rate per period.

        Returns:
            Dict with ``BenchmarkComparison`` fields plus ``benchmark_verdict``
            and optional ``iteration_proposal``.
        """
        if not strategy_returns or not benchmark_returns:
            return {
                "benchmark_verdict": "INSUFFICIENT_DATA",
                "error": "Empty return series",
            }

        if len(strategy_returns) != len(benchmark_returns):
            return {
                "benchmark_verdict": "ERROR",
                "error": (
                    f"Return series length mismatch: "
                    f"strategy={len(strategy_returns)}, benchmark={len(benchmark_returns)}"
                ),
            }

        try:
            comparison = self._aggregator.benchmark_compare(
                strategy_returns=strategy_returns,
                benchmark_returns=benchmark_returns,
                risk_free_rate=risk_free_rate,
            )
        except ValueError as e:
            return {
                "benchmark_verdict": "ERROR",
                "error": str(e),
            }

        comparison_dict = (
            comparison.model_dump() if hasattr(comparison, "model_dump") else {}
        )

        # Determine verdict
        alpha = comparison_dict.get("alpha", 0.0)
        info_ratio = comparison_dict.get("information_ratio", 0.0)
        beta = comparison_dict.get("beta", 1.0)
        tracking_error = comparison_dict.get("tracking_error", 0.0)

        # Handle nan values from constant return series
        alpha_valid = self._has_alpha(alpha)
        ir_valid = info_ratio is not None and not (isinstance(info_ratio, float) and math.isnan(info_ratio))

        if alpha_valid and alpha > 0 and ir_valid and info_ratio > 0.5:
            verdict = "OUTPERFORMS"
            iteration_proposal = None
        elif alpha_valid and alpha > 0:
            verdict = "NEUTRAL"
            iteration_proposal = None
        else:
            # Fall back to comparing mean returns directly if nan metrics
            strat_mean = sum(strategy_returns) / len(strategy_returns)
            bench_mean = sum(benchmark_returns) / len(benchmark_returns)

            if strat_mean > bench_mean:
                verdict = "OUTPERFORMS"
                iteration_proposal = None
                comparison_dict["alpha"] = strat_mean - bench_mean
                comparison_dict["information_ratio"] = float("nan")
                comparison_dict["benchmark_override"] = "mean_comparison"
            elif strat_mean < bench_mean:
                verdict = "UNDERPERFORMS"
                suggestions = ["Review market regime alignment"]
                iteration_proposal = (
                    f"Benchmark underperformance: strategy_mean={strat_mean:.6f}, "
                    f"benchmark_mean={bench_mean:.6f}. "
                    + " ".join(suggestions)
                )
                comparison_dict["alpha"] = strat_mean - bench_mean
                comparison_dict["information_ratio"] = float("nan")
                comparison_dict["benchmark_override"] = "mean_comparison"
            else:
                verdict = "NEUTRAL"
                iteration_proposal = None

        comparison_dict["benchmark_verdict"] = verdict
        comparison_dict["iteration_proposal"] = iteration_proposal

        return comparison_dict

    # ── Task 3.6: Iteration Proposal Generation ─────────────────────────────────

    def generate_iteration_proposal(
        self,
        failed_checks: list[str],
        statistics: dict[str, Any],
        wf_degradation: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Generate a structured iteration proposal based on failed checks.

        Creates parameter change suggestions and new hypotheses to address
        each failed acceptance criterion.

        Args:
            failed_checks: List of failed check names (e.g. ``["sharpe", "max_drawdown"]``).
            statistics: Dict with computed statistics.
            wf_degradation: Optional walk-forward degradation result.

        Returns:
            Dict with:
                - ``action``: str ("MODIFY_AND_RETEST")
                - ``parameter_changes``: dict of suggested changes
                - ``new_hypotheses``: list of hypothesis strings
                - ``rationale``: str summarizing failures
        """
        parameter_changes: dict[str, Any] = {}
        new_hypotheses: list[str] = []
        rationale_parts: list[str] = []

        for check in failed_checks:
            if check == "sharpe":
                current = statistics.get("sharpe_ratio") or statistics.get("sharpe", "?")
                parameter_changes["position_size"] = "0.5x"
                parameter_changes["add_filter"] = "trend_confirmation"
                new_hypotheses.append("Trend confirmation filter improves risk-adjusted returns")
                rationale_parts.append(f"Sharpe {current}<{self._sharpe_threshold}")

            elif check == "max_drawdown":
                current = statistics.get("max_drawdown") or statistics.get("max_dd", "?")
                parameter_changes["position_size"] = "0.5x"
                parameter_changes["add_filter"] = "ATR>20"
                parameter_changes["stop_loss"] = "tighter"
                new_hypotheses.append("Volatility filter reduces drawdown in choppy markets")
                rationale_parts.append(f"MDD {current}%>{self._max_drawdown_threshold}%")

            elif check == "profit_factor":
                current = statistics.get("profit_factor") or statistics.get("pf", "?")
                parameter_changes["take_profit"] = "2.0x"
                parameter_changes["add_filter"] = "quality_entry"
                new_hypotheses.append("Higher take-profit target improves profit factor")
                rationale_parts.append(f"PF {current}<{self._min_profit_factor}")

            elif check == "win_rate":
                current = statistics.get("win_rate") or statistics.get("winrate", "?")
                parameter_changes["entry_filter"] = "tighten"
                parameter_changes["add_filter"] = "confirmation"
                new_hypotheses.append("Tighter entry filter improves win rate")
                rationale_parts.append(f"Win rate {current}<{self._min_win_rate}")

            elif check == "total_trades":
                current = statistics.get("total_trades") or statistics.get("trades", "?")
                parameter_changes["data_range"] = "extend"
                new_hypotheses.append("Extended data range increases sample size for robust metrics")
                rationale_parts.append(f"Trades {current}<{self._min_trades}")

        # Add WF degradation to rationale if present
        if wf_degradation and wf_degradation.get("overfitting_flag"):
            ratio = wf_degradation.get("degradation_ratio", "?")
            rationale_parts.append(f"WF degradation ratio {ratio}")
            new_hypotheses.append("Regularization reduces walk-forward overfitting")
            parameter_changes["parameter_space"] = "reduce"
            parameter_changes["oos_window"] = "increase"

        return {
            "action": "MODIFY_AND_RETEST",
            "parameter_changes": parameter_changes,
            "new_hypotheses": new_hypotheses,
            "rationale": "; ".join(rationale_parts) if rationale_parts else "All checks passed",
            "failed_checks": failed_checks,
        }

    # ── Task 3.8: Pipeline Context Integration ──────────────────────────────────

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Execute the reviewer agent stage.

        Implements ``ReviewStage.execute()`` per the pipeline contract.

        Reads ``statistics``, ``aggregate_stats``, ``monte_carlo_bands`` from
        context artifacts (written by ``StatisticsAgent``).

        Args:
            ctx: ``PipelineContext`` with statistics artifacts.

        Returns:
            Dict with review decision, iteration proposal, and checks.
        """
        return await self.run(ctx)

    async def run(self, context: PipelineContext) -> dict[str, Any]:
        """Execute the reviewer agent stage.

        Args:
            context: ``PipelineContext`` with statistics, aggregate_stats,
                     and monte_carlo_bands in artifacts.

        Returns:
            Dict with ``review_decision``, ``iteration_proposal``,
            ``wf_degradation``, ``mc_overfit_flag``, ``benchmark_comparison``.
        """
        statistics = context.artifacts.get("statistics", {})
        aggregate_stats = context.artifacts.get("aggregate_stats", {})
        monte_carlo_bands = context.artifacts.get("monte_carlo_bands", {})

        if not statistics:
            logger.warning(
                "No statistics found in context artifacts — returning default review decision"
            )
            return {
                "review_decision": "needs_review",
                "iteration_proposal": None,
                "wf_degradation": {"overfitting_flag": False, "degradation_ratio": None},
                "mc_overfit_flag": False,
                "benchmark_comparison": {},
                "gate_decision_HUMAN_APPROVE_ITERATION": {"status": "pending", "decision": "abstain"},
            }

        # Task 3.6: Evaluate acceptance criteria
        evaluation = self.evaluate(
            statistics=statistics,
            aggregate_stats=aggregate_stats if aggregate_stats else None,
            monte_carlo_bands=monte_carlo_bands if monte_carlo_bands else None,
        )

        review_decision = evaluation["review_decision"]
        iteration_proposal = evaluation["iteration_proposal"]

        # Task 3.7: MC overfitting check from backtest MC bands
        mc_overfit = self.check_mc_overfitting(
            live_equity=None,
            monte_carlo_bands=monte_carlo_bands if monte_carlo_bands else {},
        )

        # Walk-forward check — read WF cycles from context if available
        wf_cycles = context.artifacts.get("wf_cycles", context.artifacts.get("walkforward_cycles", None))
        wf_degradation: dict[str, Any] = {
            "overfitting_flag": False,
            "degradation_ratio": None,
            "note": "No walk-forward data available in context",
        }
        if wf_cycles:
            # Extract IS and OOS metrics from WF cycles
            is_metrics = [c.get("in_sample", {}).get("sharpe", 0) for c in wf_cycles]
            oos_metrics = [c.get("out_of_sample", {}).get("sharpe", 0) for c in wf_cycles]
            if is_metrics and oos_metrics:
                wf_degradation = self.check_wf_overfitting(is_metrics, oos_metrics)

        # Benchmark comparison — check context for benchmark data
        benchmark_comparison: dict[str, Any] = {
            "benchmark_verdict": "NO_DATA",
            "note": "No benchmark data available in context",
            "alpha": None,
            "beta": None,
            "information_ratio": None,
        }
        strategy_returns = context.artifacts.get("strategy_returns")
        benchmark_returns = context.artifacts.get("benchmark_returns")
        if strategy_returns and benchmark_returns:
            benchmark_comparison = self.compare_benchmark(
                strategy_returns=strategy_returns,
                benchmark_returns=benchmark_returns,
            )

        # If iteration proposal exists and we have WF degradation, merge
        if iteration_proposal and wf_degradation.get("overfitting_flag"):
            merged = dict(iteration_proposal)
            merged["new_hypotheses"] = merged.get("new_hypotheses", []) + [
                wf_degradation.get("iteration_proposal", "")
            ]
            merged["rationale"] += f"; WF degradation ratio {wf_degradation.get('degradation_ratio')}"
            merged["parameter_changes"]["parameter_space"] = "reduce"
            iteration_proposal = merged

        # Write to context artifacts
        context.artifacts["review_decision"] = review_decision
        context.artifacts["iteration_proposal"] = iteration_proposal
        context.artifacts["wf_degradation"] = wf_degradation
        context.artifacts["mc_overfit_flag"] = mc_overfit.get("mc_overfit_flag", False)
        context.artifacts["benchmark_comparison"] = benchmark_comparison

        logger.info(
            "ReviewerAgent: decision=%s, failed=%s",
            review_decision,
            evaluation.get("failed_checks", []),
        )

        return {
            "review_decision": review_decision,
            "iteration_proposal": iteration_proposal,
            "wf_degradation": wf_degradation,
            "mc_overfit_flag": mc_overfit.get("mc_overfit_flag", False),
            "benchmark_comparison": benchmark_comparison,
        }
