"""SQX -gui Daemon Manager.

Manages the SQX -gui server lifecycle with:
- Localhost-only binding enforcement
- Startup health check validation
- Auto-restart on crash
- SIGTERM/SIGKILL graceful shutdown
"""

from __future__ import annotations

import asyncio
import signal
import time
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from quantlab.phase4.errors import SQXBindingError
from quantlab.tools.exceptions import SQXNotFoundError, TimeoutError
from quantlab.tools.platform import resolve_sqcli_path


class DaemonManagerConfig(BaseModel):
    """Configuration for SQX -gui daemon manager."""

    sqx_install_path: Path
    bind_address: str = "127.0.0.1"
    gui_port: int = 8888
    startup_timeout: float = 30.0
    health_check_interval: float = 2.0
    auto_restart: bool = True
    sqcli_path: Path | None = None


class DaemonManager:
    """Manages SQX -gui server subprocess lifecycle.

    Security-critical: Enforces localhost-only binding to prevent
    network exposure of SQX HTTP API (strategy source code, portfolio data).

    Usage:
        config = DaemonManagerConfig(sqx_install_path="/opt/SQX")
        daemon = DaemonManager(config)
        await daemon.start()
        try:
            # Use SQX HTTP API
            ...
        finally:
            await daemon.stop()
    """

    def __init__(self, config: DaemonManagerConfig) -> None:
        self._config = config
        self._process: Optional[asyncio.subprocess.Process] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._started_at: float = 0.0
        self._restart_count = 0

    @property
    def config(self) -> DaemonManagerConfig:
        return self._config

    @property
    def base_url(self) -> str:
        return f"http://{self._config.bind_address}:{self._config.gui_port}"

    @property
    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.returncode is None
        )

    @property
    def process_id(self) -> int | None:
        return self._process.pid if self._process else None

    async def start(self) -> None:
        """Start the SQX -gui server.

        Raises:
            SQXNotFoundError: If sqcli binary not found.
            SQXBindingError: If server binds to non-localhost interface.
            TimeoutError: If server fails to start within startup_timeout.
        """
        if self.is_running:
            return

        # Resolve sqcli path
        sqcli = resolve_sqcli_path(self._config.sqcli_path)
        if sqcli is None:
            raise SQXNotFoundError(
                f"SQX CLI not found at {self._config.sqcli_path or 'default locations'}"
            )

        # Build command: sqcli -gui --host <bind_address> --port <port>
        cmd = [
            str(sqcli),
            "-gui",
            "--host",
            self._config.bind_address,
            "--port",
            str(self._config.gui_port),
        ]

        # Set working directory to SQX install path
        cwd = self._config.sqx_install_path

        # Start subprocess
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started_at = time.monotonic()

        # Wait for health check
        await self._wait_for_healthy()

        # Verify binding address
        await self._verify_binding()

        # Start background health monitor
        if self._config.auto_restart:
            self._health_check_task = asyncio.create_task(self._health_monitor())

    async def _wait_for_healthy(self) -> None:
        """Wait for HTTP health endpoint to respond."""
        deadline = time.monotonic() + self._config.startup_timeout
        interval = self._config.health_check_interval

        async with httpx.AsyncClient(timeout=5.0) as client:
            while time.monotonic() < deadline:
                if self._process and self._process.returncode is not None:
                    # Process died
                    stderr = await self._process.stderr.read() if self._process.stderr else b""
                    raise TimeoutError(
                        f"SQX -gui process exited prematurely (code {self._process.returncode}): "
                        f"{stderr.decode(errors='ignore')}"
                    )

                try:
                    # Try health endpoint first, fallback to root
                    for path in ("/health", "/"):
                        try:
                            resp = await client.get(f"{self.base_url}{path}")
                            if resp.status_code == 200:
                                return  # Healthy
                        except (httpx.ConnectError, httpx.TimeoutException):
                            continue
                except Exception:
                    pass

                await asyncio.sleep(interval)

        # Timeout
        await self.stop()  # Cleanup
        raise TimeoutError(
            f"SQX -gui failed to become healthy within {self._config.startup_timeout}s"
        )

    async def _verify_binding(self) -> None:
        """Verify server is bound only to localhost.

        Raises:
            SQXBindingError: If server responds on 0.0.0.0 or unexpected interface.
        """
        # If bind_address is localhost, verify it doesn't also respond on 0.0.0.0
        if self._config.bind_address in ("127.0.0.1", "localhost"):
            test_addresses = ["0.0.0.0", "0.0.0.0"]

            async with httpx.AsyncClient(timeout=2.0) as client:
                for addr in test_addresses:
                    test_url = f"http://{addr}:{self._config.gui_port}"
                    try:
                        resp = await client.get(f"{test_url}/health")
                        if resp.status_code == 200:
                            raise SQXBindingError(
                                f"SQX -gui bound to non-localhost address: {addr}:{self._config.gui_port}. "
                                f"This exposes the HTTP API to the network!",
                                bind_address=addr,
                                expected_address=self._config.bind_address,
                            )
                    except (httpx.ConnectError, httpx.TimeoutException):
                        # Good — not accessible on this interface
                        pass
                    except SQXBindingError:
                        raise
                    except Exception:
                        pass

    async def _health_monitor(self) -> None:
        """Background task to monitor daemon health and auto-restart."""
        while self.is_running:
            await asyncio.sleep(self._config.health_check_interval)

            if not self.is_running:
                break

            healthy = await self.health_check()
            if not healthy and self._config.auto_restart:
                await self.restart()

    async def health_check(self) -> bool:
        """Check if SQX -gui server is responding.

        Returns:
            True if healthy, False otherwise.
        """
        if not self.is_running:
            return False

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                for path in ("/health", "/"):
                    try:
                        resp = await client.get(f"{self.base_url}{path}")
                        if resp.status_code == 200:
                            return True
                    except (httpx.ConnectError, httpx.TimeoutException):
                        continue
        except Exception:
            pass

        return False

    async def stop(self) -> None:
        """Stop the SQX -gui server gracefully.

        Sends SIGTERM, waits 5s, then SIGKILL if needed.
        """
        # Cancel health monitor
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        if not self._process:
            return

        # SIGTERM
        try:
            self._process.terminate()
        except ProcessLookupError:
            pass

        # Wait for graceful exit
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Force kill
            try:
                self._process.kill()
                await self._process.wait()
            except ProcessLookupError:
                pass

        self._process = None

    async def restart(self) -> None:
        """Restart the daemon (stop + start)."""
        await self.stop()
        self._restart_count += 1
        await self.start()

    async def __aenter__(self) -> DaemonManager:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    def __del__(self) -> None:
        # Best-effort cleanup
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
            except Exception:
                pass