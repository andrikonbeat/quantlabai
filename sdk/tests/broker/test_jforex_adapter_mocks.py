"""Unit tests for JForexBrokerAdapter with mocked state reads."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from quantlab.broker.jforex_adapter import JForexBrokerAdapter
from quantlab.jforex.config import JForexCredentials


class TestJForexBrokerAdapterMocks:
    """Test JForexBrokerAdapter with mocked filesystem and error paths."""

    def test_is_connected_malformed_json(self, tmp_path: Path):
        """Test is_connected returns False on malformed JSON."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "connection.json").write_text("not json")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        assert adapter.is_connected() is False

    def test_is_connected_os_error(self, tmp_path: Path):
        """Test is_connected returns False when read_text raises OSError."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "connection.json").write_text('{"connected": true}')

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        with patch(
            "quantlab.broker.jforex_adapter.Path.read_text",
            side_effect=OSError("permission denied"),
        ):
            assert adapter.is_connected() is False

    def test_get_latency_invalid_value(self, tmp_path: Path):
        """Test get_latency raises ValueError on invalid float."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "latency.txt").write_text("not-a-number")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        with pytest.raises(ValueError, match="could not convert string to float"):
            adapter.get_latency()

    def test_get_health_score_out_of_range(self, tmp_path: Path):
        """Test get_health_score raises ValueError when score is out of range."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "health.txt").write_text("1.5")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        with pytest.raises(ValueError, match="out of range"):
            adapter.get_health_score()

    def test_get_recent_slippage_invalid_value(self, tmp_path: Path):
        """Test get_recent_slippage returns None on invalid float."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "slippage.txt").write_text("bad")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        assert adapter.get_recent_slippage() is None

    def test_get_recent_slippage_os_error(self, tmp_path: Path):
        """Test get_recent_slippage returns None on OSError."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "slippage.txt").write_text("1.5")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        with patch(
            "quantlab.broker.jforex_adapter.Path.read_text",
            side_effect=OSError("permission denied"),
        ):
            assert adapter.get_recent_slippage() is None

    def test_no_state_dir_returns_disconnected(self):
        """Test adapter with no state directory reports disconnected."""
        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds)

        assert adapter.is_connected() is False
        assert adapter.get_recent_slippage() is None
