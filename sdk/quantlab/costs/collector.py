"""Cost collector — real-time cost data for execution and market guardians.

Implements the duck-typed protocol expected by ``ExecutionGuardian`` and
``MarketGuardian``: ``get_recent_slippage()``, ``.slippage``,
``spread_pips()``, and ``collect_all()``.
"""

from __future__ import annotations

from quantlab.costs.engine import CostEngine

# ── Defaults ─────────────────────────────────────────────────────────────────────

_DEFAULT_SLIPPAGE = 0.5
_DEFAULT_SPREAD = 1.5


class CostCollector:
    """Collects real-time cost data for guardian consumption.

    Provides slippage and spread estimates, either driven by a
    ``CostEngine`` (when a broker profile is configured) or using
    conservative defaults (when no engine is available).

    Duck-type protocol matches the ``hasattr`` checks in
    ``guardian/execution.py`` (``get_recent_slippage``, ``slippage``)
    and ``guardian/market.py`` (``collect_all``, dict access on entries).
    """

    def __init__(
        self,
        engine: CostEngine | None = None,
        default_spread: float = _DEFAULT_SPREAD,
    ) -> None:
        self._engine = engine
        self._default_spread = default_spread
        self._session_multipliers: dict[str, float] = {}
        if engine is not None:
            self._session_multipliers = {
                s.name: s.spread_multiplier for s in engine.profile.sessions
            }

    # ── Slippage ─────────────────────────────────────────────────────────────────

    def get_recent_slippage(self, symbol: str) -> float:
        """Return current slippage in pips for a symbol.

        Delegates to the engine's profile if available; otherwise returns
        a conservative default.
        """
        if self._engine is not None:
            return self._engine.profile.slippage.get_slippage()
        return _DEFAULT_SLIPPAGE

    @property
    def slippage(self) -> float:
        """Default slippage in pips — compatible with guardian ``hasattr`` check."""
        return self.get_recent_slippage("EURUSD")

    # ── Spread ───────────────────────────────────────────────────────────────────

    def spread_pips(self, symbol: str, session: str | None = None) -> float:
        """Return current spread in pips for a symbol and optional session.

        Uses the engine's profile spread when available; falls back to
        ``default_spread``.
        """
        if self._engine is not None:
            spread = self._engine.profile.spread_config.effective_spread(session)
            # Apply BrokerProfile session multiplier if a matching session exists
            if session and session in self._session_multipliers:
                spread *= self._session_multipliers[session]
            return spread
        return self._default_spread

    # ── Full collection ──────────────────────────────────────────────────────────

    def collect_all(self, symbols: list[str]) -> dict[str, dict]:
        """Collect cost data for all requested symbols.

        Returns a dict keyed by symbol, each containing ``spread_pips``,
        ``slippage_pips``, ``session_name``, and ``session_score``.

        The returned dicts are compatible with ``market.py``'s access
        patterns — both ``hasattr(pair_data, 'spread_pips')`` (which
        returns ``False`` for plain dicts) and the dict-key fallback.
        """
        result: dict[str, dict] = {}
        for sym in symbols:
            result[sym] = {
                "spread_pips": self.spread_pips(sym),
                "slippage_pips": self.get_recent_slippage(sym),
                "session_name": None,
                "session_score": 0.5,
            }
        return result
