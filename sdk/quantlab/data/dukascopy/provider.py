"""Dukascopy research data provider (G3).

Reuses ``DataManager`` → ``JForexProvider.fetch_history`` to return
normalized OHLC Bars for M1/M5/H1 research. Fail-soft: returns ``[]``
when the JForex state is missing, a symbol has no downloaded history,
or the symbol name fails the boundary-1 validation — it never raises,
so the research flow treats absence as a soft gap.

The provider only fetches. Dataset caching under ``knowledge/datasets/``
lives in the research flow (``cache_market_bars``) so the provider stays
a pure data path.
"""

from __future__ import annotations

from pathlib import Path

from quantlab.data import DataManager
from quantlab.data.market.models import Bar


class DukascopyProvider:
    """Dukascopy-backed research data path (D5 scope: M1/M5/H1).

    Args:
        data_manager: Injected :class:`DataManager` (tests). When
            omitted, a default manager is built from ``jforex_state_dir``.
        jforex_state_dir: JForex4 local state directory (root of
            ``history/``), consumed when no ``data_manager`` is injected.
    """

    name = "dukascopy"

    def __init__(
        self,
        data_manager: DataManager | None = None,
        jforex_state_dir: str | Path | None = None,
    ) -> None:
        self._data_manager = data_manager or DataManager(
            jforex_state_dir=jforex_state_dir
        )

    def fetch_bars(self, symbol: str, timeframe: str) -> list[Bar]:
        """Fetch normalized OHLC bars for ``symbol`` at ``timeframe``.

        Returns an empty list on any gap — no JForex state, no history
        file, invalid symbol, or a failing handler. Never raises.

        Args:
            symbol: Base symbol (e.g. ``EURUSD``).
            timeframe: FX timeframe (``M1``/``M5``/``H1``).

        Returns:
            Normalized :class:`Bar` instances, or ``[]`` on a soft gap.
        """
        try:
            handler = self._data_manager.datasources.get("jforex")
            if handler is None:
                return []
            return handler.fetch_history(symbol, timeframe)
        except Exception:
            return []


__all__ = ["DukascopyProvider"]