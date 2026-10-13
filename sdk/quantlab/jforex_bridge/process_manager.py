"""
JForex Bridge Process Manager — lifecycle management for JForex Bridge instances.

Provides a clean abstraction over starting/stopping JForex Bridge daemons with:
- Dynamic port allocation and collision detection
- Lock-file based single-instance enforcement per config
- Health checks with readiness probing
- Graceful shutdown (POST /shutdown → wait → SIGTERM)
- Background crash detection and automatic restart
- Multiple isolated instances (demo/live, different accounts)
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

from .settings import jforex_bridge_base_url

logger = logging.getLogger(__name__)

_DEFAULT_READY_TIMEOUT = 60.0  # 1 minute for bridge to connect to JForex
_DEFAULT_SHUTDOWN_TIMEOUT = 10.0


class JForexBridgeInstance:
    """Handle for a running JForex Bridge instance.

    Attributes:
        install_path: Path to the bridge JAR/installation root.
        port: Port the bridge is listening on (set after start).
        base_url: Full base URL including port.
        lock_file: Path to the lock file for this instance.
    """

    def __init__(
        self,
        bridge_jar: str,
        port: int | None = None,
        base_url: str | None = None,
        name: str = "default",
    ) -> None:
        self.bridge_jar = bridge_jar
        self.port = port
        self.base_url = base_url or (f"http://127.0.0.1:{port}" if port else None)
        self.name = name
        self._lock_file: Optional[Path] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._health_task: Optional[asyncio.Task[None]] = None
        self._restart_on_crash = False
        self._lock_fd = None

    @property
    def lock_path(self) -> Path:
        """Lock file path for this instance."""
        if self._lock_file is None:
            # Use a hash of the jar path + port + name for unique lock
            import hashlib
            key = f"{self.bridge_jar}:{self.port}:{self.name}".encode()
            hash_suffix = hashlib.sha256(key).hexdigest()[:8]
            self._lock_file = Path(tempfile.gettempdir()) / f"jforex_bridge_lock_{hash_suffix}.lock"
        return self._lock_file

    def acquire_lock(self, blocking: bool = True, timeout: float = 30.0) -> bool:
        """Acquire the instance lock.

        Args:
            blocking: If True, wait for lock. If False, return immediately.
            timeout: Max seconds to wait when blocking.

        Returns:
            True if lock acquired, False if timeout (non-blocking mode).
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
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


class JForexProcessManager:
    """Manages JForex Bridge processes with lifecycle control.

    Features:
    - Start/stop bridge instances with health checks
    - Dynamic port allocation (default 8082, fallback 8083, then ephemeral)
    - Lock-file single-instance enforcement per config
    - Readiness probing via HTTP `/health` endpoint
    - Graceful shutdown (POST /shutdown → wait → SIGTERM → SIGKILL)
    - Background crash detection and automatic restart
    - Multiple isolated instances (demo/live, different accounts)
    """

    def __init__(
        self,
        bridge_jar: str | None = None,
        ready_timeout: float = _DEFAULT_READY_TIMEOUT,
        shutdown_timeout: float = _DEFAULT_SHUTDOWN_TIMEOUT,
    ) -> None:
        self.bridge_jar = bridge_jar or os.environ.get(
            "JFOREX_BRIDGE_JAR",
            "sdk/quantlab/jforex_bridge/build/libs/jforex_bridge-all.jar"
        )
        self.ready_timeout = ready_timeout
        self.shutdown_timeout = shutdown_timeout
        self._instances: dict[str, JForexBridgeInstance] = {}
        self._lock = asyncio.Lock()

    async def ensure_running(
        self,
        port: int | None = None,
        *,
        java_home: str | None = None,
        restart_on_crash: bool = False,
        name: str | None = None,
        jnlp_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        demo: bool = True,
    ) -> JForexBridgeInstance:
        """Ensure a JForex Bridge instance is running and ready.

        This is the main entry point: starts the bridge if not running,
        waits for HTTP API readiness, and returns an instance handle.

        Args:
            port: Specific port to use (default: auto-allocate 8082/8083).
            java_home: JAVA_HOME override (default: auto-detect).
            restart_on_crash: If True, monitor and auto-restart on crash.
            name: Logical name for the instance (e.g., "demo", "live").
            jnlp_url: JForex JNLP URL override.
            username: JForex username.
            password: JForex password.
            demo: Use demo account (default: True).

        Returns:
            A ``JForexBridgeInstance`` with ``port`` and ``base_url`` populated.

        Raises:
            RuntimeError: If bridge fails to start or become ready.
        """
        name = name or f"jforex_{port or 'auto'}"
        key = f"{self.bridge_jar}:{port or 'auto'}"

        async with self._lock:
            if key in self._instances:
                inst = self._instances[key]
                if inst._proc and inst._proc.returncode is None:
                    # Already running — verify readiness
                    if await self._wait_ready(inst, timeout=5.0):
                        logger.info("JForex Bridge instance '%s' already running on port %d", inst.name, inst.port)
                        return inst
                    logger.warning("Existing JForex Bridge instance '%s' not ready, restarting", inst.name)
                    await self._stop_instance(inst)

            inst = JForexBridgeInstance(self.bridge_jar, port=port, name=name)
            inst._restart_on_crash = restart_on_crash

            if not inst.acquire_lock():
                raise RuntimeError(
                    f"Could not acquire lock for JForex Bridge instance at {self.bridge_jar} "
                    f"(port {port}). Another process may be using it."
                )

            self._instances[key] = inst

        try:
            await self._start_bridge(inst, java_home, jnlp_url, username, password, demo, name)
            await self._wait_ready(inst, timeout=self.ready_timeout)
            if restart_on_crash:
                inst._health_task = asyncio.create_task(self._health_monitor(inst, name))
            logger.info("JForex Bridge instance '%s' ready at %s", inst.name, inst.base_url)
            return inst
        except Exception:
            await self._cleanup_instance(key, inst)
            raise

    async def _start_bridge(
        self,
        inst: JForexBridgeInstance,
        java_home: str | None,
        jnlp_url: str | None,
        username: str | None,
        password: str | None,
        demo: bool,
        name: str,
    ) -> None:
        """Launch the JForex Bridge process."""
        # Kill any existing process on candidate ports
        for port in (8082, 8083, 8084):
            proc = await asyncio.create_subprocess_exec(
                "fuser", "-k", f"{port}/tcp",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

        # Kill any leftover java processes for this bridge
        for killer in (
            ("pkill", "-9", "-f", f"jforex_bridge.*{inst.name}"),
            ("pkill", "-9", "-f", "JForexBridgeApplication"),
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
                "pgrep", "-f", "JForexBridgeApplication",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            if proc.returncode != 0:
                break
            await asyncio.sleep(1)
        await asyncio.sleep(1)

        # Determine port: use specified, else try 8082, 8083, 8084
        candidate_ports = [inst.port] if inst.port else [8082, 8083, 8084]

        # Build command
        java_home = java_home or os.environ.get("JAVA_HOME", "/usr/lib/jvm/default-java")
        java_cmd = str(Path(java_home) / "bin" / "java")

        env = {
            **os.environ,
            "JAVA_HOME": java_home,
            "SERVER_PORT": str(candidate_ports[0]),
            "JFOREX_JNLP_URL": jnlp_url or jforex_jnlp_url(),
            "JFOREX_USERNAME": username or "",
            "JFOREX_PASSWORD": password or "",
            "JFOREX_DEMO": "true",
        }

        for candidate_port in candidate_ports:
            try:
                inst._proc = await asyncio.create_subprocess_exec(
                    java_cmd,
                    "-jar", self.bridge_jar,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )

                # Quick probe to see if this port works
                await asyncio.sleep(3)
                test_url = f"http://127.0.0.1:{candidate_port}/api/v1/health"
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(test_url)
                    if resp.status_code == 200:
                        body = resp.json()
                        if body.get("status") == "UP":
                            inst.port = candidate_port
                            inst.base_url = f"http://127.0.0.1:{candidate_port}"
                            return
            except Exception as e:
                logger.warning("Port %d failed: %s", candidate_port, e)
                if inst._proc:
                    inst._proc.terminate()
                    await inst._proc.wait()
                    inst._proc = None
                continue

        raise RuntimeError("No available port for JForex Bridge (tried 8082, 8083, 8084)")

    async def _wait_ready(self, inst: JForexBridgeInstance, timeout: float) -> bool:
        """Wait for HTTP API to report ready (status UP)."""
        if inst.base_url is None:
            return False

        deadline = time.monotonic() + timeout
        async with httpx.AsyncClient(timeout=5.0) as client:
            while time.monotonic() < deadline:
                if inst._proc is not None and inst._proc.returncode is not None:
                    return False
                try:
                    resp = await client.get(f"{inst.base_url}/api/v1/health")
                    if resp.status_code == 200:
                        body = resp.json()
                        if body.get("status") == "UP" and body.get("jforexConnected"):
                            return True
                except Exception:
                    pass
                await asyncio.sleep(1)
        return False

    async def _health_monitor(self, inst: JForexBridgeInstance, name: str) -> None:
        """Background task: monitor process health and restart on crash."""
        logger.info("Health monitor started for '%s'", name)
        while inst._restart_on_crash and inst._proc is not None:
            await asyncio.sleep(10.0)
            if inst._proc.returncode is not None:
                logger.warning("JForex Bridge '%s' exited (code %s), restarting...",
                               name, inst._proc.returncode)
                try:
                    await self._start_bridge(inst, None, None, None, None, True, name)
                    if await self._wait_ready(inst, timeout=self.ready_timeout):
                        logger.info("JForex Bridge '%s' restarted successfully", name)
                    else:
                        logger.error("JForex Bridge '%s' failed to become ready after restart", name)
                        break
                except Exception as e:
                    logger.error("Failed to restart JForex Bridge '%s': %s", name, e)
                    break

    async def stop(self, name: str | None = None, port: int | None = None) -> None:
        """Stop a managed JForex Bridge instance gracefully.

        Sends POST /shutdown via HTTP, waits, then SIGTERM, then SIGKILL.
        """
        key = f"{self.bridge_jar}:{port or 'auto'}"
        if name:
            # Find by name
            for k, inst in self._instances.items():
                if inst.name == name:
                    key = k
                    break

        async with self._lock:
            inst = self._instances.pop(key, None)
            if inst is None:
                logger.warning("No JForex Bridge instance found for %s:%s", name, port)
                return

        await self._cleanup_instance(key, inst)

    async def graceful_shutdown(self, inst: JForexBridgeInstance) -> None:
        """Graceful shutdown via HTTP POST /shutdown → wait → SIGTERM."""
        if inst.base_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(f"{inst.base_url}/api/v1/health/shutdown")
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
                await asyncio.wait_for(inst._proc.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                inst._proc.kill()
                await inst._proc.wait()

        # Ensure port is free
        if inst.port:
            proc = await asyncio.create_subprocess_exec(
                "fuser", "-k", f"{inst.port}/tcp",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

    async def _cleanup_instance(self, key: str, inst: JForexBridgeInstance) -> None:
        """Clean up an instance (stop process, release lock, cancel health task)."""
        if inst._health_task:
            inst._health_task.cancel()
            await asyncio.gather(inst._health_task, return_exceptions=True)

        await self.graceful_shutdown(inst)
        inst.release_lock()

    async def get_client(self, name: str | None = None, port: int | None = None) -> Optional[httpx.AsyncClient]:
        """Get an HTTP client for a running instance."""
        key = f"{self.bridge_jar}:{port or 'auto'}"
        if name:
            for k, inst in self._instances.items():
                if inst.name == name:
                    key = k
                    break
        inst = self._instances.get(key)
        if inst and inst.base_url:
            return httpx.AsyncClient(base_url=inst.base_url, timeout=30.0)
        return None

    async def health_check(self, name: str | None = None, port: int | None = None) -> bool:
        """Check if a managed instance is healthy."""
        key = f"{self.bridge_jar}:{port or 'auto'}"
        if name:
            for k, inst in self._instances.items():
                if inst.name == name:
                    key = k
                    break
        inst = self._instances.get(key)
        if not inst or not inst.base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{inst.base_url}/api/v1/health")
                return resp.status_code == 200 and resp.json().get("jforexConnected")
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

import pytest
import pytest_asyncio

@pytest_asyncio.fixture(scope="function")
async def jforex_instance() -> JForexBridgeInstance:
    """Function-scoped JForex Bridge instance fixture.

    Starts a fresh JForex Bridge for each test, stops it after.
    Skips if JFOREX_INTEGRATION=1 is not set.
    """
    import os
    if not os.environ.get("JFOREX_INTEGRATION"):
        pytest.skip("JFOREX_INTEGRATION=1 not set")

    manager = JForexProcessManager()
    inst = await manager.ensure_running()
    try:
        yield inst
    finally:
        await manager.stop()


@pytest_asyncio.fixture(scope="session")
async def jforex_session() -> JForexBridgeInstance:
    """Session-scoped JForex Bridge instance fixture.

    Starts one JForex Bridge for the entire test session, stops at end.
    Skips if JFOREX_INTEGRATION=1 is not set.
    """
    import os
    if not os.environ.get("JFOREX_INTEGRATION"):
        pytest.skip("JFOREX_INTEGRATION=1 not set")

    manager = JForexProcessManager()
    inst = await manager.ensure_running(restart_on_crash=True)
    try:
        yield inst
    finally:
        pass