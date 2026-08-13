"""DataManager — registry-based market data manager (REQ-12, REQ-13, REQ-04).

Rebuilt to the recovered ``.pyc`` contract: ``ensure_symbol``,
``update_data``, ``import_csv``, ``list_symbols``, ``get_symbol_info``.
Datasources are selected through a :class:`DatasourceRegistry`: the
launch path wraps the sqcli ``-symbol action=add`` and
``-data action=update`` commands with SQX naming (``EURUSD_M1_dukas``),
and ``datasource="jforex"`` (REQ-04) routes to :class:`JForexProvider`,
which reads history the local JForex4 platform already downloaded. The
manager records every ensured/updated symbol in a deterministic SQLite
registry (``SymbolRegistry``) so cache hits avoid re-running the source,
and is the component ``BuilderAgent._ensure_data`` consumes in
orchestrated mode (REQ-13 — replacing the temporary hard-raise).

Deferred datasources (D5: crypto, CSV, yahoo) raise ``NotSupportedError``
before any source is touched. Symbol names are validated (threat-matrix
boundary 1) so no metacharacter can reach the sqcli argv.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from quantlab.data.datasource_registry import DatasourceHandler, DatasourceRegistry
from quantlab.data.exceptions import DataManagerError, NotSupportedError
from quantlab.data.symbol_registry import SymbolRegistry, resolve_symbol
from quantlab.jforex.provider import JForexProvider

logger = logging.getLogger(__name__)


# ── sqcli discovery ─────────────────────────────────────────────────────────


def _find_sqcli(sqx_install_path: str) -> str | None:
    """Locate the ``sqcli`` binary inside an SQX installation directory.

    Args:
        sqx_install_path: Root of the SQX installation.

    Returns:
        The absolute sqcli path, or ``None`` when not found.
    """
    install = Path(sqx_install_path)
    candidates = [
        install / "sqcli",
        install / "sqcli.exe",
        install / "sqcli.sh",
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c.resolve())
    return None


async def _run_sqcli_command(sqcli_path: str, args: list[str], timeout: float = 60.0) -> str:
    """Run a single sqcli command and return its stdout.

    Args:
        sqcli_path: Absolute path to the sqcli binary.
        args: Command arguments (e.g. ``["-symbol", "action=add", ...]``).
        timeout: Max seconds before the process is killed (default 60).

    Returns:
        The captured stdout.

    Raises:
        DataManagerError: On non-zero exit or timeout.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            sqcli_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DataManagerError(
            f"failed to launch sqcli {sqcli_path!r}: {exc}"
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise DataManagerError(
            f"sqcli command timed out after {timeout:.0f}s: {args}"
        ) from None

    if proc.returncode != 0:
        detail = (stderr or stdout).decode(errors="replace").strip()
        raise DataManagerError(
            f"sqcli {' '.join(args)} failed (exit {proc.returncode}): {detail}"
        )
    return stdout.decode(errors="replace")


# ── DataManager ─────────────────────────────────────────────────────────────


class SqcliDukascopyHandler(DatasourceHandler):
    """Dukascopy datasource handler — the existing sqcli path (REQ-04 S2).

    Owns sqcli discovery and the exact ``-symbol action=add`` /
    ``-data action=update`` argv defined by the recovered ``.pyc``
    contract. Lives in this module so it shares the module-level
    ``_run_sqcli_command`` runner.
    """

    name = "dukascopy"

    def __init__(
        self,
        sqcli_path: str | None = None,
        sqx_install_path: str | None = None,
    ) -> None:
        self._sqcli_path = sqcli_path
        self._sqx_install_path = sqx_install_path

    def sqx_name(self, symbol: str, datatype: str) -> str:
        """Build ``EURUSD_M1_dukas`` with the shared validation."""
        return resolve_symbol(symbol, datatype, "dukascopy")

    async def ensure(self, symbol: str, datatype: str, sqx_name: str) -> None:
        sqcli = self._require_sqcli()
        await _run_sqcli_command(
            sqcli,
            [
                "-symbol",
                "action=add",
                f"name={sqx_name}",
                "datasource=dukascopy",
                f"datatype={datatype}",
            ],
        )

    async def update(self, symbol: str, datatype: str, sqx_name: str) -> None:
        sqcli = self._require_sqcli()
        await _run_sqcli_command(
            sqcli,
            ["-data", "action=update", f"name={sqx_name}"],
        )

    # ── sqcli resolution ────────────────────────────────────────────────

    def _locate_sqcli(self) -> str | None:
        """Resolve the sqcli binary from explicit config or env vars.

        Order: explicit ``sqcli_path`` → ``SQCLI_PATH`` env → explicit
        ``sqx_install_path`` → ``SQX_INSTALL_PATH`` env. No silent fallback
        to a bundled installation — the caller must configure the binary
        explicitly (fail-closed, REQ-13).
        """
        if self._sqcli_path:
            return self._sqcli_path

        env_binary = os.environ.get("SQCLI_PATH")
        if env_binary and os.path.isfile(env_binary) and os.access(env_binary, os.X_OK):
            return str(Path(env_binary).resolve())

        install = self._sqx_install_path or os.environ.get("SQX_INSTALL_PATH")
        if install:
            return _find_sqcli(install)
        return None

    def _require_sqcli(self) -> str:
        """Locate sqcli or raise — data operations cannot proceed without it."""
        sqcli = self._locate_sqcli()
        if sqcli is None:
            raise DataManagerError(
                "sqcli not found: set SQCLI_PATH or SQX_INSTALL_PATH, "
                "or pass sqcli_path/sqx_install_path to DataManager"
            )
        return sqcli


class DataManager:
    """Registry-based data manager with a deterministic SQLite cache.

    Args:
        sqx_install_path: Optional SQX installation root used to discover
            the sqcli binary. When ``None``, discovery falls back to the
            ``SQX_INSTALL_PATH`` env var, then ``SQCLI_PATH``.
        sqcli_path: Optional explicit sqcli binary path (highest priority).
        registry: Optional injected ``SymbolRegistry`` (tests).
        registry_path: Path for the registry database (default in-memory).
        datasources: Optional injected :class:`DatasourceRegistry` (tests).
            Defaults to dukascopy/sqcli + jforex (REQ-04).
        jforex_state_dir: JForex4 local state directory consumed by the
            default ``jforex`` datasource handler.
    """

    def __init__(
        self,
        sqx_install_path: str | None = None,
        sqcli_path: str | None = None,
        registry: SymbolRegistry | None = None,
        registry_path: str | None = None,
        datasources: DatasourceRegistry | None = None,
        jforex_state_dir: str | None = None,
    ) -> None:
        self._datasources = datasources or self._default_datasources(
            sqcli_path=sqcli_path,
            sqx_install_path=sqx_install_path,
            jforex_state_dir=jforex_state_dir,
        )
        self._registry = registry or SymbolRegistry(db_path=registry_path)

    @staticmethod
    def _default_datasources(
        sqcli_path: str | None,
        sqx_install_path: str | None,
        jforex_state_dir: str | None,
    ) -> DatasourceRegistry:
        """Build the default registry: dukascopy/sqcli + jforex (REQ-04)."""
        reg = DatasourceRegistry()
        reg.register(
            SqcliDukascopyHandler(
                sqcli_path=sqcli_path, sqx_install_path=sqx_install_path
            )
        )
        reg.register(JForexProvider(state_dir=jforex_state_dir))
        return reg

    @property
    def registry(self) -> SymbolRegistry:
        """The symbol registry backing this manager."""
        return self._registry

    @property
    def datasources(self) -> DatasourceRegistry:
        """The datasource registry this manager routes through."""
        return self._datasources

    # ── Datasource routing ───────────────────────────────────────────────

    def _handler_for(self, datasource: str) -> DatasourceHandler:
        """Look up a datasource handler, rejecting unregistered sources."""
        handler = self._datasources.get(datasource)
        if handler is None:
            raise NotSupportedError(
                f"datasource '{datasource}' is not supported at launch — "
                f"registered: {self._datasources.names()!r} "
                "(D5: crypto/CSV/yahoo deferred)"
            )
        return handler

    # ── .pyc contract API (REQ-12) ──────────────────────────────────────

    async def ensure_symbol(
        self,
        symbol: str,
        datasource: str = "dukascopy",
        datatype: str = "M1",
    ) -> dict[str, Any]:
        """Register a symbol via its datasource handler and record it.

        Cache-first: when the symbol+timeframe+datasource is already
        registered with status ``ok``, no datasource operation runs
        (deterministic cache, no re-download).

        Args:
            symbol: Base symbol (e.g. ``EURUSD``).
            datasource: Data source — ``dukascopy`` (sqcli) or ``jforex``
                (local JForex state, REQ-04).
            datatype: FX timeframe (``M1``/``M5``/``H1``).

        Returns:
            Dict with ``status``, ``sqx_name``, ``symbol``, ``timeframe``,
            ``datasource``, and ``cached``.

        Raises:
            NotSupportedError: Unregistered/unknown datasource (D5).
            ValueError: Invalid symbol (boundary 1).
            DataManagerError: The datasource handler failed (missing
                sqcli, missing JForex state, command error, timeout).
        """
        handler = self._handler_for(datasource)

        sqx_name = handler.sqx_name(symbol, datatype)

        existing = await self._registry.get(symbol, datatype, datasource=datasource)
        if existing is not None and existing.get("status") == "ok":
            return {
                "status": "ok",
                "cached": True,
                "symbol": symbol,
                "timeframe": datatype,
                "datasource": datasource,
                "sqx_name": sqx_name,
            }

        await handler.ensure(symbol, datatype, sqx_name)
        await self._registry.record(
            sqx_name, symbol, datatype, datasource, status="ok"
        )
        logger.info("DataManager: ensured symbol '%s' via '%s'", sqx_name, datasource)
        return {
            "status": "ok",
            "cached": False,
            "symbol": symbol,
            "timeframe": datatype,
            "datasource": datasource,
            "sqx_name": sqx_name,
        }

    async def update_data(
        self,
        symbol: str,
        datasource: str = "dukascopy",
        datatype: str = "M1",
    ) -> dict[str, Any]:
        """Refresh market data via the datasource handler.

        Args:
            symbol: Base symbol (e.g. ``EURUSD``).
            datasource: Data source — ``dukascopy`` (sqcli) or ``jforex``
                (local JForex state, REQ-04).
            datatype: FX timeframe (``M1``/``M5``/``H1``).

        Returns:
            Dict with ``status``, ``action``, ``sqx_name``, ``symbol``.

        Raises:
            NotSupportedError: Unregistered/unknown datasource (D5).
            ValueError: Invalid symbol (boundary 1).
            DataManagerError: The datasource handler failed.
        """
        handler = self._handler_for(datasource)

        sqx_name = handler.sqx_name(symbol, datatype)
        await handler.update(symbol, datatype, sqx_name)
        await self._registry.record(
            sqx_name, symbol, datatype, datasource, status="ok"
        )
        return {
            "status": "ok",
            "action": "update",
            "symbol": symbol,
            "timeframe": datatype,
            "datasource": datasource,
            "sqx_name": sqx_name,
        }

    async def import_csv(
        self,
        symbol: str,
        csv_path: str,
        datasource: str = "CSV",
        datatype: str = "M1",
    ) -> dict[str, Any]:
        """Import data from a CSV file — deferred at launch (D5).

        The method exists for the recovered ``.pyc`` contract, but the CSV
        datasource is explicitly out of scope at launch and raises.

        Raises:
            NotSupportedError: Always — CSV datasource deferred (D5).
        """
        raise NotSupportedError(
            f"CSV datasource is deferred (D5) — use 'dukascopy' or 'jforex' "
            f"(symbol={symbol!r})"
        )

    async def list_symbols(self) -> list[dict[str, Any]]:
        """Return every symbol registered in the SQLite registry (REQ-12)."""
        return await self._registry.list_all()

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """Return the most recent registry entry for a symbol.

        Args:
            symbol: Base symbol (e.g. ``EURUSD``).

        Returns:
            The registry row, or ``{"symbol": ..., "status": "unknown"}``
            when the symbol has never been ensured.
        """
        info = await self._registry.get(symbol)
        if info is None:
            return {"symbol": symbol, "status": "unknown"}
        return info
