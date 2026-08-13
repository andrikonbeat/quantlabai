"""Integration tests for JForex live feed and strategy bridge with mocked state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quantlab.guardian.live import evaluate_live, LiveEvaluation, max_drawdown
from quantlab.jforex.live_feed import JForexLiveFeed
from quantlab.jforex.models import OrderEvent
from quantlab.jforex.strategy_bridge import JForexStrategyBridge
from quantlab.readers.models import EquityPoint


class TestJForexIntegration:
    """Integration tests exercising live feed and strategy bridge together."""

    def test_full_feed_to_evaluation_flow(self, tmp_path: Path):
        """Test that a populated JForex state feeds into LiveEvaluation."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text(
            json.dumps([
                {"timestamp": "2026-08-12T10:00:00Z", "equity": 10000.0},
                {"timestamp": "2026-08-12T10:01:00Z", "equity": 10500.0},
                {"timestamp": "2026-08-12T10:02:00Z", "equity": 10300.0},
            ])
        )
        (state_dir / "orders.json").write_text(
            json.dumps([
                {
                    "order_id": "ORD-1",
                    "timestamp": "2026-08-12T10:00:30Z",
                    "side": "BUY",
                    "lots": 0.1,
                    "price": 1.1234,
                    "status": "FILLED",
                }
            ])
        )

        feed = JForexLiveFeed(state_dir=state_dir)
        evaluation = evaluate_live(feed)

        assert isinstance(evaluation, LiveEvaluation)
        assert evaluation.held is False
        assert evaluation.transitioned is False
        assert len(feed.read_equity()) == 3
        assert len(feed.read_orders()) == 1
        assert feed.read_orders()[0].order_id == "ORD-1"

    def test_strategy_lifecycle_with_mocked_subprocess(self, tmp_path: Path):
        """Test strategy compile -> deploy -> start -> stop lifecycle."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            bridge = JForexStrategyBridge(
                java_home="/opt/java",
                jforex_home="/opt/jforex",
            )

            source = tmp_path / "Strategy.java"
            source.write_text("public class Strategy {}")
            out_dir = tmp_path / "out"
            out_dir.mkdir()

            # Compile
            class_path = bridge.compile(source, out_dir)
            assert class_path.exists() is False  # mocked, but path is correct
            assert class_path == out_dir / "Strategy.class"

            # Deploy
            bridge.deploy(tmp_path / "strategy.jfx")

            # Start
            bridge.start("STRAT-001")

            # Stop
            bridge.stop("STRAT-001")

            assert mock_run.call_count == 4

    def test_live_feed_handles_corrupted_state_gracefully(self, tmp_path: Path):
        """Test feed does not crash on corrupted/missing state files."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text("corrupted")
        (state_dir / "orders.json").write_text("{}")

        feed = JForexLiveFeed(state_dir=state_dir)
        evaluation = evaluate_live(feed)

        assert evaluation.held is True
        assert "STREAM_LOST" in evaluation.reason
        assert feed.read_equity() == []
        assert feed.read_orders() == []

    def test_feed_produces_equity_points_compatible_with_max_drawdown(self, tmp_path: Path):
        """Test that feed output works with max_drawdown helper."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text(
            json.dumps([
                {"timestamp": "2026-08-12T10:00:00Z", "equity": 10000.0},
                {"timestamp": "2026-08-12T10:01:00Z", "equity": 9000.0},
                {"timestamp": "2026-08-12T10:02:00Z", "equity": 9500.0},
            ])
        )

        feed = JForexLiveFeed(state_dir=state_dir)
        points = feed.read_equity()
        dd = max_drawdown(points)

        assert dd == pytest.approx(0.1)

    def test_bridge_compile_failure_does_not_deploy(self, tmp_path: Path):
        """Test that a compile failure prevents deploy."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="javac error")
            source = tmp_path / "Bad.java"
            source.write_text("bad code")
            out_dir = tmp_path / "out"
            out_dir.mkdir()

            bridge = JForexStrategyBridge()
            with pytest.raises(RuntimeError, match="Compilation failed"):
                bridge.compile(source, out_dir)

            # deploy should never have been called
            assert mock_run.call_count == 1
