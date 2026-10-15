"""SQX Process Manager — lifecycle management for SQX daemon instances.

Provides a clean abstraction over starting/stopping SQX daemons with:
- Dynamic port allocation and collision detection
- Lock-file based single-instance enforcement per install
- Health checks with readiness probing
- Graceful shutdown (``-exit`` → wait → ``SIGTERM``)
- Background crash detection and automatic restart
- Pytest fixtures for deterministic integration testing
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import logging
import os
import signal
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from .settings import sqx_base_url, sqx_timeout
from .http_client import SQXHttpClient

logger = logging.getLogger(__name__)

_DEFAULT_READY_TIMEOUT = 180.0  # 3 minutes for daemon to load projects
_DEFAULT_SHUTDOWN_TIMEOUT = 10.0


class SQXInstance:
    """Handle for a running SQX daemon instance.

    Attributes:
        install_path: Path to the SQX installation root.
        port: Port the daemon is listening on (set after start).
        base_url: Full base URL including port.
        lock_file: Path to the lock file for this instance.
    """

    def __init__(
        self,
        install_path: str,
        port: int | None = None,
        base_url: str | None = None,
    ) -> None:
        self.install_path = install_path
        self.port = port
        self.base_url = base_url or (f"http://127.0.0.1:{port}" if port else None)
        self._lock_file: Optional[Path] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._health_task: Optional[asyncio.Task[None]] = None
        self._restart_on_crash = False

    @property
    def lock_path(self) -> Path:
        """Lock file path for this instance."""
        if self._lock_file is None:
            # Use a hash of the install path + port for unique lock
            import hashlib

            key = f"{self.install_path}:{self.port}".encode()
            hash_suffix = hashlib.sha256(key).hexdigest()[:8]
            self._lock_file = Path(tempfile.gettempdir()) / f"sqx_lock_{hash_suffix}.lock"
        return self._lock_file

    def acquire_lock(self, blocking: bool = True, timeout: float = 30.0) -> bool:
        """Acquire the instance lock.

        Args:
            blocking: If True, wait for lock. If False, return immediately.
            timeout: Max seconds to wait when blocking.

        Returns:
            True if lock acquired, False if timeout (non-blocking mode).
        """
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_fd = open(self.lock_path, "w")
        try:
            if blocking:
                deadline = time.monotonic() + timeout
                while True:
                    try:
                        fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() > deadline:
                            return False
                        time.sleep(0.1)
            else:
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock_fd.close()
            return False
        self._lock_fd.write(str(os.getpid()))
        self._lock_fd.flush()
        return True

    def release_lock(self) -> None:
        """Release the instance lock."""
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            self._lock_fd.close()
            self._lock_fd = None  # type: ignore[assignment]
        except Exception:
            pass


class SQXProcessManager:
    """Manages SQX daemon processes with lifecycle control.

    Features:
    - Start/stop daemons with health checks
    - Dynamic port allocation (default 5050, fallback 5051, then ephemeral)
    - Lock-file single-instance enforcement per install
    - Readiness probing via HTTP ``-h`` endpoint
    - Graceful shutdown (``-exit`` → wait → ``SIGTERM`` → ``SIGKILL``)
    - Background health monitoring with optional auto-restart
    - Multiple isolated instances (Builder, Retester, Optimizer)
    """

    def __init__(
        self,
        default_install_path: str | None = None,
        ready_timeout: float = _DEFAULT_READY_TIMEOUT,
        shutdown_timeout: float = _DEFAULT_SHUTDOWN_TIMEOUT,
    ) -> None:
        self.default_install_path = default_install_path or os.environ.get(
            "SQX_INSTALL_PATH", "assets/SQX_144_2953_linux_20260601"
        )
        self.ready_timeout = ready_timeout
        self.shutdown_timeout = shutdown_timeout
        self._instances: dict[str, SQXInstance] = {}
        self._lock = asyncio.Lock()

    async def ensure_running(
        self,
        install_path: str | None = None,
        port: int | None = None,
        *,
        java_home: str | None = None,
        restart_on_crash: bool = False,
        name: str | None = None,
    ) -> SQXInstance:
        """Ensure an SQX daemon is running and ready.

        This is the main entry point: starts the daemon if not running,
        waits for HTTP API readiness, and returns an instance handle.

        Args:
            install_path: SQX installation root (default: env ``SQX_INSTALL_PATH``).
            port: Specific port to use (default: auto-allocate 5050/5051).
            java_home: JAVA_HOME override (default: ``<install>/j64``).
            restart_on_crash: If True, monitor and auto-restart on crash.
            name: Logical name for the instance (e.g., "Builder", "Retester").

        Returns:
            An ``SQXInstance`` with ``port`` and ``base_url`` populated.

        Raises:
            RuntimeError: If daemon fails to start or become ready.
        """
        install_path = install_path or self.default_install_path
        inst_name = name or f"sqx_{port or 'auto'}"
        key = f"{install_path}:{port or 'auto'}"

        async with self._lock:
            if key in self._instances:
                inst = self._instances[key]
                if inst._proc and inst._proc.returncode is None:
                    # Already running — verify readiness
                    if await self._wait_ready(inst, timeout=5.0):
                        logger.info("SQX instance '%s' already running on port %d", inst_name, inst.port)
                        return inst
                    logger.warning("Existing SQX instance '%s' not ready, restarting", inst_name)
                    await self._stop_instance(inst)

            inst = SQXInstance(install_path, port=port)
            inst._restart_on_crash = restart_on_crash

            if not inst.acquire_lock():
                raise RuntimeError(
                    f"Could not acquire lock for SQX instance at {install_path} "
                    f"(port {port}). Another process may be using it."
                )

            self._instances[key] = inst

        try:
            await self._start_daemon(inst, java_home, inst_name)
            await self._wait_ready(inst, timeout=self.ready_timeout)
            if restart_on_crash:
                inst._health_task = asyncio.create_task(self._health_monitor(inst, inst_name))
            logger.info("SQX instance '%s' ready at %s", inst_name, inst.base_url)
            return inst
        except Exception:
            await self._cleanup_instance(key, inst)
            raise

    async def _start_daemon(
        self, inst: SQXInstance, java_home: str | None, inst_name: str
    ) -> None:
        """Launch the sqcli daemon process."""
        # Kill any existing process on candidate ports
        for port in (5050, 5051):
            proc = await asyncio.create_subprocess_exec(
                "fuser",
                "-k",
                f"{port}/tcp",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

        # Kill any leftover sqcli under this install
        for killer in (
            ("pkill", "-9", "-f", str(Path(inst.install_path) / "sqcli")),
            ("killall", "-9", "sqcli"),
        ):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *killer,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
            except Exception:
                pass

        # Wait for port to be truly free
        for _ in range(5):
            proc = await asyncio.create_subprocess_exec(
                "pgrep",
                "-f",
                str(Path(inst.install_path) / "sqcli"),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode != 0:
                break
            await asyncio.sleep(1)
        await asyncio.sleep(1)

        # Determine port: use specified, else try 5050 then 5051
        candidate_ports = [inst.port] if inst.port else [5050, 5051]
        for candidate_port in candidate_ports:
            try:
                sqcli = Path(inst.install_path) / "sqcli"
                java_home = java_home or str(Path(inst.install_path) / "j64")

                inst._proc = await asyncio.create_subprocess_exec(
                    str(sqcli),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    env={**os.environ, "JAVA_HOME": java_home},
                )

                # Quick probe to see if this port works
                await asyncio.sleep(2)
                test_url = f"http://127.0.0.1:{candidate_port}/call?cmd=-h"
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(test_url)
                    if resp.status_code == 200 and "Usage" in resp.text:
                        inst.port = candidate_port
                        inst.base_url = f"http://127.0.0.1:{candidate_port}"
                        return
            except Exception:
                if inst._proc:
                    inst._proc.terminate()
                    await inst._proc.wait()
                    inst._proc = None
                continue

        raise RuntimeError("No available port for SQX daemon (tried 5050, 5051)")

    async def _wait_ready(self, inst: SQXInstance, timeout: float) -> bool:
        """Wait for HTTP API to report ready (not 'CLI not ready')."""
        if inst.base_url is None:
            return False

        deadline = time.monotonic() + timeout
        async with httpx.AsyncClient(timeout=5.0) as client:
            while time.monotonic() < deadline:
                if inst._proc is not None and inst._proc.returncode is not None:
                    return False
                try:
                    resp = await client.get(f"{inst.base_url}/call?cmd=-h")
                    if resp.status_code == 200:
                        body = resp.text
                        if "Usage" in body and "not ready" not in body.lower():
                            return True
                except Exception:
                    pass
                await asyncio.sleep(1)
        return False

    async def _health_monitor(self, inst: SQXInstance, inst_name: str) -> None:
        """Background task: monitor process health and restart on crash."""
        logger.info("Health monitor started for '%s'", inst_name)
        while inst._restart_on_crash and inst._proc is not None:
            await asyncio.sleep(5.0)
            if inst._proc.returncode is not None:
                logger.warning("SQX instance '%s' exited (code %s), restarting...",
                               inst_name, inst._proc.returncode)
                try:
                    await self._start_daemon(inst, None, inst_name)
                    if await self._wait_ready(inst, timeout=self.ready_timeout):
                        logger.info("SQX instance '%s' restarted successfully", inst_name)
                    else:
                        logger.error("SQX instance '%s' failed to become ready after restart", inst_name)
                        break
                except Exception as e:
                    logger.error("Failed to restart SQX instance '%s': %s", inst_name, e)
                    break

    async def stop(self, install_path: str | None = None, port: int | None = None) -> None:
        """Stop a managed SQX instance gracefully.

        Sends ``-exit`` via HTTP, waits, then ``SIGTERM``, then ``SIGKILL``.
        """
        install_path = install_path or self.default_install_path
        key = f"{install_path}:{port or 'auto'}"

        async with self._lock:
            inst = self._instances.pop(key, None)
            if inst is None:
                logger.warning("No SQX instance found for %s:%s", install_path, port)
                return

        await self._cleanup_instance(f"{install_path}:{port or 'auto'}", inst)

    async def graceful_shutdown(self, inst: SQXInstance) -> None:
        """Graceful shutdown via HTTP ``-exit`` → wait → SIGTERM."""
        if inst.base_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.get(f"{inst.base_url}/call?cmd=-exit")
                # Wait for process to exit
                for _ in range(20):
                    if inst._proc is None or inst._proc.returncode is not None:
                        break
                    await asyncio.sleep(0.5)
            except Exception:
                pass

        # If still running, SIGTERM
        if inst._proc and inst._proc.returncode is None:
            inst._proc.terminate()
            try:
                await asyncio.wait_for(inst._proc.wait(), timeout=self.shutdown_timeout)
            except asyncio.TimeoutError:
                inst._proc.kill()
                await inst._proc.wait()

        # Ensure port is free
        proc = await asyncio.create_subprocess_exec(
            "fuser", "-k", f"{inst.port or 5050}/tcp",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

    async def _cleanup_instance(self, key: str, inst: SQXInstance) -> None:
        """Clean up an instance (stop process, release lock, cancel health task)."""
        if inst._health_task:
            inst._health_task.cancel()
            await asyncio.gather(inst._health_task, return_exceptions=True)

        await self.graceful_shutdown(inst)
        inst.release_lock()

    async def get_client(self, install_path: str | None = None, port: int | None = None) -> Optional[SQXHttpClient]:
        """Get an HTTP client for a running instance."""
        install_path = install_path or self.default_install_path
        key = f"{install_path}:{port or 'auto'}"
        inst = self._instances.get(key)
        if inst and inst.base_url:
            return SQXHttpClient(base_url=inst.base_url)
        return None

    async def health_check(self, install_path: str | None = None, port: int | None = None) -> bool:
        """Check if a managed instance is healthy."""
        install_path = install_path or self.default_install_path
        key = f"{install_path}:{port or 'auto'}"
        inst = self._instances.get(key)
        if not inst or not inst.base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{inst.base_url}/call?cmd=-h")
                return resp.status_code == 200 and "not ready" not in resp.text.lower()
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Fixtures moved to test file to avoid import-time pytest dependency
# See: sdk/tests/sqx/test_process_manager_fixtures.py
# ---------------------------------------------------------------------------

# Re-export for type hints
from .http_client import SQXHttpClient
from .settings import sqx_use_http
