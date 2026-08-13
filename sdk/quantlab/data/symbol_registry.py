"""Symbol registry + SQX naming helpers (REQ-12, D5).

Rebuilt to the recovered ``.pyc`` contract: SQX symbols are named
``{SYMBOL}_{TIMEFRAME}_dukas`` for Dukascopy data (matching the naming
already used by ``project_builder``). The SQLite registry persists which
symbols have been ensured/updated so the DataManager can serve cache hits
without re-downloading.

Only the Dukascopy datasource is supported at launch (D5). Any other
datasource raises ``NotSupportedError``; symbol names are validated against
``^[A-Z]{6}(_[A-Z]+\\d*)?$`` and shell metacharacters are rejected
(threat-matrix boundary 1) before any sqcli command is constructed.
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
import time
from typing import Any

from quantlab.data.exceptions import NotSupportedError

# ── Symbol validation (threat-matrix boundary 1) ────────────────────────────

# Exactly 6 uppercase letters, optionally followed by an uppercase suffix
# (with optional digits), e.g. EURUSD, GBPJPY, XAUUSD, EURUSD_CONT.
_SYMBOL_RE = re.compile(r"^[A-Z]{6}(_[A-Z]+\d*)?$")

# Datasource → SQX name suffix. Dukascopy is abbreviated "dukas" per the
# recovered .pyc contract and project_builder naming; JForex uses its own
# name (REQ-04). Launch scope is dukascopy + jforex (D5); future
# datasources map here when added.
_DATASOURCE_SUFFIX: dict[str, str] = {
    "dukascopy": "dukas",
    "jforex": "jforex",
}
_SUFFIX_DATASOURCE: dict[str, str] = {
    suffix: name for name, suffix in _DATASOURCE_SUFFIX.items()
}

_U_SYMBOL_RE = re.compile(
    r"^(?P<symbol>[A-Z]{6}(?:_[A-Z]+\d*)?)_"
    r"(?P<timeframe>[A-Z]+\d*)_(?P<suffix>[a-z]+)$"
)


def resolve_symbol(symbol: str, timeframe: str = "M1", datasource: str = "dukascopy") -> str:
    """Build the SQX symbol name (``EURUSD_M1_dukas``).

    Validates the datasource (D5 — only Dukascopy) and the symbol name
    (boundary 1 regex) before constructing the name.

    Args:
        symbol: Base symbol, e.g. ``EURUSD``.
        timeframe: FX timeframe, e.g. ``M1``/``M5``/``H1`` (launch scope).
        datasource: Data source — ``dukascopy`` (sqcli) or ``jforex``
            (local JForex state, REQ-04).

    Returns:
        The SQX symbol name, e.g. ``EURUSD_M1_dukas`` or
        ``EURUSD_M1_jforex``.

    Raises:
        NotSupportedError: The datasource is not supported at launch (D5).
        ValueError: The symbol fails the boundary-1 validation.
    """
    if datasource not in _DATASOURCE_SUFFIX:
        supported = ", ".join(sorted(_DATASOURCE_SUFFIX))
        raise NotSupportedError(
            f"datasource '{datasource}' is not supported at launch — "
            f"only {supported} (D5: crypto/CSV/yahoo deferred)"
        )
    if not _SYMBOL_RE.match(symbol):
        raise ValueError(
            f"invalid symbol {symbol!r}: expected ^[A-Z]{{6}}(_[A-Z]+\\d*)?$ "
            "(e.g. EURUSD, GBPJPY, EURUSD_CONT)"
        )
    suffix = _DATASOURCE_SUFFIX[datasource]
    return f"{symbol}_{timeframe.upper()}_{suffix}"


def u_symbol(sqx_name: str) -> dict[str, str]:
    """Reverse ``resolve_symbol``: parse an SQX name back into parts.

    Args:
        sqx_name: SQX symbol name, e.g. ``EURUSD_M1_dukas``.

    Returns:
        A dict with ``symbol``, ``timeframe``, and ``datasource``.

    Raises:
        ValueError: The name is not a valid SQX symbol name.
    """
    m = _U_SYMBOL_RE.match(sqx_name)
    if m is None:
        raise ValueError(f"invalid SQX symbol name {sqx_name!r}")
    suffix = m.group("suffix")
    datasource = _SUFFIX_DATASOURCE.get(suffix)
    if datasource is None:
        raise ValueError(
            f"unknown datasource suffix '_dukas' in {sqx_name!r}"
        )
    return {
        "symbol": m.group("symbol"),
        "timeframe": m.group("timeframe"),
        "datasource": datasource,
    }


# ── SQLite registry ─────────────────────────────────────────────────────────


class SymbolRegistry:
    """SQLite-backed registry of ensured/updated symbols (REQ-12).

    Thread-safe via ``asyncio.Lock`` + ``asyncio.to_thread`` (same pattern
    as ``quantlab.data.fundamental.cache.SqliteCache``). Uses an in-memory
    database when no ``db_path`` is given.

    Schema::

        CREATE TABLE symbols (
            sqx_name   TEXT PRIMARY KEY,
            symbol     TEXT NOT NULL,
            timeframe  TEXT NOT NULL,
            datasource TEXT NOT NULL,
            status     TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

    Args:
        db_path: Path to the SQLite database file. ``:memory:`` by default.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or ":memory:"
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()

    async def _init_db(self) -> sqlite3.Connection:
        """Ensure the database and table exist, return the connection."""
        async with self._lock:
            if self._conn is not None:
                return self._conn

            def _init() -> sqlite3.Connection:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS symbols ("
                    "  sqx_name TEXT PRIMARY KEY,"
                    "  symbol TEXT NOT NULL,"
                    "  timeframe TEXT NOT NULL,"
                    "  datasource TEXT NOT NULL,"
                    "  status TEXT NOT NULL,"
                    "  updated_at REAL NOT NULL"
                    ")"
                )
                conn.commit()
                return conn

            self._conn = await asyncio.to_thread(_init)
            return self._conn

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sqx_name": row["sqx_name"],
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "datasource": row["datasource"],
            "status": row["status"],
            "updated_at": row["updated_at"],
        }

    async def record(
        self,
        sqx_name: str,
        symbol: str,
        timeframe: str,
        datasource: str,
        status: str = "ok",
    ) -> dict[str, Any]:
        """Insert or replace the symbol row (update-in-place semantics).

        Args:
            sqx_name: SQX symbol name (primary key).
            symbol: Base symbol.
            timeframe: FX timeframe.
            datasource: Data source.
            status: Registry status, ``ok`` by default.

        Returns:
            The stored row as a dict.
        """
        conn = await self._init_db()
        now = time.time()

        def _record() -> None:
            conn.execute(
                "INSERT OR REPLACE INTO symbols("
                " sqx_name, symbol, timeframe, datasource, status, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (sqx_name, symbol, timeframe, datasource, status, now),
            )
            conn.commit()

        await asyncio.to_thread(_record)
        return {
            "sqx_name": sqx_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "datasource": datasource,
            "status": status,
            "updated_at": now,
        }

    async def get(
        self,
        symbol: str,
        timeframe: str | None = None,
        datasource: str | None = None,
    ) -> dict[str, Any] | None:
        """Return the most recent row for a symbol (optionally filtered).

        Args:
            symbol: Base symbol.
            timeframe: Optional timeframe filter (e.g. ``M1``).
            datasource: Optional datasource filter (e.g. ``jforex``) so
                multi-datasource managers can key their cache per source
                (REQ-04).
        """
        conn = await self._init_db()

        def _get() -> dict[str, Any] | None:
            clauses = ["symbol = ?"]
            params: list[Any] = [symbol]
            if timeframe is not None:
                clauses.append("timeframe = ?")
                params.append(timeframe)
            if datasource is not None:
                clauses.append("datasource = ?")
                params.append(datasource)
            cur = conn.execute(
                "SELECT * FROM symbols WHERE "
                + " AND ".join(clauses)
                + " ORDER BY updated_at DESC LIMIT 1",
                tuple(params),
            )
            row = cur.fetchone()
            return self._row_to_dict(row) if row is not None else None

        return await asyncio.to_thread(_get)

    async def has(self, symbol: str, timeframe: str | None = None) -> bool:
        """Return True when a symbol row exists (optionally per-timeframe)."""
        conn = await self._init_db()

        def _has() -> bool:
            if timeframe is None:
                cur = conn.execute(
                    "SELECT 1 FROM symbols WHERE symbol = ? LIMIT 1", (symbol,)
                )
            else:
                cur = conn.execute(
                    "SELECT 1 FROM symbols WHERE symbol = ? AND timeframe = ? LIMIT 1",
                    (symbol, timeframe),
                )
            return cur.fetchone() is not None

        return await asyncio.to_thread(_has)

    async def list_all(self) -> list[dict[str, Any]]:
        """Return every symbol row, most recently updated first."""
        conn = await self._init_db()

        def _list() -> list[dict[str, Any]]:
            cur = conn.execute(
                "SELECT * FROM symbols ORDER BY updated_at DESC"
            )
            return [self._row_to_dict(r) for r in cur.fetchall()]

        return await asyncio.to_thread(_list)

    async def close(self) -> None:
        """Close the underlying database connection, if open."""
        if self._conn is not None:
            conn = self._conn

            def _close() -> None:
                conn.close()

            await asyncio.to_thread(_close)
            self._conn = None
