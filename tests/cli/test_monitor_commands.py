"""Tests for monitor CLI commands — PR 3: CLI Integration.

RED phase: tests reference monitor_commands.py which does NOT exist yet.
Covers tasks 3.1, 3.2, 3.3.

Test layers:
- Unit: argparse wiring (parser structure, argument defaults, func dispatch)
- Integration: handler creates daemon with correct config and calls lifecycle
- Wiring: main.py build_parser() includes monitor subparser
"""

from __future__ import annotations

import argparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quantlab.cli.monitor_commands import (
    add_monitor_subparser,
    cmd_monitor_start,
    cmd_monitor_stop,
    cmd_monitor_status,
)


# ──────────────────────────────────────────────────────────────────────────────
# Task 3.1: monitor subparser structure and argument parsing (unit)
# ──────────────────────────────────────────────────────────────────────────────


class TestMonitorSubparserStructure:
    """add_monitor_subparser() creates correct parser tree with args."""

    @pytest.fixture(autouse=True)
    def _setup_parser(self) -> None:
        """Build a fresh parser for each test."""
        self.parser = argparse.ArgumentParser()
        self.subparsers = self.parser.add_subparsers(dest="command")
        add_monitor_subparser(self.subparsers)

    # ── monitor start ───────────────────────────────────────────────────────

    def test_monitor_start_requires_strategy(self) -> None:
        """--strategy is required for monitor start."""
        with pytest.raises(SystemExit):
            self.parser.parse_args(["monitor", "start"])

    def test_monitor_start_accepts_all_args(self) -> None:
        """monitor start accepts --strategy, --config, --daemon."""
        args = self.parser.parse_args([
            "monitor", "start",
            "--strategy", "X",
        ])
        assert args.strategy == "X"
        assert args.config is None
        assert args.daemon is False

        args = self.parser.parse_args([
            "monitor", "start",
            "--strategy", "Y",
            "--config", "/tmp/cfg.yaml",
            "--daemon",
        ])
        assert args.strategy == "Y"
        assert args.config == "/tmp/cfg.yaml"
        assert args.daemon is True

    def test_monitor_start_func_dispatches_correct_handler(self) -> None:
        """monitor start sets func to cmd_monitor_start."""
        args = self.parser.parse_args(["monitor", "start", "--strategy", "X"])
        assert args.func is cmd_monitor_start

    # ── monitor stop ────────────────────────────────────────────────────────

    def test_monitor_stop_optional_strategy(self) -> None:
        """--strategy is optional for monitor stop."""
        args = self.parser.parse_args(["monitor", "stop"])
        assert args.strategy is None

        args = self.parser.parse_args(["monitor", "stop", "--strategy", "X"])
        assert args.strategy == "X"

    def test_monitor_stop_func_dispatches_correct_handler(self) -> None:
        """monitor stop sets func to cmd_monitor_stop."""
        args = self.parser.parse_args(["monitor", "stop"])
        assert args.func is cmd_monitor_stop

    # ── monitor status ──────────────────────────────────────────────────────

    def test_monitor_status_optional_strategy(self) -> None:
        """--strategy is optional for monitor status."""
        args = self.parser.parse_args(["monitor", "status"])
        assert args.strategy is None

        args = self.parser.parse_args(["monitor", "status", "--strategy", "X"])
        assert args.strategy == "X"

    def test_monitor_status_func_dispatches_correct_handler(self) -> None:
        """monitor status sets func to cmd_monitor_status."""
        args = self.parser.parse_args(["monitor", "status"])
        assert args.func is cmd_monitor_status

    # ── monitor help ────────────────────────────────────────────────────────

    def test_monitor_help_shows_subcommands(self) -> None:
        """'monitor --help' lists start/stop/status subcommands."""
        with pytest.raises(SystemExit):
            self.parser.parse_args(["monitor", "--help"])


# ──────────────────────────────────────────────────────────────────────────────
# Task 3.3: Integration — command handlers wire to daemon lifecycle
# ──────────────────────────────────────────────────────────────────────────────


class TestMonitorCommandHandlers:
    """Command handlers create AutonomousMonitorDaemon and call lifecycle."""

    # ── cmd_monitor_start ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_start_creates_daemon_with_strategy_config(self) -> None:
        """cmd_monitor_start creates MonitorConfig from strategy arg."""
        mock_daemon = AsyncMock()

        with (
            patch("quantlab.cli.monitor_commands.AutonomousMonitorDaemon", return_value=mock_daemon) as mock_cls,
            patch("quantlab.cli.monitor_commands.MonitorConfig") as mock_cfg,
        ):
            args = argparse.Namespace(strategy="test_strat", config=None, daemon=False)
            result = await cmd_monitor_start(args)

        assert result == 0
        mock_cfg.assert_called_once_with(strategy_id="test_strat")
        mock_cls.assert_called_once()
        mock_daemon.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_loads_yaml_when_config_provided(self) -> None:
        """cmd_monitor_start with --config path loads from YAML."""
        mock_daemon = AsyncMock()

        with (
            patch("quantlab.cli.monitor_commands.AutonomousMonitorDaemon", return_value=mock_daemon),
            patch("quantlab.cli.monitor_commands.MonitorConfig") as mock_cfg,
        ):
            args = argparse.Namespace(strategy="ignored", config="/tmp/test.yaml", daemon=False)
            result = await cmd_monitor_start(args)

        assert result == 0
        mock_cfg.from_yaml.assert_called_once_with("/tmp/test.yaml")
        mock_daemon.start.assert_awaited_once()

    # ── cmd_monitor_stop ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_stop_creates_daemon_and_calls_stop(self) -> None:
        """cmd_monitor_stop creates daemon with config and calls stop()."""
        mock_daemon = AsyncMock()

        with (
            patch("quantlab.cli.monitor_commands.AutonomousMonitorDaemon", return_value=mock_daemon),
            patch("quantlab.cli.monitor_commands.MonitorConfig") as mock_cfg,
        ):
            args = argparse.Namespace(strategy="test_strat")
            result = await cmd_monitor_stop(args)

        assert result == 0
        mock_cfg.assert_called_once_with(strategy_id="test_strat")
        mock_daemon.stop.assert_awaited_once()

    # ── cmd_monitor_status ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_status_returns_and_displays_json(self) -> None:
        """cmd_monitor_status returns daemon status as JSON."""
        mock_daemon = MagicMock()
        expected_status = {
            "state": "running",
            "uptime_seconds": 42.5,
            "last_heartbeat": 12345.0,
            "metrics_count": 3,
            "error": None,
        }
        mock_daemon.status.return_value = expected_status

        with (
            patch("quantlab.cli.monitor_commands.AutonomousMonitorDaemon", return_value=mock_daemon),
            patch("quantlab.cli.monitor_commands.MonitorConfig"),
            patch("quantlab.cli.monitor_commands.print_json") as mock_print,
        ):
            args = argparse.Namespace(strategy="test_strat")
            result = await cmd_monitor_status(args)

        assert result == 0
        mock_daemon.status.assert_called_once()
        mock_print.assert_called_once_with(expected_status)

    @pytest.mark.asyncio
    async def test_status_shows_stopped_state_when_daemon_not_running(self) -> None:
        """cmd_monitor_status returns status even when daemon is stopped."""
        mock_daemon = MagicMock()
        mock_daemon.status.return_value = {
            "state": "stopped",
            "uptime_seconds": 0.0,
            "last_heartbeat": 0.0,
            "metrics_count": 0,
            "error": None,
        }

        with (
            patch("quantlab.cli.monitor_commands.AutonomousMonitorDaemon", return_value=mock_daemon),
            patch("quantlab.cli.monitor_commands.MonitorConfig"),
            patch("quantlab.cli.monitor_commands.print_json") as mock_print,
        ):
            args = argparse.Namespace(strategy="test_strat")
            result = await cmd_monitor_status(args)

        assert result == 0
        mock_print.assert_called_once()
        status = mock_print.call_args[0][0]
        assert status["state"] == "stopped"
        assert status["uptime_seconds"] == 0.0

    @pytest.mark.asyncio
    async def test_status_includes_error_info(self) -> None:
        """cmd_monitor_status includes error field when daemon is in error state."""
        mock_daemon = MagicMock()
        mock_daemon.status.return_value = {
            "state": "error",
            "uptime_seconds": 10.0,
            "last_heartbeat": 1000.0,
            "metrics_count": 1,
            "error": "Stream lost after 5 retries",
        }

        with (
            patch("quantlab.cli.monitor_commands.AutonomousMonitorDaemon", return_value=mock_daemon),
            patch("quantlab.cli.monitor_commands.MonitorConfig"),
            patch("quantlab.cli.monitor_commands.print_json") as mock_print,
        ):
            args = argparse.Namespace(strategy="test_strat")
            result = await cmd_monitor_status(args)

        assert result == 0
        status = mock_print.call_args[0][0]
        assert status["state"] == "error"
        assert status["error"] == "Stream lost after 5 retries"


# ──────────────────────────────────────────────────────────────────────────────
# Task 3.2: main.py wiring — build_parser() includes monitor subparser
# ──────────────────────────────────────────────────────────────────────────────


class TestMonitorWiredInMain:
    """build_parser() in main.py registers the monitor subparser."""

    def test_build_parser_includes_monitor_commands(self) -> None:
        """build_parser() registers the full monitor subparser tree."""
        from quantlab.cli.main import build_parser

        parser = build_parser()

        # Start
        args = parser.parse_args(["monitor", "start", "--strategy", "X"])
        assert args.command == "monitor"
        assert args.monitor_cmd == "start"
        assert args.strategy == "X"
        assert args.func is cmd_monitor_start

        # Stop
        args = parser.parse_args(["monitor", "stop"])
        assert args.command == "monitor"
        assert args.monitor_cmd == "stop"
        assert args.func is cmd_monitor_stop

        # Status
        args = parser.parse_args(["monitor", "status"])
        assert args.command == "monitor"
        assert args.monitor_cmd == "status"
        assert args.func is cmd_monitor_status

    def test_build_parser_monitor_does_not_conflict_with_other_commands(self) -> None:
        """Existing commands still work after adding monitor subparser."""
        from quantlab.cli.main import build_parser

        parser = build_parser()

        # Verify agent still works
        args = parser.parse_args(["agent", "memory", "inspect", "test_agent", "test_campaign"])
        assert args.command == "agent"

        # Verify daemon still works
        args = parser.parse_args(["daemon", "status"])
        assert args.command == "daemon"
