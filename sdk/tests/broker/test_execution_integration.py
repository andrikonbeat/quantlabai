"""Integration tests wiring JForexBrokerAdapter into ExecutionGuardian."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantlab.broker.jforex_adapter import JForexBrokerAdapter
from quantlab.guardian.execution import ExecutionGuardian
from quantlab.guardian.models import GuardianResult, GuardianStatus, GuardianType
from quantlab.jforex.config import JForexCredentials


class TestJForexExecutionIntegration:
    """Test ExecutionGuardian with JForexBrokerAdapter."""

    def test_execution_guardian_with_jforex_adapter(self, tmp_path: Path):
        """Test that ExecutionGuardian.check() works with JForexBrokerAdapter."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "connection.json").write_text('{"connected": true}')
        (state_dir / "latency.txt").write_text("25.0")
        (state_dir / "health.txt").write_text("0.9")
        (state_dir / "slippage.txt").write_text("2.0")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)
        guardian = ExecutionGuardian(adapter)

        result = guardian.check()

        assert isinstance(result, GuardianResult)
        assert result.guardian_type == GuardianType.EXECUTION
        assert result.status in (GuardianStatus.GREEN, GuardianStatus.YELLOW, GuardianStatus.RED)
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.message, str)
        assert result.timestamp is not None

    def test_execution_guardian_disconnected_jforex(self, tmp_path: Path):
        """Test ExecutionGuardian returns RED when JForex is disconnected."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "connection.json").write_text('{"connected": false}')

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)
        guardian = ExecutionGuardian(adapter)

        result = guardian.check()

        assert result.status == GuardianStatus.RED
        assert result.score == 0.0
        assert "disconnected" in result.message.lower()

    def test_execution_guardian_high_latency_jforex(self, tmp_path: Path):
        """Test ExecutionGuardian degrades score with high latency."""
        state_dir = tmp_path / "jforex_state"
        state_dir.mkdir()
        (state_dir / "connection.json").write_text('{"connected": true}')
        (state_dir / "latency.txt").write_text("500.0")  # High latency
        (state_dir / "health.txt").write_text("1.0")

        creds = JForexCredentials(username="user", password="pass")
        adapter = JForexBrokerAdapter(creds, state_dir=state_dir)
        guardian = ExecutionGuardian(adapter)

        result = guardian.check()

        # High latency (500ms) should degrade score below 0.8
        assert result.score < 0.8
        assert result.status in (GuardianStatus.YELLOW, GuardianStatus.RED)
