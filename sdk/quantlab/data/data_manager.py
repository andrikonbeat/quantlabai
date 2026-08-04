"""DataManager — Dukascopy-only market data manager (REQ-12, REQ-13, D5).

Rebuilt to the recovered ``.pyc`` contract: ``ensure_symbol``,
``update_data``, ``import_csv``, ``list_symbols``, ``get_symbol_info``.
The manager wraps the sqcli ``-symbol action=add`` and
``-data action=update`` commands with SQX naming (``EURUSD_M1_dukas``),
records every ensured/updated symbol in a deterministic SQLite registry
(``SymbolRegistry``) so cache hits avoid re-downloading, and is the
component ``BuilderAgent._ensure_data`` consumes in orchestrated mode
(REQ-13 — replacing the temporary hard-raise).

Launch scope is Dukascopy-only (D5): crypto, CSV, and yahoo datasources
raise ``NotSupportedError`` before any command is built. Symbol names are
validated (threat-matrix boundary 1) so no metacharacter can reach the
sqcli argv.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from quantlab.data.exceptions import DataManagerError, NotSupportedError
from quantlab.data.symbol_registry import SymbolRegistry, resolve_symbol

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


class DataManager:
    """Dukascopy-only data manager with a deterministic SQLite cache.

    Args:
        sqx_install_path: Optional SQX installation root used to discover
            the sqcli binary. When ``None``, discovery falls back to the
            ``SQX_INSTALL_PATH`` env var, then ``SQCLI_PATH``.
        sqcli_path: Optional explicit sqcli binary path (highest priority).
        registry: Optional injected ``SymbolRegistry`` (tests).
        registry_path: Path for the registry database (default in-memory).
    """

    def __init__(
        self,
        sqx_install_path: str | None = None,
        sqcli_path: str | None = None,
        registry: SymbolRegistry | None = None,
        registry_path: str | None = None,
    ) -> None:
        self._sqx_install_path = sqx_install_path
        self._sqcli_path = sqcli_path
        self._registry = registry or SymbolRegistry(db_path=registry_path)

    @property
    def registry(self) -> SymbolRegistry:
        """The symbol registry backing this manager."""
        return self._registry

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

    # ── .pyc contract API (REQ-12) ──────────────────────────────────────

    async def ensure_symbol(
        self,
        symbol: str,
        datasource: str = "dukascopy",
        datatype: str = "M1",
    ) -> dict[str, Any]:
        """Register a symbol via ``-symbol action=add`` and record it.

        Cache-first: when the symbol+timeframe is already registered with
        status ``ok``, no sqcli command runs (deterministic cache, no
        re-download).

        Args:
            symbol: Base symbol (e.g. ``EURUSD``).
            datasource: Data source — only ``dukascopy`` at launch (D5).
            datatype: FX timeframe (``M1``/``M5``/``H1``).

        Returns:
            Dict with ``status``, ``sqx_name``, ``symbol``, ``timeframe``,
            ``datasource``, and ``cached``.

        Raises:
            NotSupportedError: Deferred datasource (D5).
            ValueError: Invalid symbol (boundary 1).
            DataManagerError: sqcli missing or the command failed.
        """
        sqx_name = resolve_symbol(symbol, datatype, datasource)

        existing = await self._registry.get(symbol, datatype)
        if existing is not None and existing.get("status") == "ok":
            return {
                "status": "ok",
                "cached": True,
                "symbol": symbol,
                "timeframe": datatype,
                "datasource": datasource,
                "sqx_name": sqx_name,
            }

        sqcli = self._require_sqcli()
        await _run_sqcli_command(
            sqcli,
            [
                "-symbol",
                "action=add",
                f"name={sqx_name}",
                f"datasource={datasource}",
                f"datatype={datatype}",
            ],
        )
        await self._registry.record(
            sqx_name, symbol, datatype, datasource, status="ok"
        )
        logger.info("DataManager: ensured symbol '%s' via sqcli", sqx_name)
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
        """Refresh market data via ``-data action=update`` (SQX download).

        Args:
            symbol: Base symbol (e.g. ``EURUSD``).
            datasource: Data source — only ``dukascopy`` at launch (D5).
            datatype: FX timeframe (``M1``/``M5``/``H1``).

        Returns:
            Dict with ``status``, ``action``, ``sqx_name``, ``symbol``.

        Raises:
            NotSupportedError: Deferred datasource (D5).
            ValueError: Invalid symbol (boundary 1).
            DataManagerError: sqcli missing or the command failed.
        """
        sqx_name = resolve_symbol(symbol, datatype, datasource)
        sqcli = self._require_sqcli()
        await _run_sqcli_command(
            sqcli,
            ["-data", "action=update", f"name={sqx_name}"],
        )
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
            f"CSV datasource is deferred (D5) — only 'dukascopy' is "
            f"supported at launch (symbol={symbol!r})"
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
