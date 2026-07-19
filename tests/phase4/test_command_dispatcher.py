"""Tests for CommandDispatcher — CLI command-based API operations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quantlab.phase4.command_dispatcher import CampaignStatus, CommandDispatcher
from quantlab.phase4.errors import (
    JForexConnectionError,
    SQXSessionLockError,
)
from quantlab.phase4.http_client import (
    AsyncSQXClient,
    SQXSessionLock,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_client(**kwargs) -> AsyncSQXClient:
    """Create a real AsyncSQXClient for testing.

    The HTTP layer is mocked per-test; this just gives us a real object
    whose ``send_command`` we can patch.
    """
    return AsyncSQXClient("http://127.0.0.1:5050", **kwargs)


# ── CampaignStatus ───────────────────────────────────────────────────────────


class TestCampaignStatus:
    """CampaignStatus construction and text parsing."""

    def test_from_text_basic(self):
        text = (
            "Project: my_campaign\n"
            "Status: running\n"
            "Progress: 45%\n"
            "Generation: 2/10\n"
        )
        status = CampaignStatus.from_text(text)
        assert status.campaign_name == "my_campaign"
        assert status.status == "running"
        assert status.progress == 45.0
        assert status.current_generation == 2
        assert status.total_generations == 10
        assert status.error_message is None

    def test_from_text_with_error(self):
        text = (
            "Project: broken\n"
            "Status: failed\n"
            "Error: Strategy not found\n"
        )
        status = CampaignStatus.from_text(text, "broken")
        assert status.status == "failed"
        assert status.error_message in ("Strategy not found", "Error: Strategy not found")
        assert status.is_failed is True
        assert status.is_running is False
        assert status.is_complete is False

    def test_from_text_completed(self):
        text = "Builder finished successfully.\nAll tasks completed."
        status = CampaignStatus.from_text(text, "Builder")
        assert status.campaign_name == "Builder"
        assert status.is_complete is True
        assert status.progress == 0.0

    def test_from_text_unknown_status(self):
        text = "Some random output without clear status"
        status = CampaignStatus.from_text(text)
        assert status.campaign_name == "unknown"
        assert status.status == "unknown"
        assert status.progress == 0.0
        assert status.current_generation == 0

    def test_from_text_keyword_matches(self):
        text = "Test run started"
        status = CampaignStatus.from_text(text, "test")
        assert status.status == "running"

        text2 = "All tasks completed"
        status2 = CampaignStatus.from_text(text2, "test")
        assert status2.is_complete is True

        text3 = "Error: Out of memory"
        status3 = CampaignStatus.from_text(text3, "test")
        assert status3.is_failed is True

    @pytest.mark.parametrize(
        "status_str,expected",
        [
            ("completed", True),
            ("finished", True),
            ("done", True),
            ("success", True),
            ("running", False),
            ("in progress", False),
            ("failed", False),
        ],
    )
    def test_is_complete(self, status_str, expected):
        status = CampaignStatus("test", status_str)
        assert status.is_complete is expected

    def test_is_running(self):
        for s in ("running", "in progress", "working"):
            assert CampaignStatus("test", s).is_running is True
        assert CampaignStatus("test", "completed").is_running is False

    def test_is_failed(self):
        for s in ("failed", "error", "aborted"):
            assert CampaignStatus("test", s).is_failed is True
        assert CampaignStatus("test", "running").is_failed is False

    def test_repr(self):
        status = CampaignStatus("test", "running", progress=50.0)
        assert "test" in repr(status)
        assert "running" in repr(status)

    def test_repr_with_error(self):
        status = CampaignStatus("test", "error", error_message="boom")
        assert "boom" in repr(status)


# ── CommandDispatcher ────────────────────────────────────────────────────────


class TestCommandDispatcherConstructor:
    """CommandDispatcher construction."""

    def test_accepts_client(self):
        client = make_client()
        d = CommandDispatcher(client)
        assert d._client is client

    def test_default_lock_created(self):
        client = make_client()
        d = CommandDispatcher(client)
        assert isinstance(d._lock, SQXSessionLock)
        assert d._lock.use_file_lock is False

    def test_use_file_lock(self):
        client = make_client()
        d = CommandDispatcher(client, use_file_lock=True)
        assert d._lock.use_file_lock is True

    def test_lock_blocking_and_timeout(self):
        client = make_client()
        d = CommandDispatcher(client, lock_blocking=False, lock_timeout=5.0)
        assert d._lock_blocking is False
        assert d._lock_timeout == 5.0

    def test_accepts_sqx_install_path(self):
        client = make_client()
        d = CommandDispatcher(client, sqx_install_path="/opt/SQX")
        assert d._sqx_install_path == Path("/opt/SQX")


class TestCommandDispatcherFromDaemon:
    """CommandDispatcher.from_daemon() classmethod."""

    @pytest.mark.asyncio
    async def test_from_daemon_creates_dispatcher(self):
        client = make_client()
        mock_daemon = MagicMock()
        mock_daemon.get_client = AsyncMock(return_value=client)
        from quantlab.phase4.daemon import SQXDaemonManager

        with patch.object(SQXDaemonManager, "get_client", return_value=client):
            mock_daemon.__class__ = SQXDaemonManager
            dispatcher = await CommandDispatcher.from_daemon(mock_daemon)
            assert isinstance(dispatcher, CommandDispatcher)
            assert dispatcher._client is client

    @pytest.mark.asyncio
    async def test_from_daemon_rejects_wrong_type(self):
        with pytest.raises(TypeError, match="SQXDaemonManager"):
            await CommandDispatcher.from_daemon("not_a_daemon")

    @pytest.mark.asyncio
    async def test_from_daemon_forwards_kwargs(self):
        client = make_client()
        mock_daemon = MagicMock()
        mock_daemon.get_client = AsyncMock(return_value=client)
        from quantlab.phase4.daemon import SQXDaemonManager

        mock_daemon.__class__ = SQXDaemonManager
        dispatcher = await CommandDispatcher.from_daemon(
            mock_daemon, use_file_lock=True, sqx_install_path="/opt/SQX"
        )
        assert dispatcher._lock.use_file_lock is True
        assert dispatcher._sqx_install_path == Path("/opt/SQX")


# ── Campaign operations ──────────────────────────────────────────────────────


class TestCommandDispatcherOperations:
    """Test each campaign method with mocked send_command."""

    @pytest.fixture(autouse=True)
    def _dispatcher(self):
        self.client = make_client()
        self.dispatcher = CommandDispatcher(
            self.client,
            use_file_lock=False,
            sqx_install_path="/opt/SQX",
        )

    # ── load_config ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_load_config(self, tmp_path):
        cfx_file = tmp_path / "test.cfx"
        cfx_file.write_text("<cfx>content</cfx>")

        with patch.object(self.client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "Config loaded successfully"

            result = await self.dispatcher.load_config(cfx_file)

            assert "loaded" in result.lower()
            # Verify the command contains the right args
            call_cmd = mock_send.call_args[0][0]
            assert "action=loadconfig" in call_cmd
            assert str(cfx_file) in call_cmd

    @pytest.mark.asyncio
    async def test_load_config_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            await self.dispatcher.load_config("/nonexistent/file.cfx")

    # ── start_project ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_start_project(self):
        with patch.object(self.client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "Project started"

            result = await self.dispatcher.start_project("Builder")

            assert result == "Project started"
            mock_send.assert_called_once()
            call_cmd = mock_send.call_args[0][0]
            assert "-project action=start" in call_cmd
            assert "Builder" in call_cmd

    @pytest.mark.asyncio
    async def test_start_project_empty_name(self):
        with patch.object(self.client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "Started"
            result = await self.dispatcher.start_project("")
            assert result == "Started"

    # ── stop_project ───────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_stop_project(self):
        with patch.object(self.client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "Project stopped"

            result = await self.dispatcher.stop_project("Builder")

            assert result == "Project stopped"
            call_cmd = mock_send.call_args[0][0]
            assert "-project action=stop" in call_cmd
            assert "Builder" in call_cmd

    # ── get_status ─────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_status(self):
        status_text = (
            "Project: Builder\n"
            "Status: running\n"
            "Progress: 65%\n"
            "Generation: 3/10\n"
        )

        with patch.object(self.client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = status_text

            status = await self.dispatcher.get_status("Builder")

            assert status.campaign_name == "Builder"
            assert status.status == "running"
            assert status.progress == 65.0
            assert status.current_generation == 3
            assert status.total_generations == 10
            call_cmd = mock_send.call_args[0][0]
            assert "action=status" in call_cmd

    @pytest.mark.asyncio
    async def test_get_status_completed(self):
        text = "Builder completed successfully. All tasks done."
        with patch.object(self.client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = text
            status = await self.dispatcher.get_status("Builder")
            assert status.is_complete is True

    # ── list_projects ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_projects(self):
        project_text = (
            "23:45:22 List of available projects\n"
            "-------------------------------------------\n"
            "PortfolioMaster\n"
            "PortfolioComposer\n"
            "Builder\n"
            "Optimizer\n"
        )

        with patch.object(self.client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = project_text

            projects = await self.dispatcher.list_projects()

            assert "Builder" in projects
            assert "PortfolioMaster" in projects
            assert "List of" not in projects  # Should strip headers
            assert "23:45:22" not in projects  # Should strip timestamps
            assert len(projects) == 4

    # ── export_results ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_export_results_no_sqx_path(self, tmp_path):
        """Without sqx_install_path, export creates a placeholder."""
        dispatcher = CommandDispatcher(self.client, use_file_lock=False)

        with patch.object(self.client, "send_command", new_callable=AsyncMock):
            result_path = await dispatcher.export_results("Builder", tmp_path)

            expected = tmp_path / "Builder_results.csv"
            assert result_path == str(expected)
            assert expected.exists()
            assert "Results" in expected.read_text()

    @pytest.mark.asyncio
    async def test_export_results_copies_file(self, tmp_path):
        """With sqx_install_path, export copies existing CSV files."""
        # Create a mock results directory
        results_dir = Path("/opt/SQX") / "user/strategies" / "Builder"
        results_dir = tmp_path / "user" / "strategies" / "Builder"
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "results.csv").write_text("symbol,value\nEURUSD,1.23")

        dispatcher = CommandDispatcher(
            self.client,
            use_file_lock=False,
            sqx_install_path=tmp_path,
        )

        with patch.object(self.client, "send_command", new_callable=AsyncMock):
            result_path = await dispatcher.export_results("Builder", tmp_path)

            expected = tmp_path / "Builder_results.csv"
            assert result_path == str(expected)
            assert expected.exists()
            assert "EURUSD" in expected.read_text()

    # ── export_retest_report ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_export_retest_report(self, tmp_path):
        output_path = tmp_path / "retest.html"

        dispatcher = CommandDispatcher(
            self.client,
            use_file_lock=False,
            sqx_install_path=tmp_path,
        )

        with patch.object(self.client, "send_command", new_callable=AsyncMock):
            result = await dispatcher.export_retest_report(
                "Builder", output_path
            )

            assert result == str(output_path)
            assert output_path.exists()

    @pytest.mark.asyncio
    async def test_export_retest_copies_html(self, tmp_path):
        retest_dir = tmp_path / "user/retest" / "Builder"
        retest_dir.mkdir(parents=True, exist_ok=True)
        (retest_dir / "report.html").write_text("<html>Report</html>")

        dispatcher = CommandDispatcher(
            self.client, use_file_lock=False, sqx_install_path=tmp_path,
        )
        output = tmp_path / "out.html"

        with patch.object(self.client, "send_command", new_callable=AsyncMock):
            result = await dispatcher.export_retest_report("Builder", output)

            assert "<html>" in output.read_text()

    # ── export_databanks ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_export_databanks(self, tmp_path):
        retest_dir = tmp_path / "user/retest" / "Builder"
        retest_dir.mkdir(parents=True, exist_ok=True)
        (retest_dir / "data.csv").write_text("data")
        (retest_dir / "model.dat").write_text("binary")

        dispatcher = CommandDispatcher(
            self.client, use_file_lock=False, sqx_install_path=tmp_path,
        )
        output_dir = tmp_path / "export"

        with patch.object(self.client, "send_command", new_callable=AsyncMock):
            files = await dispatcher.export_databanks("Builder", output_dir)

            assert len(files) >= 2
            assert any("data.csv" in f for f in files)

    # ── get_results_xml ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_results_xml(self, tmp_path):
        strategies_dir = tmp_path / "user/strategies" / "Builder"
        strategies_dir.mkdir(parents=True, exist_ok=True)
        (strategies_dir / "results.xml").write_text(
            '<?xml version="1.0"?><results/>'
        )

        dispatcher = CommandDispatcher(
            self.client, use_file_lock=False, sqx_install_path=tmp_path,
        )

        with patch.object(self.client, "send_command", new_callable=AsyncMock):
            result = await dispatcher.get_results_xml("Builder")
            assert "<results" in result


# ── Error handling ────────────────────────────────────────────────────────────


class TestCommandDispatcherErrors:
    """Error propagation from HTTP client."""

    @pytest.fixture(autouse=True)
    def _dispatcher(self):
        self.client = make_client()
        self.dispatcher = CommandDispatcher(self.client, use_file_lock=False)

    @pytest.mark.asyncio
    async def test_connection_error_propagated(self):
        with patch.object(self.client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = JForexConnectionError(
                "127.0.0.1", 5050, "Connection refused"
            )

            with pytest.raises(JForexConnectionError, match="Connection refused"):
                await self.dispatcher.get_status("test")

    @pytest.mark.asyncio
    async def test_lock_timeout_raises(self):
        client = make_client()
        dispatcher = CommandDispatcher(
            client,
            use_file_lock=False,
            lock_blocking=True,
            lock_timeout=0.01,
        )

        await dispatcher._lock.acquire()

        with pytest.raises(SQXSessionLockError):
            await dispatcher.get_status("test")

        dispatcher._lock.release()

    @pytest.mark.asyncio
    async def test_non_blocking_lock_raises_when_held(self):
        client = make_client()
        dispatcher = CommandDispatcher(
            client, use_file_lock=False, lock_blocking=False
        )

        await dispatcher._lock.acquire()

        with pytest.raises(SQXSessionLockError):
            await dispatcher.get_status("test")

        dispatcher._lock.release()


# ── Lock integration ─────────────────────────────────────────────────────────


class TestCommandDispatcherLock:
    """SessionLock acquire/release lifecycle."""

    @pytest.mark.asyncio
    async def test_lock_released_after_operation(self):
        client = make_client()
        dispatcher = CommandDispatcher(client, use_file_lock=False)

        with patch.object(client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "OK"
            await dispatcher.start_project("test")

        # Lock should be released
        await dispatcher._lock.acquire()
        dispatcher._lock.release()

    @pytest.mark.asyncio
    async def test_lock_released_on_error(self):
        client = make_client()
        dispatcher = CommandDispatcher(client, use_file_lock=False)

        with patch.object(client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = JForexConnectionError(
                "127.0.0.1", 5050, "fail"
            )

            with pytest.raises(JForexConnectionError):
                await dispatcher.get_status("test")

        # Lock should be released despite the error
        await dispatcher._lock.acquire()
        dispatcher._lock.release()

    @pytest.mark.asyncio
    async def test_concurrent_operations_serialized(self):
        client = make_client()
        dispatcher = CommandDispatcher(client, use_file_lock=False)

        ok_resp = "OK"
        with patch.object(client, "send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = ok_resp

            async def op1():
                await dispatcher.start_project("a")

            async def op2():
                await dispatcher.start_project("b")

            await asyncio.gather(op1(), op2())
            assert mock_send.call_count == 2


# ── Close ────────────────────────────────────────────────────────────────────


class TestCommandDispatcherClose:
    """Close lifecycle."""

    @pytest.mark.asyncio
    async def test_close_calls_client_close(self):
        client = make_client()
        dispatcher = CommandDispatcher(client)

        with patch.object(client, "close", new_callable=AsyncMock) as mock_close:
            await dispatcher.close()
            mock_close.assert_called_once()
