"""JForex4 historical data provider for the DataManager (REQ-04).

Reads OHLCV history that the local JForex4 platform has already
downloaded from the local state directory, so ``datasource="jforex"``
works without sqcli. Fail-closed: when JForex state is missing or a
symbol has no history file, ``ensure``/``update`` raise instead of
silently pretending the data exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantlab.data.datasource_registry import DatasourceHandler
from quantlab.data.exceptions import DataManagerError
from quantlab.data.market.models import Bar
from quantlab.data.symbol_registry import resolve_symbol


class JForexProvider(DatasourceHandler):
    """Historical-data handler backed by the local JForex4 state directory.

    History files live at ``{state_dir}/history/{SQX_NAME}.json`` as a
    JSON array of OHLCV rows with keys ``timestamp``, ``open``, ``high``,
    ``low``, ``close``, ``volume``.

    Attributes:
        state_dir: JForex4 local state directory (root of ``history/``).
    """

    name = "jforex"

    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = Path(state_dir) if state_dir else None

    # ── DatasourceHandler contract ─────────────────────────────────────────

    def sqx_name(self, symbol: str, datatype: str) -> str:
        """Build ``EURUSD_M1_jforex`` with the shared boundary-1 validation."""
        return resolve_symbol(symbol, datatype, "jforex")

    async def ensure(self, symbol: str, datatype: str, sqx_name: str) -> None:
        """Verify JForex already holds history for the symbol (fail-closed)."""
        self._require_history(sqx_name)

    async def update(self, symbol: str, datatype: str, sqx_name: str) -> None:
        """Verify JForex history is available (JForex refreshes on its own)."""
        self._require_history(sqx_name)

    # ── Historical data API ─────────────────────────────────────────────────

    def fetch_history(self, symbol: str, datatype: str) -> list[Bar]:
        """Return normalized OHLCV bars from local JForex history.

        Reads ``history/{SQX_NAME}.json`` from the state directory. Returns
        an empty list when the state directory or file is missing or the
        JSON is malformed — the same tolerance as :class:`JForexLiveFeed`
        reads (benign: the platform simply has not downloaded it yet).
        """
        if self.state_dir is None:
            return []
        path = self.state_dir / "history" / f"{self.sqx_name(symbol, datatype)}.json"
        if not path.is_file():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, list):
            return []
        return self._parse_bars(raw)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _require_history(self, sqx_name: str) -> None:
        """Fail-closed check that local JForex history exists."""
        if self.state_dir is None:
            raise DataManagerError(
                "JForex datasource not configured: set jforex_state_dir "
                "on DataManager"
            )
        path = self.state_dir / "history" / f"{sqx_name}.json"
        if not path.is_file():
            raise DataManagerError(
                f"JForex has no local history for {sqx_name!r} — "
                "download the instrument in the JForex4 platform first"
            )

    @staticmethod
    def _parse_bars(raw: list[dict[str, Any]]) -> list[Bar]:
        """Convert raw OHLCV dicts into :class:`Bar` instances (pure).

        Rows with missing keys or unparseable values are skipped.
        """
        bars: list[Bar] = []
        for row in raw:
            try:
                bars.append(
                    Bar(
                        timestamp=JForexProvider._parse_timestamp(row["timestamp"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return bars

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        """Parse an ISO-8601 string or datetime into an aware UTC datetime."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
