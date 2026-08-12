"""Phase 4 — Async SQX HTTP Client with retry, circuit breaker, command API."""

from __future__ import annotations

import asyncio
import hashlib
import time
import urllib.parse
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from quantlab.phase4.errors import (
    JForexConnectionError,
    JForexServerError,
    JForexStrategyNotFoundError,
    SQXBindingError,
    SQXSessionLockError,
)


DEFAULT_PORT = 5050
COMMAND_ENDPOINT = "/call"


class CircuitBreaker:
    """Simple circuit breaker for HTTP calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        excluded_codes: Optional[set[int]] = None,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.excluded_codes = excluded_codes or {429}

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"  # closed, open, half-open
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.time() - self._last_failure_time > self.recovery_timeout:
                return "half-open"
        return self._state

    async def record_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._state = "closed"

    async def record_failure(self, status_code: Optional[int] = None) -> None:
        async with self._lock:
            if status_code in (429,):
                return
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = "open"

    async def can_execute(self) -> bool:
        async with self._lock:
            if self._state == "open":
                if time.time() - (self._last_failure_time or 0) > self.recovery_timeout:
                    self._state = "half-open"
                    return True
                return False
            return True


class SQXSessionLock:
    """Async lock for SQX single-instance serialization.

    Uses asyncio.Lock for in-process + optional file lock for cross-process.
    Lock file at ~/.quantlab/sqx-{hash}.lock
    """

    def __init__(
        self,
        sqx_install_path: str,
        *,
        use_file_lock: bool = True,
    ):
        self.sqx_install_path = Path(sqx_install_path).resolve()
        self.use_file_lock = use_file_lock
        self._async_lock = asyncio.Lock()
        self._file_lock: Optional[Any] = None
        self._acquired = False

        path_hash = hashlib.sha256(str(self.sqx_install_path).encode()).hexdigest()[:16]
        self._lock_dir = Path.home() / ".quantlab"
        self._lock_file = self._lock_dir / f"sqx-{path_hash}.lock"
        self._lock_dir.mkdir(parents=True, exist_ok=True)

    async def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire both async and file locks."""
        try:
            if timeout is not None:
                await asyncio.wait_for(self._async_lock.acquire(), timeout=timeout)
            else:
                await self._async_lock.acquire()
        except asyncio.TimeoutError:
            if blocking:
                return False
            raise

        if self.use_file_lock:
            try:
                import portalocker
                self._file_lock = open(self._lock_file, "w")
                portalocker.lock(self._file_lock, portalocker.LOCK_EX | portalocker.LOCK_NB)
            except ImportError:
                try:
                    import fcntl
                    self._file_lock = open(self._lock_file, "w")
                    fcntl.flock(self._file_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except Exception:
                    self._file_lock = None

        self._acquired = True
        return True

    def release(self) -> None:
        """Release both locks."""
        if self._acquired:
            if self._file_lock:
                try:
                    import portalocker
                    portalocker.unlock(self._file_lock)
                except ImportError:
                    try:
                        import fcntl
                        fcntl.flock(self._file_lock, fcntl.LOCK_UN)
                    except Exception:
                        pass
                self._file_lock.close()
                self._file_lock = None

            self._async_lock.release()
            self._acquired = False

    async def __aenter__(self) -> "SQXSessionLock":
        await self.acquire()
        return self

    async def __aexit__(self, *args) -> None:
        self.release()


class AsyncSQXClient:
    """Async HTTP client for SQX command-based API with retry and circuit breaker.

    Uses the SQX HTTP API at ``/call?cmd=<command>`` where commands are
    passed as CLI-style arguments (e.g. ``-project action=list``).

    URL encoding rules (verified against SQX v144.2953):
    - Spaces in the command → ``%20`` (NOT ``+``)
    - Equals signs stay as literal ``=``
    - Other special characters → standard URL percent-encoding

    The SQX daemon auto-exits after completing all tasks. For long-running
    projects (e.g. Builder optimization), the daemon stays alive until the
    project finishes.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        bind_address: str = "127.0.0.1",
    ):
        if bind_address not in ("127.0.0.1", "::1", "localhost"):
            raise SQXBindingError(bind_address)

        self.base_url = base_url.rstrip("/")
        self.bind_address = bind_address
        self._timeout_value = timeout
        self._timeout = httpx.Timeout(timeout)
        self._max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self._circuit_breaker = CircuitBreaker()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
            )
        return self._client

    def _encode_command(self, command: str) -> str:
        """Encode a CLI command for the SQX HTTP API.

        Rules:
        - ``%20`` for spaces (NOT ``+`` — verified against SQX v144.2953)
        - ``=`` kept as literal
        - Standard URL encoding for other special characters
        """
        return urllib.parse.quote(command, safe="=")

    async def send_command(self, command: str) -> str:
        """Send a CLI command to SQX via the HTTP API.

        Args:
            command: The command string, e.g. ``"-project action=list"``
                     or ``"-project action=status name=Builder"``.

        Returns:
            The plain-text response body.

        Raises:
            JForexConnectionError: If connection fails or max retries exceeded.
            JForexServerError: If SQX returns a server error.
        """
        if not await self._circuit_breaker.can_execute():
            raise JForexConnectionError(
                self.bind_address, DEFAULT_PORT,
                "Circuit breaker is open",
            )

        encoded = self._encode_command(command)
        url = f"{COMMAND_ENDPOINT}?cmd={encoded}"

        last_exception = None
        for attempt in range(self._max_retries + 1):
            try:
                if not await self._circuit_breaker.can_execute():
                    await asyncio.sleep(1.0)
                    continue

                client = await self._ensure_client()
                resp = await client.get(url)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "1"))
                    await asyncio.sleep(retry_after)
                    continue

                if 500 <= resp.status_code < 600:
                    await self._circuit_breaker.record_failure(resp.status_code)
                    if attempt < self._max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise JForexServerError(resp.status_code, resp.text)

                await self._circuit_breaker.record_success()
                return resp.text

            except httpx.TimeoutException as e:
                await self._circuit_breaker.record_failure()
                last_exception = e
                if attempt < self._max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise JForexConnectionError(
                    self.bind_address, DEFAULT_PORT,
                    f"Timeout after {self._timeout_value}s: {e}",
                )
            except httpx.ConnectError as e:
                await self._circuit_breaker.record_failure()
                last_exception = e
                raise JForexConnectionError(
                    self.bind_address, DEFAULT_PORT,
                    f"Connection failed: {e}",
                )

        raise JForexConnectionError(
            self.bind_address, DEFAULT_PORT,
            f"Max retries ({self._max_retries}) exceeded: {last_exception}",
        )

    async def health_check(self) -> bool:
        """Check if SQX HTTP API is responding by sending ``-h``."""
        try:
            result = await self.send_command("-h")
            return "Usage" in result
        except Exception:
            return False

    async def export_sourcecode(self, strategy_id: str) -> str:
        """Export source code for *strategy_id* via ``/sourcecode/print``.

        Args:
            strategy_id: SQX strategy identifier.

        Returns:
            The Java source code as a string.

        Raises:
            JForexStrategyNotFoundError: If SQX returns HTTP 404.
            JForexConnectionError: If the connection fails.
            JForexServerError: If SQX returns HTTP 5xx.
        """
        client = await self._ensure_client()
        url = f"/sourcecode/print?id={urllib.parse.quote(strategy_id)}"

        try:
            resp = await client.get(url)
        except httpx.TimeoutException as exc:
            raise JForexConnectionError(
                self.bind_address, DEFAULT_PORT,
                f"Timeout exporting source for {strategy_id}: {exc}",
            ) from exc
        except httpx.ConnectError as exc:
            raise JForexConnectionError(
                self.bind_address, DEFAULT_PORT,
                f"Connection failed exporting source for {strategy_id}: {exc}",
            ) from exc

        if resp.status_code == 404:
            raise JForexStrategyNotFoundError(strategy_id)
        if 500 <= resp.status_code < 600:
            raise JForexServerError(resp.status_code, resp.text)

        resp.raise_for_status()
        return resp.text

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "AsyncSQXClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
