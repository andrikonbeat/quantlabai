"""Tests for SQXDaemonManager — lifecycle, health checks, binding enforcement."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quantlab.phase4.daemon import SQXDaemonManager
from quantlab.phase4.errors import SQXBindingError, SQXDaemonStartError


class TestSQXDaemonManagerBinding:
    """Tests for bind address enforcement."""

    def test_rejects_non_localhost(self):
        with pytest.raises(SQXBindingError) as exc_info:
            SQXDaemonManager("/opt/SQX", bind_address="0.0.0.0")
        assert exc_info.value.bind_address == "0.0.0.0"

    def test_accepts_localhost(self):
        daemon = SQXDaemonManager("/opt/SQX", bind_address="127.0.0.1")
        assert daemon.bind_address == "127.0.0.1"

    def test_accepts_loopback_ipv6(self):
        daemon = SQXDaemonManager("/opt/SQX", bind_address="::1")
        assert daemon.bind_address == "::1"

    def test_default_bind_is_localhost(self):
        daemon = SQXDaemonManager("/opt/SQX")
        assert daemon.bind_address == "127.0.0.1"


class TestSQXDaemonManagerLifecycle:
    """Tests for daemon start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_launches_sqcli(self, tmp_path):
        sqcli = tmp_path / "sqcli"
        sqcli.write_text("#!/bin/sh\necho 'mock sqcli'\n")
        sqcli.chmod(0o755)

        daemon = SQXDaemonManager(
            str(tmp_path),
            port=18888,
            startup_timeout=2.0,
            max_restarts=0,
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.text = "Usage: sqcli.exe\n-project Manage projects."
                mock_get.return_value = mock_resp

                url = await daemon.start()

                mock_popen.assert_called_once()
                call_args = mock_popen.call_args[0][0]

                # Should NOT have -gui, -port or -bind flags
                # (they only work WITH -gui; without -gui, SQX reads from AppSettings.txt)
                assert "-gui" not in call_args
                assert not any(a.startswith("-port=") for a in call_args)
                assert not any(a.startswith("-bind=") for a in call_args)
                # Port falls back to DEFAULT_PORT (5050) when no AppSettings.txt
                assert url == "http://127.0.0.1:5050"
                # Internal port should be set correctly
                assert daemon.port == 5050

    @pytest.mark.asyncio
    async def test_start_fails_if_sqcli_missing(self, tmp_path):
        daemon = SQXDaemonManager(str(tmp_path), startup_timeout=1.0, max_restarts=0)

        with pytest.raises(SQXDaemonStartError, match="sqcli not found"):
            await daemon.start()

    @pytest.mark.asyncio
    async def test_start_fails_if_process_exits_early(self, tmp_path):
        sqcli = tmp_path / "sqcli"
        sqcli.write_text("#!/bin/sh\nexit 1\n")
        sqcli.chmod(0o755)

        daemon = SQXDaemonManager(str(tmp_path), startup_timeout=2.0, max_restarts=0)

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.poll.return_value = 1
            mock_proc.communicate.return_value = (b"error: java not found", b"")
            mock_popen.return_value = mock_proc

            with pytest.raises(SQXDaemonStartError, match="exited early"):
                await daemon.start()

    @pytest.mark.asyncio
    async def test_start_fails_health_check_timeout(self, tmp_path):
        sqcli = tmp_path / "sqcli"
        sqcli.write_text("#!/bin/sh\nsleep 10\n")
        sqcli.chmod(0o755)

        daemon = SQXDaemonManager(str(tmp_path), startup_timeout=0.5, max_restarts=0)

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.side_effect = Exception("connection refused")

                with pytest.raises(SQXDaemonStartError, match="health check|not ready"):
                    await daemon.start()

    @pytest.mark.asyncio
    async def test_readiness_checks_call_endpoint(self, tmp_path):
        sqcli = tmp_path / "sqcli"
        sqcli.write_text("#!/bin/sh\nsleep 10\n")
        sqcli.chmod(0o755)

        daemon = SQXDaemonManager(str(tmp_path), startup_timeout=5.0, max_restarts=0)

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc

            # Return "not ready" first, then "Usage" to signal readiness
            not_ready_resp = MagicMock()
            not_ready_resp.status_code = 200
            not_ready_resp.text = "Error: CLI not ready."

            ready_resp = MagicMock()
            ready_resp.status_code = 200
            ready_resp.text = "Usage: sqcli.exe\n-project Manage projects."

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.side_effect = [not_ready_resp, ready_resp]

                url = await daemon.start()
                assert url == "http://127.0.0.1:5050"

                # Should have called /call?cmd=-h (not /health)
                call_url = mock_get.call_args[0][0]
                assert "call?cmd=-h" in call_url or "cmd=-h" in call_url

    @pytest.mark.asyncio
    async def test_stop_terminates_process(self, tmp_path):
        sqcli = tmp_path / "sqcli"
        sqcli.write_text("#!/bin/sh\nsleep 10\n")
        sqcli.chmod(0o755)

        daemon = SQXDaemonManager(str(tmp_path), startup_timeout=2.0, max_restarts=0)

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            mock_proc.wait.return_value = 0
            mock_popen.return_value = mock_proc

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.text = "Usage: sqcli.exe"
                mock_get.return_value = mock_resp

                await daemon.start()

        await daemon.stop()
        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_force_kills_on_timeout(self, tmp_path):
        daemon = SQXDaemonManager(str(tmp_path))
        daemon._process = MagicMock()
        daemon._process.poll.return_value = None

        await daemon.stop(force=True)
        daemon._process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_start_stop(self, tmp_path):
        sqcli = tmp_path / "sqcli"
        sqcli.write_text("#!/bin/sh\nsleep 10\n")
        sqcli.chmod(0o755)

        daemon = SQXDaemonManager(str(tmp_path), startup_timeout=2.0, max_restarts=0)

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None
            mock_popen.return_value = mock_proc

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.text = "Usage: sqcli.exe"
                mock_get.return_value = mock_resp

                async with daemon as d:
                    assert d.is_running

                mock_proc.terminate.assert_called_once()


class TestSQXDaemonManagerHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self, tmp_path):
        daemon = SQXDaemonManager(str(tmp_path))
        daemon._process = MagicMock()
        daemon._process.poll.return_value = None

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "Usage: sqcli.exe\n-project Manage projects."
            mock_get.return_value = mock_resp

            result = await daemon.health_check()
            assert result is True
            # Should hit /call?cmd=-h, not /health
            call_url = mock_get.call_args[0][0]
            assert "cmd=-h" in call_url

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self, tmp_path):
        daemon = SQXDaemonManager(str(tmp_path))
        daemon._process = MagicMock()
        daemon._process.poll.return_value = None

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("connection refused")

            result = await daemon.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_if_process_dead(self, tmp_path):
        daemon = SQXDaemonManager(str(tmp_path))
        daemon._process = MagicMock()
        daemon._process.poll.return_value = 1

        result = await daemon.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_checks_usage_in_response(self, tmp_path):
        """Health check verifies 'Usage' appears in the response body."""
        daemon = SQXDaemonManager(str(tmp_path))
        daemon._process = MagicMock()
        daemon._process.poll.return_value = None

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # Response without "Usage" should still return False
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "Error: CLI not ready."
            mock_get.return_value = mock_resp

            result = await daemon.health_check()
            assert result is False


class TestSQXDaemonManagerAutoRestart:
    """Tests for auto-restart on crash."""

    @pytest.mark.asyncio
    async def test_restart_on_crash(self, tmp_path):
        sqcli = tmp_path / "sqcli"
        sqcli.write_text("#!/bin/sh\nsleep 10\n")
        sqcli.chmod(0o755)

        daemon = SQXDaemonManager(str(tmp_path), max_restarts=2, restart_delay=0.1)
        daemon._monitor_interval = 0.05

        with patch("subprocess.Popen") as mock_popen:
            mock_proc1 = MagicMock()
            mock_proc1.poll.return_value = None
            mock_proc1.communicate.return_value = (b"", b"")

            mock_proc2 = MagicMock()
            mock_proc2.poll.return_value = None

            mock_popen.side_effect = [mock_proc1, mock_proc2]

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.text = "Usage: sqcli.exe"
                mock_get.return_value = mock_resp

                await daemon.start()

                # Simulate crash
                mock_proc1.poll.return_value = 1
                mock_proc1.communicate.return_value = (b"", b"crashed")

                await asyncio.sleep(0.3)

                assert mock_popen.call_count >= 2


class TestSQXDaemonManagerGetClient:
    """Tests for get_client method."""

    @pytest.mark.asyncio
    async def test_get_client_returns_async_sqx_client(self, tmp_path):
        daemon = SQXDaemonManager(str(tmp_path))
        daemon._process = MagicMock()
        daemon._process.poll.return_value = None

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "Usage: sqcli.exe"
            mock_get.return_value = mock_resp

            client = await daemon.get_client()
            assert client is not None
            assert client.base_url == daemon.base_url
