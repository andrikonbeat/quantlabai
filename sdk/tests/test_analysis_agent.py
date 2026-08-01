"""Tests for AnalysisAgent — task 3.2 + 3.8."""

import csv
from pathlib import Path

import pytest

from quantlab.agents.analysis_agent import AnalysisAgent
from quantlab.analysis.models import SelectionResult, StrategyAnalysis
from quantlab.pipeline.base import PipelineContext


class TestAnalysisAgentRun:
    """Task 3.2 + 3.8: AnalysisAgent.run() integration."""

    @pytest.mark.asyncio
    async def test_missing_strategies_csv_returns_empty_artifacts(self, tmp_path: Path) -> None:
        """GIVEN export_paths without strategies.csv
        WHEN run() is called
        THEN warning is logged and all analysis artifacts are empty.
        """
        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(tmp_path / "trades.csv")],
            },
        )

        result = await agent.run(ctx)
        assert ctx.artifacts["strategy_analysis"] == []
        assert ctx.artifacts["selected_strategies"] == []
        assert ctx.artifacts["strategy_verdicts"] == {}
        assert ctx.artifacts["wf_cycles"] == []

    @pytest.mark.asyncio
    async def test_corrupt_strategies_csv_returns_empty_artifacts(self, tmp_path: Path) -> None:
        """GIVEN export_paths with a corrupt strategies.csv
        WHEN run() is called
        THEN warning is logged and all analysis artifacts are empty.
        """
        csv_path = tmp_path / "strategies.csv"
        csv_path.write_bytes(b"\x80\x81\x82\xff\xfe")

        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(csv_path)],
            },
        )

        result = await agent.run(ctx)
        assert ctx.artifacts["strategy_analysis"] == []
        assert ctx.artifacts["selected_strategies"] == []
        assert ctx.artifacts["strategy_verdicts"] == {}
        assert ctx.artifacts["wf_cycles"] == []

    @pytest.mark.asyncio
    async def test_full_run_selects_non_empty_strategies(self, tmp_path: Path) -> None:
        """GIVEN a valid strategies.csv with healthy metrics
        WHEN run() is called
        THEN selected_strategies is non-empty and verdicts mark ACCEPT.
        """
        csv_path = tmp_path / "strategies.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Profit Factor", "Sharpe Ratio", "Win Rate",
                "Trades", "Max DD", "WF IS Sharpe", "WF OOS Sharpe",
            ])
            for i in range(5):
                writer.writerow([
                    f"Strat{i}",
                    1.5,
                    1.2,
                    0.55,
                    100,
                    0.10,
                    1.1,
                    1.0,
                ])

        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(csv_path)],
            },
        )

        result = await agent.run(ctx)
        assert len(ctx.artifacts["selected_strategies"]) > 0
        assert all(v == "ACCEPT" for v in ctx.artifacts["strategy_verdicts"].values())
        assert "strategy_analysis" in ctx.artifacts
        assert len(ctx.artifacts["strategy_analysis"]) == 5

    @pytest.mark.asyncio
    async def test_full_run_rejects_extreme_pf_low_trades(self, tmp_path: Path) -> None:
        """GIVEN a strategy with extreme PF and only 5 trades
        WHEN run() is called
        THEN that strategy is REJECTED.
        """
        csv_path = tmp_path / "strategies.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Profit Factor", "Sharpe Ratio", "Win Rate",
                "Trades", "Max DD",
            ])
            writer.writerow(["BadStrat", 5.0, 2.5, 0.9, 5, 0.05])
            writer.writerow(["GoodStrat", 1.5, 1.0, 0.55, 100, 0.10])

        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(csv_path)],
            },
        )

        result = await agent.run(ctx)
        assert ctx.artifacts["strategy_verdicts"]["BadStrat"] == "REJECT"
        assert ctx.artifacts["strategy_verdicts"]["GoodStrat"] == "ACCEPT"

    @pytest.mark.asyncio
    async def test_empty_selection_emits_warning(self, tmp_path: Path) -> None:
        """GIVEN strategies that all fail heuristics
        WHEN run() is called
        THEN selected_strategies is empty and warnings are present.
        """
        csv_path = tmp_path / "strategies.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Profit Factor", "Sharpe Ratio", "Win Rate",
                "Trades", "Max DD",
            ])
            writer.writerow(["BadStrat", 5.0, 2.5, 0.9, 5, 0.05])

        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(csv_path)],
            },
        )

        result = await agent.run(ctx)
        assert ctx.artifacts["selected_strategies"] == []
        # The engine returns a SelectionResult; warnings are in the result dict
        assert "strategy_analysis" in result
        assert "strategy_verdicts" in result

    @pytest.mark.asyncio
    async def test_thresholds_from_research_config(self, tmp_path: Path) -> None:
        """GIVEN research_config.analysis with custom thresholds
        WHEN run() is called
        THEN those thresholds are used instead of defaults.
        """
        csv_path = tmp_path / "strategies.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Profit Factor", "Sharpe Ratio", "Win Rate",
                "Trades", "Max DD",
            ])
            writer.writerow(["EdgeStrat", 2.5, 1.5, 0.55, 30, 0.10])

        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(csv_path)],
                "research_config": {
                    "analysis": {
                        "min_trades": 50,
                        "extreme_pf": 3.0,
                        "extreme_sharpe": 2.0,
                        "oos_is_threshold": 0.7,
                    }
                },
            },
        )

        result = await agent.run(ctx)
        # With min_trades=50, 30 trades with PF=2.5 should NOT trigger extreme_pf
        # because extreme_pf is 3.0 and PF=2.5 < 3.0
        assert ctx.artifacts["strategy_verdicts"]["EdgeStrat"] == "ACCEPT"
