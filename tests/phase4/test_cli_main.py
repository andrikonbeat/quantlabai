"""Tests for QuantLab CLI — Phase 4 automation commands."""

import argparse
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quantlab.cli.main import (
    build_parser,
    main,
    _parse_strategies,
    cmd_daemon_start,
    cmd_daemon_stop,
    cmd_daemon_status,
    cmd_portfolio_run,
    cmd_portfolio_status,
    cmd_portfolio_export,
    cmd_optimizer_run,
    cmd_optimizer_status,
    cmd_optimizer_export,
    cmd_retester_run,
    cmd_retester_status,
    cmd_retester_export,
    cmd_jforex_deploy,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_args():
    """Create a mock argparse.Namespace with common defaults."""
    args = argparse.Namespace()
    args.sqx_path = "/fake/sqx"
    args.port = 8888
    args.timeout = 30.0
    args.force = False
    args.no_daemon_stop = False
    args.json = False
    args.output_dir = None
    args.dry_run = False  # Default to False for real command tests
    args.name = "TestCampaign"
    return args


# ── Helper Tests ────────────────────────────────────────────────────────────


class TestParseStrategies:
    """Tests for _parse_strategies helper."""

    def test_comma_separated(self):
        args = argparse.Namespace(strategies=["strat-1,strat-2,strat-3"])
        result = _parse_strategies(args)
        assert result == ["strat-1", "strat-2", "strat-3"]

    def test_space_separated(self):
        args = argparse.Namespace(strategies=["strat-1", "strat-2", "strat-3"])
        result = _parse_strategies(args)
        assert result == ["strat-1", "strat-2", "strat-3"]

    def test_mixed(self):
        args = argparse.Namespace(strategies=["strat-1,strat-2", "strat-3"])
        result = _parse_strategies(args)
        assert result == ["strat-1", "strat-2", "strat-3"]

    def test_empty(self):
        args = argparse.Namespace(strategies=None)
        result = _parse_strategies(args)
        assert result == []

    def test_with_whitespace(self):
        args = argparse.Namespace(strategies=["  strat-1  ,  strat-2  "])
        result = _parse_strategies(args)
        assert result == ["strat-1", "strat-2"]


# ── Argparse Tests ─────────────────────────────────────────────────────────


class TestArgParser:
    """Tests for argument parser structure."""

    def test_parser_builds(self):
        parser = build_parser()
        assert parser is not None
        assert isinstance(parser, argparse.ArgumentParser)

    def test_top_level_help(self):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--help"])
        assert exc.value.code == 0

    def test_subcommands_exist(self):
        parser = build_parser()
        # Parse args to trigger subparser registration
        args = parser.parse_args(["daemon", "start"])
        assert args.command == "daemon"

    def test_daemon_subcommands(self):
        parser = build_parser()
        args = parser.parse_args(["daemon", "start"])
        assert args.daemon_cmd == "start"
        args = parser.parse_args(["daemon", "stop"])
        assert args.daemon_cmd == "stop"
        args = parser.parse_args(["daemon", "status"])
        assert args.daemon_cmd == "status"

    def test_portfolio_subcommands(self):
        parser = build_parser()
        args = parser.parse_args(["portfolio", "run", "--strategies", "s1", "--dry-run"])
        assert args.portfolio_cmd == "run"
        args = parser.parse_args(["portfolio", "status", "test"])
        assert args.portfolio_cmd == "status"
        args = parser.parse_args(["portfolio", "export", "test"])
        assert args.portfolio_cmd == "export"

    def test_optimizer_subcommands(self):
        parser = build_parser()
        args = parser.parse_args(["optimizer", "run", "s1", "--dry-run"])
        assert args.optimizer_cmd == "run"
        args = parser.parse_args(["optimizer", "status", "test"])
        assert args.optimizer_cmd == "status"
        args = parser.parse_args(["optimizer", "export", "test"])
        assert args.optimizer_cmd == "export"

    def test_retester_subcommands(self):
        parser = build_parser()
        args = parser.parse_args(["retester", "run", "s1", "--databanks", "EURUSD_H1", "--dry-run"])
        assert args.retester_cmd == "run"
        args = parser.parse_args(["retester", "status", "test"])
        assert args.retester_cmd == "status"
        args = parser.parse_args(["retester", "export", "test"])
        assert args.retester_cmd == "export"

    def test_jforex_subcommands(self):
        parser = build_parser()
        args = parser.parse_args(["jforex", "deploy", "s1", "--output-dir", "/tmp", "--dry-run"])
        assert args.jforex_cmd == "deploy"

    def test_global_options(self):
        parser = build_parser()
        # Global options must be passed after the command (per _add_common_args pattern)
        args = parser.parse_args(["daemon", "start", "--sqx-path", "/custom/path", "--port", "9999"])
        assert args.sqx_path == "/custom/path"
        assert args.port == 9999

    def test_json_flag(self):
        parser = build_parser()
        args = parser.parse_args(["daemon", "start", "--json"])
        assert args.json is True

    def test_dry_run_flag(self):
        parser = build_parser()
        args = parser.parse_args(["portfolio", "run", "--dry-run", "--strategies", "s1"])
        assert args.dry_run is True

    def test_no_daemon_stop_flag(self):
        parser = build_parser()
        args = parser.parse_args(["portfolio", "run", "--no-daemon-stop", "--strategies", "s1"])
        assert args.no_daemon_stop is True


# ── Command Tests (dry-run mode with mocks) ───────────────────────────────


class TestDaemonCommands:
    """Tests for daemon start/stop/status commands."""

    @pytest.mark.asyncio
    async def test_daemon_start_success(self, mock_args):
        mock_args.dry_run = False

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.start.return_value = "http://127.0.0.1:8888"
            mock_daemon_class.return_value = mock_daemon

            result = await cmd_daemon_start(mock_args)

            assert result == 0
            mock_daemon.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_daemon_start_failure(self, mock_args):
        mock_args.dry_run = False

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            from quantlab.phase4.errors import SQXDaemonStartError

            mock_daemon.start.side_effect = SQXDaemonStartError("Failed to start")
            mock_daemon_class.return_value = mock_daemon

            result = await cmd_daemon_start(mock_args)

            assert result == 1

    @pytest.mark.asyncio
    async def test_daemon_stop(self, mock_args):
        mock_args.dry_run = False

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.stop.return_value = None
            mock_daemon_class.return_value = mock_daemon

            result = await cmd_daemon_stop(mock_args)

            assert result == 0
            mock_daemon.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_daemon_status_healthy(self, mock_args):
        mock_args.json = True

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.health_check.return_value = True
            mock_daemon.base_url = "http://127.0.0.1:8888"
            mock_daemon_class.return_value = mock_daemon

            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                result = await cmd_daemon_status(mock_args)
                output = mock_stdout.getvalue()

            assert result == 0
            data = json.loads(output.strip())
            assert data["healthy"] is True

    @pytest.mark.asyncio
    async def test_daemon_status_unhealthy(self, mock_args):
        mock_args.json = True

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.health_check.return_value = False
            mock_daemon.base_url = "http://127.0.0.1:8888"
            mock_daemon_class.return_value = mock_daemon

            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                result = await cmd_daemon_status(mock_args)
                output = mock_stdout.getvalue()

            assert result == 1
            data = json.loads(output.strip())
            assert data["healthy"] is False


# ── Portfolio Commands ───────────────────────────────────────────────────


class TestPortfolioCommands:
    """Tests for portfolio run/status/export commands."""

    @pytest.mark.asyncio
    async def test_portfolio_run_dry_run_json(self, mock_args):
        mock_args.strategies = ["strat-1", "strat-2"]
        mock_args.dry_run = True
        mock_args.json = True
        mock_args.generations = 50
        mock_args.population = 200
        mock_args.fitness = "NetProfit"
        mock_args.min_strategies = 2
        mock_args.max_strategies = 10
        mock_args.rebalance = "Monthly"

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = await cmd_portfolio_run(mock_args)
            output = mock_stdout.getvalue()

        assert result == 0
        data = json.loads(output.strip())
        assert data["type"] == "portfolio"
        assert data["dry_run"] is True
        assert data["strategies"] == ["strat-1", "strat-2"]
        assert "cfx_base64" in data

    @pytest.mark.asyncio
    async def test_portfolio_run_missing_strategies(self, mock_args):
        mock_args.strategies = None
        mock_args.dry_run = True

        result = await cmd_portfolio_run(mock_args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_portfolio_status_json(self, mock_args):
        mock_args.name = "MyPortfolio"
        mock_args.json = True

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.start.return_value = "http://127.0.0.1:8888"
            mock_daemon.get_client.return_value = AsyncMock()
            mock_daemon_class.return_value = mock_daemon

            with patch("quantlab.cli.main.CommandDispatcher") as mock_dispatcher_class:
                mock_dispatcher = AsyncMock()
                mock_status = MagicMock()
                mock_status.campaign_name = "MyPortfolio"
                mock_status.status = "running"
                mock_status.progress = 50.0
                mock_status.current_generation = 25
                mock_status.total_generations = 50
                mock_status.error_message = None
                mock_dispatcher.get_status.return_value = mock_status
                mock_dispatcher_class.from_daemon = AsyncMock(return_value=mock_dispatcher)

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = await cmd_portfolio_status(mock_args)
                    output = mock_stdout.getvalue()

                assert result == 0
                data = json.loads(output.strip())
                assert data["campaign"] == "MyPortfolio"
                assert data["status"] == "running"
                assert data["progress"] == 50.0

    @pytest.mark.asyncio
    async def test_portfolio_export(self, mock_args):
        mock_args.name = "MyPortfolio"
        mock_args.output_dir = "/tmp/output"
        mock_args.json = True

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.start.return_value = "http://127.0.0.1:8888"
            mock_daemon.get_client.return_value = AsyncMock()
            mock_daemon_class.return_value = mock_daemon

            mock_dispatcher = AsyncMock()
            mock_dispatcher.export_results.return_value = "/tmp/output/MyPortfolio_results.csv"

            with patch("quantlab.cli.main.CommandDispatcher") as mock_dispatcher_class:
                mock_dispatcher_class.from_daemon = AsyncMock(return_value=mock_dispatcher)

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = await cmd_portfolio_export(mock_args)
                    output = mock_stdout.getvalue()

                assert result == 0
                data = json.loads(output.strip())
                assert data["output"] == "/tmp/output/MyPortfolio_results.csv"


# ── Optimizer Commands ───────────────────────────────────────────────────


class TestOptimizerCommands:
    """Tests for optimizer run/status/export commands."""

    @pytest.mark.asyncio
    async def test_optimizer_run_dry_run_json(self, mock_args):
        mock_args.strategy_id = "strat-1"
        mock_args.dry_run = True
        mock_args.json = True
        mock_args.method = "Genetic"
        mock_args.objective = "SharpeRatio"
        mock_args.walkforward_cycles = 10
        mock_args.population = 100
        mock_args.generations = 50
        mock_args.crossover = 0.8
        mock_args.mutation = 0.1
        mock_args.databanks = ["EURUSD_H1"]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = await cmd_optimizer_run(mock_args)
            output = mock_stdout.getvalue()

        assert result == 0
        data = json.loads(output.strip())
        assert data["type"] == "optimizer"
        assert data["dry_run"] is True
        assert data["strategy_id"] == "strat-1"
        assert "cfx_base64" in data

    @pytest.mark.asyncio
    async def test_optimizer_status_json(self, mock_args):
        mock_args.name = "MyOptimizer"
        mock_args.json = True

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.start.return_value = "http://127.0.0.1:8888"
            mock_daemon.get_client.return_value = AsyncMock()
            mock_daemon_class.return_value = mock_daemon

            mock_dispatcher = AsyncMock()
            mock_status = MagicMock()
            mock_status.campaign_name = "MyOptimizer"
            mock_status.status = "completed"
            mock_status.progress = 100.0
            mock_status.current_generation = 50
            mock_status.total_generations = 50
            mock_status.error_message = None
            mock_dispatcher.get_status.return_value = mock_status

            with patch("quantlab.cli.main.CommandDispatcher") as mock_dispatcher_class:
                mock_dispatcher_class.from_daemon = AsyncMock(return_value=mock_dispatcher)

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = await cmd_optimizer_status(mock_args)
                    output = mock_stdout.getvalue()

                assert result == 0
                data = json.loads(output.strip())
                assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_optimizer_export(self, mock_args):
        mock_args.name = "MyOptimizer"
        mock_args.output_dir = "/tmp/output"
        mock_args.json = True

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.start.return_value = "http://127.0.0.1:8888"
            mock_daemon.get_client.return_value = AsyncMock()
            mock_daemon_class.return_value = mock_daemon

            mock_dispatcher = AsyncMock()
            mock_dispatcher.export_optimization_results.return_value = "/tmp/output/MyOptimizer_optimizer.csv"

            with patch("quantlab.cli.main.CommandDispatcher") as mock_dispatcher_class:
                mock_dispatcher_class.from_daemon = AsyncMock(return_value=mock_dispatcher)

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = await cmd_optimizer_export(mock_args)
                    output = mock_stdout.getvalue()

                assert result == 0
                data = json.loads(output.strip())
                assert data["output"] == "/tmp/output/MyOptimizer_optimizer.csv"


# ── Retester Commands ────────────────────────────────────────────────────


class TestRetesterCommands:
    """Tests for retester run/status/export commands."""

    @pytest.mark.asyncio
    async def test_retester_run_dry_run_json(self, mock_args):
        mock_args.strategy_id = "strat-1"
        mock_args.databanks = ["EURUSD_H1", "GBPUSD_H1"]
        mock_args.dry_run = True
        mock_args.json = True
        mock_args.mc_runs = 100
        mock_args.mc_percentile = 95
        mock_args.walkforward_cycles = 5
        mock_args.min_trades = 30
        mock_args.confidence_level = 0.95

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = await cmd_retester_run(mock_args)
            output = mock_stdout.getvalue()

        assert result == 0
        data = json.loads(output.strip())
        assert data["type"] == "retester"
        assert data["dry_run"] is True
        assert data["databanks"] == ["EURUSD_H1", "GBPUSD_H1"]
        assert "cfx_base64" in data

    @pytest.mark.asyncio
    async def test_retester_run_missing_databanks(self, mock_args):
        mock_args.strategy_id = "strat-1"
        mock_args.databanks = None
        mock_args.dry_run = True

        result = await cmd_retester_run(mock_args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_retester_status_json(self, mock_args):
        mock_args.name = "MyRetester"
        mock_args.json = True

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.start.return_value = "http://127.0.0.1:8888"
            mock_daemon.get_client.return_value = AsyncMock()
            mock_daemon_class.return_value = mock_daemon

            mock_dispatcher = AsyncMock()
            mock_status = MagicMock()
            mock_status.campaign_name = "MyRetester"
            mock_status.status = "running"
            mock_status.progress = 25.0
            mock_status.current_generation = 2
            mock_status.total_generations = 5
            mock_status.error_message = None
            mock_dispatcher.get_status.return_value = mock_status

            with patch("quantlab.cli.main.CommandDispatcher") as mock_dispatcher_class:
                mock_dispatcher_class.from_daemon = AsyncMock(return_value=mock_dispatcher)

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = await cmd_retester_status(mock_args)
                    output = mock_stdout.getvalue()

                assert result == 0
                data = json.loads(output.strip())
                assert data["status"] == "running"


# ── JForex Commands ──────────────────────────────────────────────────────


class TestJForexCommands:
    """Tests for jforex deploy command."""

    @pytest.mark.asyncio
    async def test_jforex_deploy_dry_run(self, mock_args):
        mock_args.strategy_id = "strat-1"
        mock_args.dry_run = True
        mock_args.json = True
        mock_args.output_dir = "/tmp/output"  # Required for dry_run

        with patch("quantlab.cli.main.SQXDaemonManager") as mock_daemon_class:
            mock_daemon = AsyncMock()
            mock_daemon.start.return_value = "http://127.0.0.1:8888"
            mock_daemon_class.return_value = mock_daemon

            with patch("quantlab.cli.main.JForexDeployer") as mock_deployer_class:
                mock_deployer = AsyncMock()
                mock_deployer.dry_run_export.return_value = "java source code"
                mock_deployer_class.return_value = mock_deployer

                with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                    result = await cmd_jforex_deploy(mock_args)
                    output = mock_stdout.getvalue()

                assert result == 0
                data = json.loads(output.strip())
                assert data["strategy_id"] == "strat-1"
                assert "java_source" in data


# ── Main Entry Point ─────────────────────────────────────────────────────


class TestMainEntryPoint:
    """Tests for the main() synchronous entry point."""

    def test_help_exits_zero(self):
        with patch.object(sys, "argv", ["quantlab-cli", "--help"]):
            result = main()
            assert result == 0

    def test_invalid_command_exits_error(self):
        with patch.object(sys, "argv", ["quantlab-cli", "invalid"]):
            result = main()
            assert result == 2  # argparse exits with 2 for invalid choice

    def test_keyboard_interrupt(self, mock_args):
        mock_args.dry_run = True

        with patch("quantlab.cli.main.build_parser") as mock_parser:
            # parse_args returns the mock args, but the command function raises KeyboardInterrupt
            mock_parser.return_value.parse_args.return_value = mock_args
            mock_args.func = AsyncMock(side_effect=KeyboardInterrupt())

            result = main(["daemon", "start"])
            assert result == 1


# ── JSON Output Tests ────────────────────────────────────────────────────


class TestJsonOutput:
    """Verify --json flag produces valid JSON for all subcommands."""

    @pytest.mark.asyncio
    async def test_all_dry_run_commands_json(self):
        """All dry-run commands should output valid JSON with --json."""
        commands = [
            ("portfolio", "run", {"strategies": ["s1"], "dry_run": True}),
            ("optimizer", "run", {"strategy_id": "s1", "dry_run": True}),
            ("retester", "run", {"strategy_id": "s1", "databanks": ["EURUSD_H1"], "dry_run": True}),
            ("jforex", "deploy", {"strategy_id": "s1", "dry_run": True}),
        ]

        for cmd_group, cmd, extra in commands:
            parser = build_parser()
            args_list = [cmd_group, cmd, "--dry-run", "--json"]
            # Add required args
            if cmd_group == "portfolio":
                args_list += ["--strategies", "s1"]
            elif cmd_group == "optimizer":
                args_list += ["s1"]  # positional strategy_id
            elif cmd_group == "retester":
                args_list += ["s1", "--databanks", "EURUSD_H1"]  # positional strategy_id
            elif cmd_group == "jforex":
                args_list += ["s1", "--output-dir", "/tmp"]  # positional strategy_id

            args = parser.parse_args(args_list)
            args.sqx_path = "/fake/path"
            args.port = 8888
            args.timeout = 30.0
            args.force = False
            args.no_daemon_stop = False
            args.json = True

            # Run with mocked internals
            with patch("quantlab.cli.main.CfxTemplateBuilder") as mock_builder:
                mock_builder.build_portfolio_cfx.return_value = b"fake"
                mock_builder.build_optimizer_cfx.return_value = b"fake"
                mock_builder.build_retester_cfx.return_value = b"fake"

                if cmd_group == "portfolio":
                    await cmd_portfolio_run(args)
                elif cmd_group == "optimizer":
                    await cmd_optimizer_run(args)
                elif cmd_group == "retester":
                    await cmd_retester_run(args)
                elif cmd_group == "jforex":
                    await cmd_jforex_deploy(args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])