"""Tests for JForexBrokerAdapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from quantlab.broker.protocol import BrokerAdapter
from quantlab.broker.jforex_adapter import JForexBrokerAdapter
from quantlab.jforex.config import JForexCredentials


class TestJForexBrokerAdapter:
    """Test the JForexBrokerAdapter implementation."""

    def test_adapter_implements_protocol(self):
        """Test that JForexBrokerAdapter satisfies BrokerAdapter protocol."""
        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds)

        assert isinstance(adapter, BrokerAdapter)

    def test_is_connected_true(self, tmp_path: Path):
        """Test is_connected returns True when state indicates connected."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "connection.json").write_text('{"connected": true}')

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        assert adapter.is_connected() is True

    def test_is_connected_false(self, tmp_path: Path):
        """Test is_connected returns False when state indicates disconnected."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "connection.json").write_text('{"connected": false}')

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        assert adapter.is_connected() is False

    def test_get_latency(self, tmp_path: Path):
        """Test get_latency reads from local state."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "latency.txt").write_text("42.5")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        assert adapter.get_latency() == 42.5

    def test_get_health_score(self, tmp_path: Path):
        """Test get_health_score reads from local state."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "health.txt").write_text("0.85")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        assert adapter.get_health_score() == 0.85

    def test_get_recent_slippage(self, tmp_path: Path):
        """Test get_recent_slippage reads from local state."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "slippage.txt").write_text("2.5")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        assert adapter.get_recent_slippage() == 2.5

    def test_get_recent_slippage_unavailable(self, tmp_path: Path):
        """Test get_recent_slippage returns None when state is missing."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)

        assert adapter.get_recent_slippage() is None
