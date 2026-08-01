"""Tests for dashboard foundation — DashboardServer and create_app."""

import pytest
from unittest.mock import patch

from sdk.quantlab.dashboard.app import DashboardServer, ServerConfig, create_app


class TestServerConfig:
    """ServerConfig construction and defaults."""

    def test_server_config_defaults(self):
        config = ServerConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.debug is False

    def test_server_config_custom(self):
        config = ServerConfig(host="0.0.0.0", port=9090, debug=True)
        assert config.host == "0.0.0.0"
        assert config.port == 9090
        assert config.debug is True


class TestDashboardServer:
    """DashboardServer construction and configuration."""

    def test_dashboard_server_requires_config(self):
        with pytest.raises(TypeError):
            DashboardServer()

    def test_dashboard_server_creation(self, mock_cli_runner):
        config = ServerConfig(port=9090)
        with patch("sdk.quantlab.dashboard.app.CliRunner", return_value=mock_cli_runner):
            server = DashboardServer(config=config)
        assert server.config is not None
        assert server.config.port == 9090

    def test_dashboard_server_url(self, mock_cli_runner):
        config = ServerConfig(host="127.0.0.1", port=7070)
        with patch("sdk.quantlab.dashboard.app.CliRunner", return_value=mock_cli_runner):
            server = DashboardServer(config=config)
        assert server.url == "http://127.0.0.1:7070"

    def test_dashboard_server_is_running_initially_false(self, mock_cli_runner):
        config = ServerConfig()
        with patch("sdk.quantlab.dashboard.app.CliRunner", return_value=mock_cli_runner):
            server = DashboardServer(config=config)
        assert server.is_running is False


class TestCreateApp:
    """create_app factory returns a Flask app."""

    def test_create_app_returns_flask_app(self, mock_cli_runner):
        with patch("sdk.quantlab.dashboard.app.CliRunner", return_value=mock_cli_runner):
            app = create_app()
        assert app is not None

    def test_create_app_with_config(self, mock_cli_runner):
        config = ServerConfig(host="127.0.0.1", port=7070)
        with patch("sdk.quantlab.dashboard.app.CliRunner", return_value=mock_cli_runner):
            app = create_app(config=config)
        assert app is not None


class TestDashboardCLISubcommand:
    """Dashboard CLI subcommand registration."""

    def test_dashboard_subcommand_registered(self):
        from sdk.quantlab.cli.main import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["dashboard", "--help"])
        assert exc_info.value.code == 0

    def test_dashboard_start_shows_help(self):
        from sdk.quantlab.cli.main import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["dashboard", "start", "--help"])
        assert exc_info.value.code == 0

    def test_dashboard_stop_shows_help(self):
        from sdk.quantlab.cli.main import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["dashboard", "stop", "--help"])
        assert exc_info.value.code == 0

    def test_dashboard_status_shows_help(self):
        from sdk.quantlab.cli.main import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["dashboard", "status", "--help"])
        assert exc_info.value.code == 0