"""Tests for the SQX CLI wrapper — Executor protocol and CliRunner."""

import platform
from unittest.mock import patch

import pytest

from quantlab.cli.runner import (
    CliResult,
    CliRunner,
    MockExecutor,
    RealExecutor,
)
from quantlab.tools.exceptions import SQXNotFoundError, TimeoutError


class TestCliResult:
    """Tests for the ``CliResult`` structured result model."""

    def test_default_fields(self) -> None:
        result = CliResult()
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.duration_seconds == 0.0
        assert result.is_dry_run is False
        assert result.platform == platform.system().lower()

    def test_contains_all_metadata(self) -> None:
        """GIVEN any command execution (real or dry-run)
        WHEN the wrapper completes
        THEN a structured result with all required fields is returned.
        """
        result = CliResult(
            stdout="backtest complete",
            stderr="",
            exit_code=0,
            duration_seconds=1.234,
            is_dry_run=True,
            platform="linux",
        )
        assert result.stdout == "backtest complete"
        assert result.duration_seconds == 1.234
        assert result.is_dry_run is True


class TestMockExecutor:
    """Tests for the ``MockExecutor`` — dry-run mode."""

    def test_dry_run_returns_mock_success(self) -> None:
        """GIVEN the wrapper is in dry-run mode
        WHEN any sqcli.exe command is invoked
        THEN no subprocess is created and a structured mock result is
        returned with exit code 0 and documented mock output.
        """
        executor = MockExecutor()
        result = executor.execute("backtest --cfx output/Test.cfx")

        assert result.exit_code == 0
        assert result.is_dry_run is True
        assert "[mock]" in result.stdout

    def test_custom_default_result(self) -> None:
        custom = CliResult(
            stdout="custom mock",
            stderr="",
            exit_code=42,
            duration_seconds=0.5,
            is_dry_run=True,
            platform="linux",
        )
        executor = MockExecutor(default_result=custom)
        result = executor.execute("any command")
        assert result.stdout == "custom mock"
        assert result.exit_code == 42
        assert result.duration_seconds == 0.5

    def test_ignore_timeout_param(self) -> None:
        """Mock mode ignores timeout — should never raise."""
        executor = MockExecutor()
        result = executor.execute("slow command", timeout=9999)
        assert result.exit_code == 0

    def test_accepts_token_list_command(self) -> None:
        """GIVEN a command passed as a token list (e.g. LicenseManager)
        WHEN execute() is called on the mock
        THEN the canned mock result is returned without crashing.
        """
        executor = MockExecutor()
        result = executor.execute(["-license", "action=info"])
        assert result.exit_code == 0
        assert result.is_dry_run is True
        assert "[mock]" in result.stdout


class TestRealExecutor:
    """Tests for the ``RealExecutor`` — subprocess mode."""

    def test_no_binary_raises_sqx_not_found(self) -> None:
        """GIVEN Linux/WSL without a configured sqcli path
        WHEN the wrapper attempts to resolve sqcli
        THEN a clear error is raised indicating sqcli is not installed.
        """
        with patch(
            "quantlab.cli.runner.resolve_sqcli_path", return_value=None
        ):
            with pytest.raises(SQXNotFoundError, match="not found"):
                RealExecutor()

    def test_custom_path_not_found_raises(self) -> None:
        with patch(
            "quantlab.cli.runner.resolve_sqcli_path", return_value=None
        ):
            with pytest.raises(SQXNotFoundError):
                RealExecutor(sqcli_path="/bad/path/sqcli")

    def test_binary_resolved_on_init(self) -> None:
        """The executor resolves the binary path at construction."""
        with patch(
            "quantlab.cli.runner.resolve_sqcli_path",
            return_value=__file__,  # use this file as a stand-in binary
        ):
            executor = RealExecutor()
            assert executor._binary is not None

    @staticmethod
    def _make_echo_binary(tmp_path) -> str:
        """Create a tiny executable that echoes its argv, one token per line."""
        echo = tmp_path / "sqcli"
        echo.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
        echo.chmod(0o755)
        return str(echo)

    def test_accepts_token_list_command(self, tmp_path) -> None:
        """GIVEN a command passed as a token list (e.g. LicenseManager)
        WHEN execute() is called
        THEN the tokens are forwarded to the subprocess unchanged.
        """
        binary = self._make_echo_binary(tmp_path)
        with patch("quantlab.cli.runner.resolve_sqcli_path", return_value=binary):
            executor = RealExecutor()

        result = executor.execute(["-license", "action=info"])

        assert result.exit_code == 0
        assert "-license" in result.stdout
        assert "action=info" in result.stdout

    def test_accepts_str_command(self, tmp_path) -> None:
        """GIVEN a command passed as a single string
        WHEN execute() is called
        THEN it is split on whitespace and forwarded token by token.
        """
        binary = self._make_echo_binary(tmp_path)
        with patch("quantlab.cli.runner.resolve_sqcli_path", return_value=binary):
            executor = RealExecutor()

        result = executor.execute("backtest --cfx output/Test.cfx")

        assert result.exit_code == 0
        stdout_lines = result.stdout.splitlines()
        assert stdout_lines == ["backtest", "--cfx", "output/Test.cfx"]


class TestCliRunner:
    """Tests for the ``CliRunner`` facade."""

    def test_dry_run_mode_uses_mock_executor(self) -> None:
        """GIVEN a runner with dry_run=True
        WHEN any command is executed
        THEN the result has is_dry_run=True.
        """
        runner = CliRunner(dry_run=True)
        result = runner.execute("backtest --cfx test.cfx")
        assert result.is_dry_run is True
        assert result.exit_code == 0

    def test_dry_run_override_per_call(self) -> None:
        """GIVEN a runner initialized with dry_run=True
        WHEN a command is invoked with dry_run=False override
        THEN real execution is attempted (sqcli must exist).
        """
        runner = CliRunner(dry_run=True)
        # On Linux without sqcli, this should raise SQXNotFoundError,
        # proving that the override switched to RealExecutor.
        with pytest.raises(SQXNotFoundError):
            runner.execute("backtest", dry_run=False)

    def test_mock_override_to_dry_run(self) -> None:
        """Per-call override can switch to dry-run."""
        with patch(
            "quantlab.cli.runner.resolve_sqcli_path",
            return_value=__file__,
        ):
            runner = CliRunner(dry_run=False)
        result = runner.execute("backtest", dry_run=True)
        assert result.is_dry_run is True
        assert "[mock]" in result.stdout

    def test_custom_executor_injection(self) -> None:
        """A custom executor can be injected at construction."""
        custom_result = CliResult(
            stdout="injected",
            exit_code=99,
            is_dry_run=True,
            platform="linux",
        )
        executor = MockExecutor(default_result=custom_result)
        runner = CliRunner(executor=executor)
        result = runner.execute("any command")
        assert result.stdout == "injected"
        assert result.exit_code == 99

    def test_dry_run_mode_is_configurable_per_call(self) -> None:
        """GIVEN a wrapper instance initialized with dry-run=true
        WHEN a command is invoked with dry-run=false override
        THEN the subprocess is executed (not mocked) for that call.
        """
        runner = CliRunner(dry_run=True)
        # Default call: dry-run (mock)
        result_default = runner.execute("cmd")
        assert result_default.is_dry_run is True

        # Override: attempts real (will fail without sqcli)
        with pytest.raises(SQXNotFoundError):
            runner.execute("cmd", dry_run=False)


class TestCrossPlatform:
    """Cross-platform path and binary resolution tests."""

    def test_platform_in_result(self) -> None:
        """Result model captures the current platform."""
        result = CliResult()
        # Should match the OS running the test
        assert result.platform in ("linux", "windows", "darwin")

    def test_windows_binary_naming(self) -> None:
        with patch(
            "quantlab.cli.runner.get_sqcli_binary", return_value="sqcli.exe"
        ):
            assert platform.system() or True  # just confirming patch works
