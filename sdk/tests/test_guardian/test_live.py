"""Tests for LiveEvaluation and JForexLiveFeed wiring."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from quantlab.guardian.live import (
    DEFAULT_LIVE_DRAWDOWN_THRESHOLD,
    LiveEvaluation,
    evaluate_live,
    max_drawdown,
)
from quantlab.jforex.live_feed import JForexLiveFeed
from quantlab.readers.models import EquityPoint


class TestMaxDrawdown:
    """Test the max_drawdown helper."""

    def test_no_drawdown_when_flat(self):
        """Test max_drawdown returns 0.0 for constant equity."""
        points = [
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc), equity=10000.0),
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 1, tzinfo=timezone.utc), equity=10000.0),
        ]
        assert max_drawdown(points) == 0.0

    def test_drawdown_calculation(self):
        """Test max_drawdown computes peak-to-trough correctly."""
        points = [
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc), equity=10000.0),
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 1, tzinfo=timezone.utc), equity=9000.0),
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 2, tzinfo=timezone.utc), equity=9500.0),
        ]
        assert max_drawdown(points) == pytest.approx(0.1)


class TestEvaluateLiveWithFeed:
    """Test evaluate_live consuming JForexLiveFeed directly."""

    def test_evaluate_live_accepts_jforex_feed(self, tmp_path: Path):
        """Test evaluate_live accepts JForexLiveFeed as points argument."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text(
            '[{"timestamp": "2026-08-12T10:00:00Z", "equity": 10000.0}]'
        )

        feed = JForexLiveFeed(state_dir=state_dir)
        result = evaluate_live(feed)

        assert isinstance(result, LiveEvaluation)
        assert result.campaign_id == "campaign"
        assert result.held is False
        assert result.transitioned is False
        assert result.drawdown == 0.0

    def test_evaluate_live_feed_triggers_defensive(self, tmp_path: Path):
        """Test evaluate_live transitions to DEFENSIVE when feed drawdown is high."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text(
            '[{"timestamp": "2026-08-12T10:00:00Z", "equity": 10000.0}, '
            '{"timestamp": "2026-08-12T10:01:00Z", "equity": 8000.0}]'
        )

        feed = JForexLiveFeed(state_dir=state_dir)
        result = evaluate_live(feed, drawdown_threshold=0.10)

        assert result.transitioned is True
        assert result.state == "DEFENSIVE"
        assert result.drawdown == pytest.approx(0.2)

    def test_evaluate_live_empty_feed_holds(self, tmp_path: Path):
        """Test evaluate_live holds with STREAM_LOST when feed is empty."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()

        feed = JForexLiveFeed(state_dir=state_dir)
        result = evaluate_live(feed)

        assert result.held is True
        assert result.transitioned is False
        assert "STREAM_LOST" in result.reason

    def test_evaluate_live_feed_with_missing_file_holds(self, tmp_path: Path):
        """Test evaluate_live holds when feed directory has no equity file."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()

        feed = JForexLiveFeed(state_dir=state_dir)
        result = evaluate_live(feed)

        assert result.held is True
        assert "STREAM_LOST" in result.reason

    def test_evaluate_live_backward_compatible_with_list(self):
        """Test evaluate_live still works with a plain list of EquityPoint."""
        points = [
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc), equity=10000.0),
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 1, tzinfo=timezone.utc), equity=10050.0),
        ]
        result = evaluate_live(points)

        assert result.held is False
        assert result.transitioned is False
        assert result.drawdown == 0.0

    def test_evaluate_live_backward_compatible_with_tuple(self):
        """Test evaluate_live works with a tuple of EquityPoint."""
        points = (
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc), equity=10000.0),
            EquityPoint(timestamp=datetime(2026, 8, 12, 10, 1, tzinfo=timezone.utc), equity=9000.0),
        )
        result = evaluate_live(points, drawdown_threshold=0.05)

        assert result.transitioned is True
        assert result.state == "DEFENSIVE"
