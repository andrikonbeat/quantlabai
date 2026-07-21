"""Phase 4 — SQX Daemon Manager for CLI-based HTTP API lifecycle.

The SQX ``sqcli`` binary starts an HTTP server that accepts commands via
``/call?cmd=<command>``.  It runs in command-line mode (no GUI) and
auto-exits after completing all tasks.  For long-running projects the
daemon stays alive until the project finishes.

Lifecycle::

    start → wait for HTTP API → send commands → auto-exit → restart
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx

from quantlab.phase4.errors import SQXDaemonStartError, SQXBindingError
from quantlab.phase4.http_client import AsyncSQXClient, DEFAULT_PORT


class SQXDaemonManager:
    """Manages SQX CLI-based HTTP server lifecycle.

    Features:
    - Enforces 127.0.0.1 binding only (security)
    - Auto-starts sqcli -port=X on demand (without ``-gui`` flag)
    - Health check polling via ``/call?cmd=-h`` until API is ready
    - Graceful shutdown (SIGTERM → SIGKILL)
    - Restart on crash (configurable max retries)

    The ``-gui`` flag is intentionally NOT used — it disables all CLI
    commands in the HTTP API (confirmed on SQX v144.2953).
    """

    def __init__(
        self,
        sqx_install_path: str,
        *,
        port: int = DEFAULT_PORT,
        bind_address: str = "127.0.0.1",
        startup_timeout: float = 60.0,
        max_restarts: int = 3,
        restart_delay: float = 2.0,
    ):
        self.sqx_install_path = Path(sqx_install_path).resolve()
        self.port = port
        self.bind_address = bind_address
        self.startup_timeout = startup_timeout
        self.max_restarts = max_restarts
        self.restart_delay = restart_delay
        self._monitor_interval = 5.0

        self._process: Optional[subprocess.Popen] = None
        self._restart_count = 0
        self._monitor_task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._is_restarting = False

        _localhost_aliases = {"127.0.0.1", "::1", "localhost"}
        if bind_address not in _localhost_aliases:
            raise SQXBindingError(bind_address)

    @property
    def base_url(self) -> str:
        return f"http://{self.bind_address}:{self.port}"

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _read_port_from_settings(self) -> int:
        """Read the HTTP API port from ``internal/AppSettings.txt``.

        Falls back to ``DEFAULT_PORT`` (5050) if the file is missing
        or the setting is not found.
        """
        settings_path = self.sqx_install_path / "internal" / "AppSettings.txt"
        try:
            text = settings_path.read_text()
            import re
            m = re.search(
                r"<AppWebServerPortSQUANT>\s*(\d+)\s*</AppWebServerPortSQUANT>",
                text,
            )
            if m:
                return int(m.group(1))
        except (FileNotFoundError, OSError, ValueError):
            pass
        return DEFAULT_PORT

    async def start(self) -> str:
        """Start SQX daemon (no GUI) and wait for HTTP API readiness.

        The daemon runs ``sqcli`` (without ``-gui``, ``-port``, or
        ``-bind``) so the CLI command-based HTTP API is fully functional.
        The port is read from ``AppSettings.txt`` (default 5050).

        NOTE: ``-port=X`` and ``-bind=Y`` flags only work with ``-gui``.
        Without ``-gui``, SQX always uses the port from its configuration
        file (AppSettings.txt → AppWebServerPortSQUANT).  We ignore the
        configured *port* and always use the config-file value.

        Returns:
            Base URL for AsyncSQXClient (e.g. ``http://127.0.0.1:5050``)

        Raises:
            SQXDaemonStartError: If daemon fails to start or readiness
                check times out.
        """
        if self.is_running:
            return self.base_url

        sqcli = self.sqx_install_path / "sqcli"
        if not sqcli.exists():
            raise SQXDaemonStartError(f"sqcli not found at {sqcli}")

        # Read actual port from AppSettings.txt — -port flag only works with -gui
        actual_port = self._read_port_from_settings()
        if actual_port != self.port:
            self.port = actual_port

        # Build command — intentionally WITHOUT -gui (disables CLI commands)
        # Also without -port/-bind (they are unrecognized without -gui)
        cmd = [str(sqcli)]

        env = os.environ.copy()

        self._process = subprocess.Popen(
            cmd,
            cwd=self.sqx_install_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        # Wait for HTTP API readiness via /call?cmd=-h
        start_time = time.time()
        ready = False

        async with httpx.AsyncClient(timeout=5.0) as client:
            while time.time() - start_time < self.startup_timeout:
                if not self.is_running:
                    stdout, _ = self._process.communicate(timeout=1)
                    raise SQXDaemonStartError(
                        f"SQX process exited early (code {self._process.returncode}). "
                        f"stdout: {(stdout or b'').decode(errors='replace')}"
                    )

                try:
                    resp = await client.get(
                        f"{self.base_url}/call?cmd=-h",
                        timeout=5.0,
                    )
                    body = resp.text
                    if "Usage" in body and "not ready" not in body.lower():
                        ready = True
                        break
                except Exception:
                    pass

                # Read stdout to detect readiness or errors
                await asyncio.sleep(1.0)

        if not ready:
            await self._kill_process()
            raise SQXDaemonStartError(
                f"SQX HTTP API not ready after {self.startup_timeout}s. "
                f"Check that port {self.port} is free and SQX license is valid."
            )

        # Cancel existing monitor task (unless restarting)
        if not self._is_restarting:
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass

        self._restart_count = 0
        self._monitor_task = asyncio.create_task(self._monitor())

        return self.base_url

    async def _monitor(self) -> None:
        """Monitor process health and restart on crash."""
        while True:
            await asyncio.sleep(self._monitor_interval)
            if not self.is_running:
                if self._restart_count < self.max_restarts:
                    self._restart_count += 1
                    await asyncio.sleep(self.restart_delay)
                    try:
                        self._is_restarting = True
                        await self.start()
                    except Exception:
                        pass
                    finally:
                        self._is_restarting = False
                else:
                    break

    async def stop(self, force: bool = False) -> None:
        """Stop the daemon gracefully.

        Args:
            force: If True, use SIGKILL immediately
        """
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        await self._kill_process(force=force)

    async def _kill_process(self, force: bool = False) -> None:
        if self._process and self._process.poll() is None:
            if force:
                self._process.kill()
            else:
                self._process.terminate()
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(self._process.wait),
                        timeout=10.0,
                    )
                except asyncio.TimeoutError:
                    self._process.kill()
                    await asyncio.to_thread(self._process.wait)

    async def get_client(self) -> AsyncSQXClient:
        """Get an AsyncSQXClient for this daemon."""
        return AsyncSQXClient(self.base_url)

    async def health_check(self) -> bool:
        """Quick health check via ``/call?cmd=-h``.

        First verifies the process is alive, then checks the HTTP API.
        """
        if not self.is_running:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/call?cmd=-h",
                    timeout=5.0,
                )
                return resp.status_code == 200 and "Usage" in resp.text
        except Exception:
            return False

    async def __aenter__(self) -> "SQXDaemonManager":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.stop()
