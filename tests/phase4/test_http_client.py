"""Tests for AsyncSQXClient — command API, retry, circuit breaker, encoding."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from quantlab.phase4.http_client import (
    AsyncSQXClient,
    CircuitBreaker,
    SQXSessionLock,
)
from quantlab.phase4.errors import (
    JForexConnectionError,
    JForexServerError,
    JForexStrategyNotFoundError,
    SQXBindingError,
    SQXSessionLockError,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker state machine."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_excluded_codes_not_counted(self):
        cb = CircuitBreaker(failure_threshold=3, excluded_codes={429})
        await cb.record_failure(status_code=429)
        await cb.record_failure(status_code=429)
        assert cb._failure_count == 0
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "open"
        await asyncio.sleep(0.06)
        can_exec = await cb.can_execute()
        assert can_exec is True
        assert cb.state in ("half-open", "closed")


class TestSQXSessionLock:
    """Tests for SQXSessionLock."""

    @pytest.mark.asyncio
    async def test_lock_acquire_release(self, tmp_path):
        lock = SQXSessionLock("/fake/sqx", use_file_lock=False)
        await lock.acquire()
        assert lock._acquired is True
        lock.release()
        assert lock._acquired is False

    @pytest.mark.asyncio
    async def test_lock_context_manager(self, tmp_path):
        lock = SQXSessionLock("/fake/sqx", use_file_lock=False)
        async with lock:
            assert lock._acquired is True
        assert lock._acquired is False

    @pytest.mark.asyncio
    async def test_lock_generates_install_hash(self):
        lock = SQXSessionLock("/opt/SQX/144", use_file_lock=False)
        assert lock._lock_file.name.startswith("sqx-")
        assert lock._lock_file.name.endswith(".lock")
        assert len(lock._lock_file.stem.replace("sqx-", "")) == 16

    @pytest.mark.asyncio
    async def test_lock_blocks_concurrent_acquire(self, tmp_path):
        lock = SQXSessionLock("/fake/sqx", use_file_lock=False)
        await lock.acquire()

        async def try_acquire():
            try:
                await asyncio.wait_for(lock.acquire(), timeout=0.1)
                return True
            except asyncio.TimeoutError:
                return False

        result = await try_acquire()
        assert result is False
        lock.release()

    @pytest.mark.asyncio
    async def test_lock_invalid_install_path(self):
        lock = SQXSessionLock("", use_file_lock=False)
        assert lock._lock_file.name.startswith("sqx-")
        assert lock._lock_file.name.endswith(".lock")


class TestAsyncSQXClient:
    """Tests for AsyncSQXClient."""

    def test_rejects_non_localhost_bind(self):
        with pytest.raises(SQXBindingError):
            AsyncSQXClient("http://192.168.1.1:8888", bind_address="0.0.0.0")

    def test_accepts_localhost_bind(self):
        client = AsyncSQXClient("http://127.0.0.1:5050", bind_address="127.0.0.1")
        assert client.bind_address == "127.0.0.1"

    def test_accepts_ipv6_loopback(self):
        client = AsyncSQXClient("http://[::1]:5050", bind_address="::1")
        assert client.bind_address == "::1"

    # ── Command encoding ──────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "command,expected",
        [
            ("-h", "-h"),
            ("-project action=list", "-project%20action=list"),
            ("-project action=start name=Builder", "-project%20action=start%20name=Builder"),
            ("simple", "simple"),
            ("-project action=status name=My Campaign", "-project%20action=status%20name=My%20Campaign"),
        ],
    )
    def test_encode_command(self, command, expected):
        client = AsyncSQXClient("http://127.0.0.1:5050")
        assert client._encode_command(command) == expected

    # ── send_command ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_send_command_basic(self):
        client = AsyncSQXClient("http://127.0.0.1:5050")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "List of available projects\nBuilder\nPortfolioMaster"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            result = await client.send_command("-project action=list")
            assert "Builder" in result
            assert "PortfolioMaster" in result

            # Verify URL encoding
            call_url = mock_get.call_args[0][0]
            assert "%20" in call_url or "action=" in call_url

    @pytest.mark.asyncio
    async def test_send_command_with_special_chars(self):
        client = AsyncSQXClient("http://127.0.0.1:5050")
        command = '-project action=start name="My Project"'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Started"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            result = await client.send_command(command)
            assert result == "Started"

    @pytest.mark.asyncio
    async def test_retry_on_5xx(self):
        client = AsyncSQXClient("http://127.0.0.1:5050", max_retries=2)

        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        mock_resp_500.text = "Internal Error"

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.text = "OK"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [mock_resp_500, mock_resp_200]

            result = await client.send_command("-h")
            assert result == "OK"
            assert mock_req.call_count == 2

    @pytest.mark.asyncio
    async def test_429_respects_retry_after(self):
        client = AsyncSQXClient("http://127.0.0.1:5050", max_retries=3)

        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.headers = {"Retry-After": "0"}

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.text = "OK"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_req:
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                mock_req.side_effect = [mock_resp_429, mock_resp_200]

                result = await client.send_command("-h")
                assert mock_req.call_count == 2
                mock_sleep.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_timeout_raises_connection_error(self):
        client = AsyncSQXClient("http://127.0.0.1:5050", max_retries=1)

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.TimeoutException("timeout")

            with pytest.raises(JForexConnectionError, match="Timeout"):
                await client.send_command("-h")

    @pytest.mark.asyncio
    async def test_connect_error_raises_connection_error(self):
        client = AsyncSQXClient("http://127.0.0.1:5050")

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.ConnectError("connection refused")

            with pytest.raises(JForexConnectionError, match="Connection failed"):
                await client.send_command("-h")

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_calls(self):
        client = AsyncSQXClient("http://127.0.0.1:5050", max_retries=0)
        client._circuit_breaker._state = "open"
        client._circuit_breaker._failure_count = 5
        # Set last failure to recent so recovery timeout hasn't elapsed
        import time
        client._circuit_breaker._last_failure_time = time.time()
        client._circuit_breaker.recovery_timeout = 60.0

        with pytest.raises(JForexConnectionError):
            await client.send_command("-h")

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self):
        client = AsyncSQXClient("http://127.0.0.1:5050")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Usage: sqcli.exe\n-project Manage projects."

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false(self):
        client = AsyncSQXClient("http://127.0.0.1:5050")

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("connection refused")
            result = await client.health_check()
            assert result is False


class TestAsyncSQXClientExportSourcecode:
    """REQ-601: AsyncSQXClient.export_sourcecode()."""

    @pytest.mark.asyncio
    async def test_export_returns_source_string(self):
        """GIVEN SQX server with strategy "s1"
        WHEN export_sourcecode("s1") is called
        THEN HTTP GET /sourcecode/print?id=s1 is issued
        AND the response body is returned as a string.
        """
        client = AsyncSQXClient("http://127.0.0.1:5050")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "public class S1 {}"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            result = await client.export_sourcecode("s1")
            assert result == "public class S1 {}"
            call_url = mock_get.call_args[0][0]
            assert "/sourcecode/print?id=s1" in call_url

    @pytest.mark.asyncio
    async def test_export_404_raises_not_found(self):
        """GIVEN SQX returns 404 for strategy "missing"
        WHEN export_sourcecode("missing") is called
        THEN JForexStrategyNotFoundError is raised.
        """
        client = AsyncSQXClient("http://127.0.0.1:5050")

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not found"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            with pytest.raises(JForexStrategyNotFoundError, match="missing"):
                await client.export_sourcecode("missing")

    @pytest.mark.asyncio
    async def test_export_5xx_raises_server_error(self):
        """GIVEN SQX returns 500
        WHEN export_sourcecode("s1") is called
        THEN JForexServerError is raised with the response body preserved.
        """
        client = AsyncSQXClient("http://127.0.0.1:5050")

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal server error"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            with pytest.raises(JForexServerError, match="500"):
                await client.export_sourcecode("s1")

    @pytest.mark.asyncio
    async def test_export_network_failure_raises_connection_error(self):
        """GIVEN SQX is unreachable
        WHEN export_sourcecode("s1") is called
        THEN JForexConnectionError is raised.
        """
        client = AsyncSQXClient("http://127.0.0.1:5050")

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("connection refused")

            with pytest.raises(JForexConnectionError, match="Connection failed"):
                await client.export_sourcecode("s1")

    @pytest.mark.asyncio
    async def test_export_quotes_strategy_id_in_url(self):
        """GIVEN a strategy_id with special characters
        WHEN export_sourcecode() is called
        THEN the strategy_id is URL-encoded in the request path.
        """
        client = AsyncSQXClient("http://127.0.0.1:5050")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "source"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            await client.export_sourcecode("strategy with spaces")
            call_url = mock_get.call_args[0][0]
            assert "strategy%20with%20spaces" in call_url

    @pytest.mark.asyncio
    async def test_export_other_4xx_raises_http_error(self):
        """GIVEN SQX returns 403
        WHEN export_sourcecode("s1") is called
        THEN raise_for_status raises an HTTP error.
        """
        client = AsyncSQXClient("http://127.0.0.1:5050")

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=None, response=mock_resp
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp

            with pytest.raises(httpx.HTTPStatusError):
                await client.export_sourcecode("s1")


class TestSQXSessionLockIntegration:
    """Integration tests for SQXSessionLock with real file system."""

    @pytest.mark.asyncio
    async def test_file_lock_created_in_quantlab_dir(self, tmp_path):
        lock_dir = tmp_path / ".quantlab"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock = SQXSessionLock("/fake/sqx", use_file_lock=True)
        lock._lock_dir = lock_dir
        lock._lock_file = lock_dir / "sqx-test123.lock"

        await lock.acquire()
        assert lock._lock_file.exists()
        lock.release()

    @pytest.mark.asyncio
    async def test_multiple_locks_different_paths(self, tmp_path):
        lock_dir = tmp_path / ".quantlab"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock1 = SQXSessionLock("/opt/SQX/1", use_file_lock=True)
        lock1._lock_dir = lock_dir
        lock1._lock_file = lock_dir / "sqx-hash1.lock"

        lock2 = SQXSessionLock("/opt/SQX/2", use_file_lock=True)
        lock2._lock_dir = lock_dir
        lock2._lock_file = lock_dir / "sqx-hash2.lock"

        await lock1.acquire()
        await lock2.acquire()  # Should not block (different files)

        lock1.release()
        lock2.release()
