"""Integration tests for the Statistics → Reviewer → Portfolio agent chain — tasks 3.14-3.18.

Verifies that:
1. StatisticsAgent produces artifacts consumed by ReviewerAgent
2. ReviewerAgent produces review_decision consumed by PortfolioAgent
3. All agents work with a shared PipelineContext
4. Artifact I/O matches the requires/provides contracts

Uses synthetic data — no SQX dependency.
"""

import csv
import os
import tempfile

import pytest

from quantlab.agents.statistics_agent import StatisticsAgent
from quantlab.agents.reviewer_agent import ReviewerAgent
from quantlab.agents.portfolio_agent import PortfolioAgent
from quantlab.pipeline.base import PipelineContext


def _create_export_dir(trades: list[float], equity: list[float]) -> str:
    """Create a temporary export directory with trades.csv and equity.csv."""
    tmp_dir = tempfile.mkdtemp()

    trades_path = os.path.join(tmp_dir, "trades.csv")
    with open(trades_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["profit", "entry_time", "exit_time", "direction", "lots"])
        for p in trades:
            writer.writerow([p, "2024-01-01T00:00:00", "2024-01-02T00:00:00", "LONG", 1.0])

    equity_path = os.path.join(tmp_dir, "equity.csv")
    with open(equity_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["equity", "timestamp"])
        for i, e in enumerate(equity):
            # Use ordinal date format to avoid hour/day overflow
            from datetime import datetime, timedelta
            ts = datetime(2024, 1, 1) + timedelta(hours=i)
            writer.writerow([e, ts.isoformat()])

    return tmp_dir


class TestStatisticsReviewerChain:
    """Task 3.17: Statistics → Reviewer chain with shared PipelineContext."""

    @pytest.mark.asyncio
    async def test_statistics_to_reviewer_chain(self) -> None:
        """GIVEN a shared PipelineContext with export_paths
        WHEN StatisticsAgent writes statistics, THEN ReviewerAgent reads them
        AND produces a coherent review decision.
        """
        # Create export data: 60% win rate, decent equity curve
        n_trades = 200
        trades = [100.0] * 120 + [-50.0] * 80  # 60% win rate
        equity = [10000.0 + i * 30 for i in range(n_trades + 1)]  # Steady growth

        tmp_dir = _create_export_dir(trades, equity)
        try:
            export_paths = [
                os.path.join(tmp_dir, "trades.csv"),
                os.path.join(tmp_dir, "equity.csv"),
            ]

            ctx = PipelineContext(
                config={},
                artifacts={"export_paths": export_paths},
            )

            # --- StatisticsAgent ---
            stats_agent = StatisticsAgent(n_simulations=100, mc_seed=42)
            stats_result = await stats_agent.run(ctx)

            # Verify StatisticsAgent outputs
            assert "statistics" in stats_result
            assert "monte_carlo_bands" in stats_result
            assert "rolling_metrics" in stats_result

            statistics = stats_result["statistics"]
            assert statistics["total_trades"] == n_trades
            assert statistics["win_rate"] == 0.6

            # --- ReviewerAgent ---
            review_agent = ReviewerAgent(
                sharpe_threshold=1.0,
                max_drawdown_threshold=20.0,
                min_profit_factor=1.2,
                min_win_rate=0.40,
                min_trades=100,
            )
            review_result = await review_agent.run(ctx)

            # Verify ReviewerAgent consumed StatisticsAgent outputs
            assert review_result["review_decision"] in ("ACCEPT", "ITERATE", "REJECT")
            assert "iteration_proposal" in review_result
            assert "wf_degradation" in review_result
            assert "mc_overfit_flag" in review_result

            # Context should have all artifacts from both agents
            assert "statistics" in ctx.artifacts
            assert "monte_carlo_bands" in ctx.artifacts
            assert "review_decision" in ctx.artifacts
            assert "iteration_proposal" in ctx.artifacts

        finally:
            import shutil
            shutil.rmtree(tmp_dir)

    @pytest.mark.asyncio
    async def test_weak_strategy_triggers_iterate(self) -> None:
        """GIVEN a weak strategy with low Sharpe and high drawdown
        WHEN the Stats → Review chain runs
        THEN review_decision = ITERATE or REJECT.
        """
        # Weak strategy: 40% win rate, declining equity
        trades = [50.0] * 40 + [-80.0] * 60  # 40% win rate
        # Declining equity
        equity = [10000.0 - i * 10 for i in range(101)]

        tmp_dir = _create_export_dir(trades, equity)
        try:
            export_paths = [
                os.path.join(tmp_dir, "trades.csv"),
                os.path.join(tmp_dir, "equity.csv"),
            ]

            ctx = PipelineContext(
                config={},
                artifacts={"export_paths": export_paths},
            )

            # Statistics
            stats_agent = StatisticsAgent(n_simulations=100, mc_seed=42)
            await stats_agent.run(ctx)

            # Review with moderate criteria
            review_agent = ReviewerAgent(
                sharpe_threshold=1.0,
                max_drawdown_threshold=10.0,
                min_profit_factor=1.3,
                min_win_rate=0.45,
                min_trades=50,
            )
            review_result = await review_agent.run(ctx)

            # Weak strategy should not be ACCEPT
            assert review_result["review_decision"] in ("REJECT", "ITERATE")

        finally:
            import shutil
            shutil.rmtree(tmp_dir)


class TestFullAgentChain:
    """Task 3.17: Full Statistics → Reviewer → Portfolio chain."""

    @pytest.mark.asyncio
    async def test_full_agent_chain(self) -> None:
        """GIVEN export data with good stats
        WHEN all three agents run sequentially with shared context
        THEN the portfolio is constructed with selected strategies.
        """
        # Strong strategy data
        trades = [100.0] * 150 + [-40.0] * 50  # 75% win rate
        equity = [10000.0 + i * 50 for i in range(201)]  # Strong uptrend

        tmp_dir = _create_export_dir(trades, equity)
        try:
            export_paths = [
                os.path.join(tmp_dir, "trades.csv"),
                os.path.join(tmp_dir, "equity.csv"),
            ]

            ctx = PipelineContext(
                config={},
                artifacts={
                    "export_paths": export_paths,
                    "selected_strategies": ["strat_1", "strat_2", "strat_3"],
                },
            )

            # --- StatisticsAgent ---
            stats_agent = StatisticsAgent(n_simulations=100, mc_seed=42)
            await stats_agent.run(ctx)

            # --- ReviewerAgent ---
            review_agent = ReviewerAgent(
                sharpe_threshold=0.5,
                max_drawdown_threshold=25.0,
                min_profit_factor=1.0,
                min_win_rate=0.30,
                min_trades=50,
            )
            await review_agent.run(ctx)

            # --- PortfolioAgent ---
            portfolio_agent = PortfolioAgent()
            await portfolio_agent.run(ctx)

            # Verify all artifacts are in context
            assert "statistics" in ctx.artifacts
            assert "monte_carlo_bands" in ctx.artifacts
            assert "review_decision" in ctx.artifacts
            assert "portfolio_cfx" in ctx.artifacts
            assert "portfolio_result" in ctx.artifacts
            assert "correlation_matrix" in ctx.artifacts
            assert "risk_allocation" in ctx.artifacts

            # Verify review_decision is ACCEPT (strong strategy)
            assert ctx.artifacts["review_decision"] == "ACCEPT"

            # Verify portfolio was constructed
            pr = ctx.artifacts["portfolio_result"]
            assert pr["status"] != "skipped"
            assert pr["status"] != "blocked"
            assert len(pr["selected_strategies"]) == 3

            # Verify correlation matrix has correct dimensions
            assert len(ctx.artifacts["correlation_matrix"]) == 3

            # Verify risk allocation has kelly results
            assert "kelly_results" in ctx.artifacts["risk_allocation"]

        finally:
            import shutil
            shutil.rmtree(tmp_dir)

    @pytest.mark.asyncio
    async def test_chain_with_weak_stats_shows_iterate(self) -> None:
        """GIVEN weak strategy data
        WHEN all three agents run
        THEN review_decision is ITERATE/REJECT, portfolio respects decision.
        """
        # Very weak: 35% win rate, sharp decline
        trades = [30.0] * 35 + [-70.0] * 65  # 35% win rate
        equity = [10000.0 - i * 20 for i in range(101)]  # Decline

        tmp_dir = _create_export_dir(trades, equity)
        try:
            export_paths = [
                os.path.join(tmp_dir, "trades.csv"),
                os.path.join(tmp_dir, "equity.csv"),
            ]

            ctx = PipelineContext(
                config={},
                artifacts={
                    "export_paths": export_paths,
                    "selected_strategies": ["strat_1"],
                },
            )

            stats_agent = StatisticsAgent(n_simulations=100, mc_seed=42)
            await stats_agent.run(ctx)

            review_agent = ReviewerAgent(
                sharpe_threshold=2.0,
                max_drawdown_threshold=5.0,
                min_profit_factor=2.0,
                min_win_rate=0.60,
                min_trades=200,
            )
            await review_agent.run(ctx)

            portfolio_agent = PortfolioAgent()
            await portfolio_agent.run(ctx)

            # Weak strategy => non-ACCEPT
            assert ctx.artifacts["review_decision"] in ("ITERATE", "REJECT")

        finally:
            import shutil
            shutil.rmtree(tmp_dir)
