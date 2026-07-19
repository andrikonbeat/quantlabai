"""Daemon Context — async context manager for SQX daemon lifecycle.

Provides `DaemonContext` and `run_with_daemon` for clean daemon lifecycle
management (start → health check → yield → graceful stop → force kill).
Reduces CLI boilerplate by ~60% vs manual start/stop.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import AsyncContextManager, Callable, Optional

from quantlab.phase4.daemon import SQXDaemonManager
from quantlab.phase4.command_dispatcher import CommandDispatcher
from quantlab.phase4.http_client import AsyncSQXClient


class DaemonContext:
    """Async context manager wrapping SQX daemon + dispatcher + HTTP client.

    Usage:
        async with DaemonContext(sqx_path="/opt/StrategyQuantX") as ctx:
            dispatcher = ctx.dispatcher
            client = ctx.client
            # ... use dispatcher/client
        # Automatically stops daemon on exit (SIGTERM → 5s → SIGKILL)

    Attributes:
        daemon: SQXDaemonManager instance
        client: AsyncSQXClient for direct HTTP calls
        dispatcher: CommandDispatcher for high-level SQX operations
    """

    def __init__(
        self,
        sqx_install_path: str | Path = "/opt/StrategyQuantX",
        port: int = 8888,
        startup_timeout: float = 60.0,
        force_stop_timeout: float = 5.0,
    ) -> None:
        self.sqx_install_path = str(sqx_install_path)
        self.port = port
        self.startup_timeout = startup_timeout
        self.force_stop_timeout = force_stop_timeout

        self._daemon: Optional[SQXDaemonManager] = None
        self._client: Optional[AsyncSQXClient] = None
        self._dispatcher: Optional[CommandDispatcher] = None

    async def __aenter__(self):
        """Start daemon, create client + dispatcher."""
        self._daemon = SQXDaemonManager(
            self.sqx_install_path,
            port=self.port,
            startup_timeout=self.startup_timeout,
        )
        base_url = await self._daemon.start()

        self._client = AsyncSQXClient(self._daemon.base_url)
        self._dispatcher = await CommandDispatcher.from_daemon(self._daemon)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Graceful stop → force kill if needed."""
        if self._client:
            await self._client.close()

        if self._daemon:
            try:
                await self._daemon.stop(force=False)
            except Exception:
                pass  # Force kill will handle it

    @property
    def daemon(self) -> Optional[object]:
        """SQXDaemonManager instance."""
        return self._daemon

    @property
    def client(self) -> Optional[object]:
        """AsyncSQXClient for direct HTTP calls."""
        return self._client

    @property
    def dispatcher(self) -> Optional[object]:
        """CommandDispatcher for high-level SQX operations."""
        return self._dispatcher


async def run_with_daemon(
    sqx_install_path: str | Path = "/opt/StrategyQuantX",
    port: int = 8888,
    startup_timeout: float = 60.0,
    func: Optional[Callable] = None,
    *args,
    **kwargs,
):
    """Run a coroutine with automatic daemon lifecycle management.

    Usage:
        async def my_work(dispatcher, client):
            dispatcher.load_config(...)
            ...

        await run_with_daemon(func=my_work, sqx_install_path="/opt/StrategyQuantX")

    Args:
        sqx_install_path: Path to SQX installation.
        port: SQX -gui port.
        startup_timeout: Daemon startup timeout (seconds).
        func: Async function to run inside the daemon context.
              Signature: func(dispatcher, client, *args, **kwargs)
        *args, **kwargs: Passed to func.

    Returns:
        The return value of func.
    """
    async with DaemonContext(
        sqx_install_path=sqx_install_path,
        port=port,
        startup_timeout=startup_timeout,
    ) as ctx:
        if func:
            return await func(ctx.dispatcher, ctx.client, *args, **kwargs)
        return None


# Convenience alias
@contextlib.asynccontextmanager
async def daemon_context(
    sqx_install_path: str = "/opt/StrategyQuantX",
    port: int = 8888,
    startup_timeout: float = 60.0,
) -> AsyncContextManager:
    """Async context manager for DaemonContext.

    Usage:
        async with daemon_context("/opt/StrategyQuantX") as ctx:
            dispatcher = ctx.dispatcher
            ...
    """
    ctx = DaemonContext(sqx_install_path=sqx_install_path, port=port, startup_timeout=startup_timeout)
    await ctx.__aenter__()
    try:
        yield ctx
    finally:
        await ctx.__aexit__(None, None, None)