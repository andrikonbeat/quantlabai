"""SQLite-backed cache with configurable TTL expiration."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from typing import Any


class SqliteCache:
    """Async SQLite cache with per-key TTL.

    Thread-safe via ``asyncio.Lock`` + ``asyncio.to_thread``. Uses an
    in-memory SQLite database when no ``db_path`` is given, making it
    suitable for both production and test environments.

    Schema::

        CREATE TABLE cache (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,      -- JSON-encoded
            expires_at REAL NOT NULL       -- Unix timestamp
        );

    Args:
        db_path: Path to the SQLite database file. ``:memory:`` by default.
        default_ttl: Default TTL in seconds (1 hour).
    """

    def __init__(self, db_path: str | None = None, default_ttl: int = 3600) -> None:
        self.db_path = db_path or ":memory:"
        self.default_ttl = default_ttl
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
                    "CREATE TABLE IF NOT EXISTS cache ("
                    "  key TEXT PRIMARY KEY,"
                    "  value TEXT NOT NULL,"
                    "  expires_at REAL NOT NULL"
                    ")"
                )
                conn.commit()
                return conn

            self._conn = await asyncio.to_thread(_init)
            return self._conn

    async def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve a cached value.

        Returns ``None`` when the key is missing or expired (expired
        entries are automatically deleted).
        """
        conn = await self._init_db()

        def _get() -> dict[str, Any] | None:
            cur = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            if row["expires_at"] < time.time():
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None
            return json.loads(row["value"])

        return await asyncio.to_thread(_get)

    async def set(
        self,
        key: str,
        value: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Store a value with an optional TTL override.

        If ``ttl`` is ``None``, ``default_ttl`` is used.
        """
        conn = await self._init_db()
        expires = time.time() + (ttl or self.default_ttl)
        encoded = json.dumps(value)

        def _set() -> None:
            conn.execute(
                "INSERT OR REPLACE INTO cache(key, value, expires_at) VALUES (?, ?, ?)",
                (key, encoded, expires),
            )
            conn.commit()

        await asyncio.to_thread(_set)

    async def clear(self) -> None:
        """Remove all cached entries."""
        conn = await self._init_db()

        def _clear() -> None:
            conn.execute("DELETE FROM cache")
            conn.commit()

        await asyncio.to_thread(_clear)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            conn = self._conn

            def _close() -> None:
                conn.close()

            await asyncio.to_thread(_close)
            self._conn = None
