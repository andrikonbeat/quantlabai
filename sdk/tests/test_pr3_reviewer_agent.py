"""Tests for ReviewerAgent — tasks 3.5-3.8, 3.15.

Tests criteria evaluation, walk-forward degradation, MC overfitting,
benchmark comparison, iteration proposal generation, and pipeline integration.
"""

import pytest

from quantlab.agents.reviewer_agent import ReviewerAgent
from quantlab.pipeline.base import PipelineContext


class TestEvaluate:
    """Task 3.6 + 3.15: ReviewerAgent.evaluate()."""

    def test_accept_when_all_criteria_met(self) -> None:
        """GIVEN stats: sharpe=1.6, mdd=10%, pf=1.8, win_rate=55%, trades=150
        AND criteria: min_sharpe=1.5, max_drawdown=15%, min_pf=1.5, min_win_rate=50%, min_trades=100
        WHEN evaluate() is called
        THEN decision = ACCEPT, no failed checks.
        """
        agent = ReviewerAgent(
            sharpe_threshold=1.5,
            max_drawdown_threshold=15.0,
            min_profit_factor=1.5,
            min_win_rate=0.50,
            min_trades=100,
        )
        statistics = {
            "sharpe_ratio": 1.6,
            "max_drawdown": 10.0,
            "profit_factor": 1.8,
            "win_rate": 0.55,
            "total_trades": 150,
            "net_profit": 5000.0,
        }

        result = agent.evaluate(statistics)

        assert result["review_decision"] == "ACCEPT"
        assert result["failed_checks"] == []
        assert result["iteration_proposal"] is None

    def test_iterate_when_sharpe_fails(self) -> None:
        """GIVEN stats: sharpe=1.2, mdd=18%, pf=1.3
        AND criteria: min_sharpe=1.5, max_drawdown=15%, min_pf=1.5
        WHEN evaluate() is called
        THEN decision = ITERATE, failed_checks = ["sharpe", "max_drawdown", "profit_factor"].
        """
        agent = ReviewerAgent(
            sharpe_threshold=1.5,
            max_drawdown_threshold=15.0,
            min_profit_factor=1.5,
            min_win_rate=0.50,
            min_trades=100,
        )
        statistics = {
            "sharpe_ratio": 1.2,
            "max_drawdown": 18.0,
            "profit_factor": 1.3,
            "win_rate": 0.55,
            "total_trades": 150,
        }

        result = agent.evaluate(statistics)

        assert result["review_decision"] == "ITERATE"
        assert "sharpe" in result["failed_checks"]
        assert "max_drawdown" in result["failed_checks"]
        assert "profit_factor" in result["failed_checks"]
        assert result["iteration_proposal"] is not None
        # Check iteration proposal has rationale with all failures
        assert "Sharpe" in result["iteration_proposal"]["rationale"]
        assert "MDD" in result["iteration_proposal"]["rationale"]
        assert "PF" in result["iteration_proposal"]["rationale"]

    def test_reject_when_many_checks_fail(self) -> None:
        """GIVEN stats with 3+ failed checks
        WHEN evaluate() is called
        THEN decision = REJECT.
        """
        agent = ReviewerAgent(
            sharpe_threshold=1.5,
            max_drawdown_threshold=15.0,
            min_profit_factor=1.5,
            min_win_rate=0.50,
            min_trades=100,
        )
        statistics = {
            "sharpe_ratio": 0.5,
            "max_drawdown": 35.0,
            "profit_factor": 0.8,
            "win_rate": 0.20,
            "total_trades": 30,
        }

        result = agent.evaluate(statistics)

        assert result["review_decision"] == "REJECT"
        assert len(result["failed_checks"]) >= 3
        assert result["iteration_proposal"] is not None

    def test_edge_sharpe_exactly_at_threshold(self) -> None:
        """GIVEN sharpe exactly at threshold (1.5)
        WHEN evaluate() is called
        THEN it passes the sharpe check.
        """
        agent = ReviewerAgent(sharpe_threshold=1.5)
        statistics = {
            "sharpe_ratio": 1.5,
            "max_drawdown": 10.0,
            "profit_factor": 1.8,
            "win_rate": 0.55,
            "total_trades": 150,
        }

        result = agent.evaluate(statistics)
        assert result["check_results"]["sharpe"] is True

    def test_all_checks_reported(self) -> None:
        """GIVEN statistics with all values
        WHEN evaluate() is called
        THEN all 5 checks (sharpe, max_drawdown, profit_factor, win_rate, total_trades) are reported.
        """
        agent = ReviewerAgent()
        statistics = {
            "sharpe_ratio": 1.6,
            "max_drawdown": 10.0,
            "profit_factor": 1.8,
            "win_rate": 0.55,
            "total_trades": 150,
        }

        result = agent.evaluate(statistics)
        assert set(result["check_results"].keys()) == {
            "sharpe", "max_drawdown", "profit_factor", "win_rate", "total_trades"
        }


class TestWalkForwardOverfitting:
    """Task 3.7: ReviewerAgent.check_wf_overfitting()."""

    def test_degradation_detected(self) -> None:
        """GIVEN WF cycles: IS sharpe=[2.1, 2.3, 2.0], OOS sharpe=[0.8, 0.5, 0.3]
        WHEN check_wf_overfitting() is called
        THEN overfitting_flag = TRUE, degradation_ratio approx 0.3.
        """
        agent = ReviewerAgent()
        is_metrics = [2.1, 2.3, 2.0]
        oos_metrics = [0.8, 0.5, 0.3]

        result = agent.check_wf_overfitting(is_metrics, oos_metrics)

        assert result["overfitting_flag"] is True
        assert result["degradation_ratio"] is not None
        assert result["degradation_ratio"] < 0.7
        # Mean OOS: (0.8+0.5+0.3)/3 = 0.533, Mean IS: (2.1+2.3+2.0)/3 = 2.133, Ratio = 0.25
        assert abs(result["degradation_ratio"] - 0.25) < 0.1
        assert "iteration_proposal" in result

    def test_wf_robust(self) -> None:
        """GIVEN IS sharpe=[1.8, 1.9], OOS sharpe=[1.5, 1.6]
        WHEN check_wf_overfitting() is called
        THEN overfitting_flag = FALSE, degradation_ratio > 0.7.
        """
        agent = ReviewerAgent()
        is_metrics = [1.8, 1.9]
        oos_metrics = [1.5, 1.6]

        result = agent.check_wf_overfitting(is_metrics, oos_metrics)

        assert result["overfitting_flag"] is False
        assert result["degradation_ratio"] is not None
        # Mean OOS: 1.55, Mean IS: 1.85, Ratio: 0.838
        assert result["degradation_ratio"] > 0.7
        assert "iteration_proposal" not in result

    def test_empty_metrics(self) -> None:
        """GIVEN empty metric lists
        WHEN check_wf_overfitting() is called
        THEN no overfitting flag, error is reported.
        """
        agent = ReviewerAgent()
        result = agent.check_wf_overfitting([], [])

        assert result["overfitting_flag"] is False
        assert "error" in result

    def test_custom_metric_name(self) -> None:
        """GIVEN IS and OOS for a non-Sharpe metric
        WHEN check_wf_overfitting(metric_name="profit_factor") is called
        THEN the result reflects the custom metric.
        """
        agent = ReviewerAgent()
        result = agent.check_wf_overfitting(
            is_metrics=[2.0, 2.5],
            oos_metrics=[0.5, 0.6],
            metric_name="profit_factor",
        )
        assert result["metric"] == "profit_factor"


class TestMonteCarloOverfitting:
    """Task 3.7: ReviewerAgent.check_mc_overfitting()."""

    def test_live_curve_below_p10(self) -> None:
        """GIVEN live equity curve and MC bands p10/p50/p90
        WHEN check_mc_overfitting() is called
        AND live curve crosses below p10 at trade 40
        THEN mc_overfit_flag = TRUE, breach_trade = 40, severity = HIGH.
        """
        agent = ReviewerAgent()
        # MC bands: p10 is flat at 1000
        mc_bands = {
            10: [1000.0] * 101,
            50: [2000.0] * 101,
            90: [3000.0] * 101,
        }
        # Live equity: stays above p10 for 40 trades, then drops below
        live_equity = [1500.0] * 41 + [500.0] * 60

        result = agent.check_mc_overfitting(live_equity, mc_bands)

        assert result["mc_overfit_flag"] is True
        assert result["breach_trade"] == 41  # 0-indexed
        assert result["severity"] == "HIGH"

    def test_live_curve_within_bands(self) -> None:
        """GIVEN live equity tracks near p50, never below p10
        WHEN check_mc_overfitting() is called
        THEN mc_overfit_flag = FALSE.
        """
        agent = ReviewerAgent()
        mc_bands = {
            10: [1000.0] * 101,
            50: [2000.0] * 101,
            90: [3000.0] * 101,
        }
        live_equity = [2000.0] * 101

        result = agent.check_mc_overfitting(live_equity, mc_bands)

        assert result["mc_overfit_flag"] is False
        assert result["breach_trade"] is None

    def test_backtest_p10_negative(self) -> None:
        """GIVEN backtest MC p10 curve goes negative
        WHEN check_mc_overfitting(live_equity=None) is called
        THEN mc_overfit_flag = TRUE.
        """
        agent = ReviewerAgent()
        mc_bands = {
            10: [1000.0] * 50 + [-500.0] * 51,
            50: [2000.0] * 101,
            90: [3000.0] * 101,
        }

        result = agent.check_mc_overfitting(live_equity=None, monte_carlo_bands=mc_bands)

        assert result["mc_overfit_flag"] is True
        assert result["breach_trade"] == 50
        assert result["severity"] == "HIGH"

    def test_no_p10_band(self) -> None:
        """GIVEN no p10 band in MC data
        WHEN check_mc_overfitting() is called
        THEN no overfitting flag.
        """
        agent = ReviewerAgent()
        result = agent.check_mc_overfitting(
            live_equity=[1000.0],
            monte_carlo_bands={},
        )
        assert result["mc_overfit_flag"] is False
        assert "error" in result


class TestBenchmarkComparison:
    """Task 3.7: ReviewerAgent.compare_benchmark()."""

    def test_strategy_beats_benchmark(self) -> None:
        """GIVEN strategy returns outperform benchmark
        WHEN compare_benchmark() is called
        THEN benchmark_verdict = "OUTPERFORMS", alpha > 0.
        """
        agent = ReviewerAgent()
        # Strategy: steady 1% returns; Benchmark: flat
        # Use non-constant returns so metrics are meaningful
        import numpy as np
        rng = np.random.RandomState(42)
        strategy_returns = [float(v) for v in rng.randn(100) * 0.005 + 0.01]
        benchmark_returns = [float(v) for v in rng.randn(100) * 0.008]

        result = agent.compare_benchmark(strategy_returns, benchmark_returns)

        assert result["benchmark_verdict"] == "OUTPERFORMS"
        assert result["alpha"] > 0
        assert result["information_ratio"] > 0.5

    def test_strategy_underperforms(self) -> None:
        """GIVEN strategy underperforms benchmark
        WHEN compare_benchmark() is called
        THEN benchmark_verdict = "UNDERPERFORMS", iteration_proposal is generated.
        """
        agent = ReviewerAgent()
        # Use non-constant returns so metrics are meaningful
        import numpy as np
        rng = np.random.RandomState(42)
        strategy_returns = [float(v) for v in rng.randn(100) * 0.005]
        benchmark_returns = [float(v) for v in rng.randn(100) * 0.01 + 0.005]

        result = agent.compare_benchmark(strategy_returns, benchmark_returns)

        assert result["benchmark_verdict"] == "UNDERPERFORMS"
        assert result["iteration_proposal"] is not None

    def test_empty_returns(self) -> None:
        """GIVEN empty return series
        WHEN compare_benchmark() is called
        THEN verdict = "INSUFFICIENT_DATA".
        """
        agent = ReviewerAgent()
        result = agent.compare_benchmark([], [])
        assert result["benchmark_verdict"] == "INSUFFICIENT_DATA"

    def test_mismatched_lengths(self) -> None:
        """GIVEN mismatched return lengths
        WHEN compare_benchmark() is called
        THEN it handles the error gracefully.
        """
        agent = ReviewerAgent()
        result = agent.compare_benchmark([0.01, 0.02], [0.01])
        assert result["benchmark_verdict"] == "ERROR"
        assert "error" in result


class TestIterationProposal:
    """Task 3.6: ReviewerAgent.generate_iteration_proposal()."""

    def test_proposal_covers_all_failures(self) -> None:
        """GIVEN failed checks: sharpe, mdd, wf_degradation
        WHEN generate_iteration_proposal() is called
        THEN iteration proposal includes parameter_changes, new_hypotheses, rationale.
        """
        agent = ReviewerAgent()
        statistics = {
            "sharpe_ratio": 1.2,
            "max_drawdown": 18.0,
            "profit_factor": 1.3,
        }
        wf_degradation = {
            "overfitting_flag": True,
            "degradation_ratio": 0.35,
        }

        proposal = agent.generate_iteration_proposal(
            failed_checks=["sharpe", "max_drawdown", "profit_factor"],
            statistics=statistics,
            wf_degradation=wf_degradation,
        )

        assert proposal["action"] == "MODIFY_AND_RETEST"
        assert len(proposal["parameter_changes"]) >= 1
        assert len(proposal["new_hypotheses"]) >= 1
        assert "Sharpe" in proposal["rationale"]
        assert "MDD" in proposal["rationale"]
        assert "PF" in proposal["rationale"]

    def test_empty_failed_checks(self) -> None:
        """GIVEN empty failed_checks list
        WHEN generate_iteration_proposal() is called
        THEN a minimal proposal is returned.
        """
        agent = ReviewerAgent()
        proposal = agent.generate_iteration_proposal(
            failed_checks=[],
            statistics={"sharpe_ratio": 2.0},
        )
        assert proposal["action"] == "MODIFY_AND_RETEST"
        assert proposal["rationale"] == "All checks passed"

    def test_failed_checks_in_rationale(self) -> None:
        """GIVEN specific failed checks
        WHEN generate_iteration_proposal() is called
        THEN all failed_checks are referenced in the rationale.
        """
        agent = ReviewerAgent()
        proposal = agent.generate_iteration_proposal(
            failed_checks=["sharpe", "win_rate"],
            statistics={"sharpe_ratio": 1.0, "win_rate": 0.3},
        )
        rationale_lower = proposal["rationale"].lower()
        hypotheses_lower = " ".join(proposal["new_hypotheses"]).lower()
        combined = rationale_lower + " " + hypotheses_lower
        # Check "sharpe" appears (from "Sharpe 1.0<1.5")
        assert "sharpe" in combined
        # Check win-related content appears (from "Win rate 0.3<0.5")
        assert "win" in combined


class TestRunMethod:
    """Task 3.8: ReviewerAgent.run(context)."""

    @pytest.mark.asyncio
    async def test_run_writes_context_artifacts(self) -> None:
        """GIVEN a PipelineContext with statistics
        WHEN run() is called
        THEN review_decision, iteration_proposal, etc. are written to context.
        """
        agent = ReviewerAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "statistics": {
                    "sharpe_ratio": 1.6,
                    "max_drawdown": 10.0,
                    "profit_factor": 1.8,
                    "win_rate": 0.55,
                    "total_trades": 150,
                    "net_profit": 5000.0,
                },
                "aggregate_stats": {},
                "monte_carlo_bands": {
                    10: [1000.0] * 51,
                    50: [2000.0] * 51,
                    90: [3000.0] * 51,
                },
            },
        )

        result = await agent.run(ctx)

        assert "review_decision" in ctx.artifacts
        assert ctx.artifacts["review_decision"] == "ACCEPT"
        assert "iteration_proposal" in ctx.artifacts
        assert "wf_degradation" in ctx.artifacts
        assert "mc_overfit_flag" in ctx.artifacts
        assert "benchmark_comparison" in ctx.artifacts

        assert "review_decision" in result
        assert result["review_decision"] == "ACCEPT"

    @pytest.mark.asyncio
    async def test_run_missing_statistics_raises(self) -> None:
        """GIVEN a PipelineContext without statistics
        WHEN run() is called
        THEN ValueError is raised.
        """
        agent = ReviewerAgent()
        ctx = PipelineContext(config={})

        with pytest.raises(ValueError, match="No statistics"):
            await agent.run(ctx)

    @pytest.mark.asyncio
    async def test_run_with_benchmark_data(self) -> None:
        """GIVEN context with benchmark returns
        WHEN run() is called
        THEN benchmark comparison is populated.
        """
        agent = ReviewerAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "statistics": {
                    "sharpe_ratio": 1.6,
                    "max_drawdown": 10.0,
                    "profit_factor": 1.8,
                    "win_rate": 0.55,
                    "total_trades": 150,
                },
                "strategy_returns": [0.01, 0.02, -0.01, 0.015, 0.005] * 10,
                "benchmark_returns": [0.001, 0.002, -0.003, 0.001, 0.0] * 10,
            },
        )

        result = await agent.run(ctx)
        assert ctx.artifacts["benchmark_comparison"]["benchmark_verdict"] == "OUTPERFORMS"
