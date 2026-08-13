"""Tests for JForexLiveFeed."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from quantlab.jforex.live_feed import JForexLiveFeed
from quantlab.jforex.models import OrderEvent
from quantlab.readers.models import EquityPoint


class TestJForexLiveFeed:
    """Test the JForexLiveFeed implementation."""

    def test_feed_without_state_dir_returns_empty(self):
        """Test that a feed without state_dir yields no data."""
        feed = JForexLiveFeed()

        assert list(feed) == []
        assert feed.read_equity() == []
        assert feed.read_orders() == []

    def test_read_equity_parses_json(self, tmp_path: Path):
        """Test read_equity parses equity.json into EquityPoint objects."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text(
            '[{"timestamp": "2026-08-12T10:00:00Z", "equity": 10000.0}, '
            '{"timestamp": "2026-08-12T10:01:00Z", "equity": 10050.0}]'
        )

        feed = JForexLiveFeed(state_dir=state_dir)
        points = feed.read_equity()

        assert len(points) == 2
        assert points[0].equity == 10000.0
        assert points[1].equity == 10050.0
        assert points[0].timestamp == datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc)

    def test_read_equity_missing_file_returns_empty(self, tmp_path: Path):
        """Test read_equity returns empty list when equity.json is missing."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()

        feed = JForexLiveFeed(state_dir=state_dir)
        assert feed.read_equity() == []

    def test_read_equity_invalid_json_returns_empty(self, tmp_path: Path):
        """Test read_equity returns empty list on malformed JSON."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text("not json")

        feed = JForexLiveFeed(state_dir=state_dir)
        assert feed.read_equity() == []

    def test_read_orders_parses_json(self, tmp_path: Path):
        """Test read_orders parses orders.json into OrderEvent objects."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "orders.json").write_text(
            '[{"order_id": "1", "timestamp": "2026-08-12T10:00:00Z", '
            '"side": "BUY", "lots": 0.1, "price": 1.1234, "status": "FILLED"}]'
        )

        feed = JForexLiveFeed(state_dir=state_dir)
        events = feed.read_orders()

        assert len(events) == 1
        assert events[0].order_id == "1"
        assert events[0].side == "BUY"
        assert events[0].lots == 0.1
        assert events[0].status == "FILLED"

    def test_read_orders_missing_file_returns_empty(self, tmp_path: Path):
        """Test read_orders returns empty list when orders.json is missing."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()

        feed = JForexLiveFeed(state_dir=state_dir)
        assert feed.read_orders() == []

    def test_feed_is_iterable_over_equity(self, tmp_path: Path):
        """Test that JForexLiveFeed is iterable and yields EquityPoint objects."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text(
            '[{"timestamp": "2026-08-12T10:00:00Z", "equity": 10000.0}]'
        )

        feed = JForexLiveFeed(state_dir=state_dir)
        points = list(feed)

        assert len(points) == 1
        assert isinstance(points[0], EquityPoint)
        assert points[0].equity == 10000.0

    def test_read_equity_empty_json_array(self, tmp_path: Path):
        """Test read_equity handles empty JSON array."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text("[]")

        feed = JForexLiveFeed(state_dir=state_dir)
        assert feed.read_equity() == []

    def test_feed_iterable_empty_when_no_equity_file(self, tmp_path: Path):
        """Test iterable yields nothing when equity.json is missing."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()

        feed = JForexLiveFeed(state_dir=state_dir)
        assert list(feed) == []

    def test_read_equity_skips_invalid_entries(self, tmp_path: Path):
        """Test read_equity skips malformed entries and keeps valid ones."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "equity.json").write_text(
            '[{"timestamp": "2026-08-12T10:00:00Z", "equity": 10000.0}, '
            '{"bad": "entry"}, '
            '{"timestamp": "2026-08-12T10:02:00Z", "equity": 10100.0}]'
        )

        feed = JForexLiveFeed(state_dir=state_dir)
        points = feed.read_equity()

        assert len(points) == 2
        assert points[0].equity == 10000.0
        assert points[1].equity == 10100.0
