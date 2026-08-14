"""WU6 RED tests: AnalysisAgent Frame consumption (REQ-307, T-5.1).

Covers additive Frame reading:
- When Frame is present, AnalysisAgent includes market context in output.
- When Frame is absent, behavior is identical to current (no regression).

Strict TDD: written first — FAIL (RED) until AnalysisAgent reads Frame.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from quantlab.analysis.frame import Frame
from quantlab.pipeline.base import PipelineContext


class TestAnalysisAgentFrameConsumption:
    """AnalysisAgent additive Frame consumption."""

    @pytest.mark.asyncio
    async def test_frame_present_includes_market_context_in_output(self, tmp_path: Path) -> None:
        """GIVEN context.artifacts contains a Frame
        WHEN AnalysisAgent.run() is called
        THEN the returned dict includes a 'market_context' key
        AND it contains the frame's regime, sentiment, and timeframe.
        """
        from quantlab.agents.analysis_agent import AnalysisAgent

        csv_path = tmp_path / "strategies.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Profit Factor", "Sharpe Ratio", "Win Rate",
                "Trades", "Max DD", "WF IS Sharpe", "WF OOS Sharpe",
            ])
            writer.writerow([
                "Strat0", 1.5, 1.2, 0.55, 100, 0.10, 1.1, 1.0,
            ])

        frame = Frame(
            regime="trending",
            regime_confidence=0.8,
            sentiment=0.5,
            timeframe="H1",
            edge="trend-following",
            instruments=["EURUSD"],
            guardian_hints={
                "regime_shift": {"detected": False, "confidence": 0.0, "recommended_action": "none"},
                "sentiment_shift": {"detected": False, "confidence": 0.0, "recommended_action": "none"},
                "volatility_expansion": {"detected": False, "confidence": 0.0, "recommended_action": "none"},
            },
        )

        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(csv_path)],
                "frame": frame.to_json(),
            },
        )

        result = await agent.run(ctx)
        assert "market_context" in result, "AnalysisAgent must include 'market_context' when Frame is present"
        assert result["market_context"]["regime"] == "trending"
        assert result["market_context"]["sentiment"] == 0.5
        assert result["market_context"]["timeframe"] == "H1"

    @pytest.mark.asyncio
    async def test_frame_absent_preserves_original_behavior(self, tmp_path: Path) -> None:
        """GIVEN context.artifacts does NOT contain a Frame
        WHEN AnalysisAgent.run() is called
        THEN the returned dict has only the original keys
        AND no 'market_context' key is added.
        """
        from quantlab.agents.analysis_agent import AnalysisAgent

        csv_path = tmp_path / "strategies.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Profit Factor", "Sharpe Ratio", "Win Rate",
                "Trades", "Max DD", "WF IS Sharpe", "WF OOS Sharpe",
            ])
            writer.writerow([
                "Strat0", 1.5, 1.2, 0.55, 100, 0.10, 1.1, 1.0,
            ])

        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(csv_path)],
            },
        )

        result = await agent.run(ctx)
        assert "market_context" not in result, "AnalysisAgent must NOT add 'market_context' when Frame is absent"
        assert set(result.keys()) == {
            "strategy_analysis",
            "selected_strategies",
            "strategy_verdicts",
            "wf_cycles",
        }

    @pytest.mark.asyncio
    async def test_frame_json_string_present_includes_market_context(self, tmp_path: Path) -> None:
        """GIVEN context.artifacts contains a Frame as raw JSON string
        WHEN AnalysisAgent.run() is called
        THEN the returned dict includes 'market_context'.
        """
        from quantlab.agents.analysis_agent import AnalysisAgent

        csv_path = tmp_path / "strategies.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Profit Factor", "Sharpe Ratio", "Win Rate",
                "Trades", "Max DD", "WF IS Sharpe", "WF OOS Sharpe",
            ])
            writer.writerow([
                "Strat0", 1.5, 1.2, 0.55, 100, 0.10, 1.1, 1.0,
            ])

        frame = Frame(
            regime="range-bound",
            regime_confidence=0.6,
            sentiment=-0.2,
            timeframe="D1",
        )

        agent = AnalysisAgent()
        ctx = PipelineContext(
            config={},
            artifacts={
                "export_paths": [str(csv_path)],
                "frame": frame.to_json(),
            },
        )

        result = await agent.run(ctx)
        assert "market_context" in result
        assert result["market_context"]["regime"] == "range-bound"
        assert result["market_context"]["sentiment"] == -0.2
        assert result["market_context"]["timeframe"] == "D1"
