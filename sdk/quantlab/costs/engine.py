"""Cost computation engine — per-trade and per-symbol cost aggregation."""

from __future__ import annotations

from typing import Dict, List, Optional

from quantlab.costs.models import CostBreakdown
from quantlab.costs.profiles import BrokerProfile

# ── Helpers ──────────────────────────────────────────────────────────────────────

_PROFILE_ALIASES: dict[str, str] = {
    "dukascopy": "dukascopy",
    "ib": "interactive_brokers",
    "interactive_brokers": "interactive_brokers",
    "oanda": "oanda",
}


def _resolve_profile(name: str) -> BrokerProfile:
    """Resolve a profile name to a BrokerProfile instance."""
    normalized = name.strip().lower()
    factory_name = _PROFILE_ALIASES.get(normalized)
    if factory_name is None:
        factories = sorted(set(_PROFILE_ALIASES.values()))
        raise ValueError(
            f"Unknown profile: {name!r}. Known: {factories}"
        )
    factory = getattr(BrokerProfile, factory_name)
    return factory()


def _pip_value(symbol: str, volume: float) -> float:
    """Estimate pip value in account currency for a given symbol and volume.

    For major forex pairs, 1 pip ≈ $10 per standard lot (100k units).
    This is a simplifying assumption — cross-rates and minors vary.
    """
    _ = symbol  # Reserved for future symbol-specific pip values
    return 10.0 * (volume / 100_000.0)


# ── CostEngine ───────────────────────────────────────────────────────────────────


class CostEngine:
    """Computes trade costs given a broker profile.

    Provides per-trade ``compute()``, per-symbol aggregation via
    ``compute_symbol()``, and runtime profile switching via ``set_profile()``.
    """

    def __init__(self, profile: BrokerProfile) -> None:
        self._profile = profile
        self._history: Dict[str, List[CostBreakdown]] = {}
        self._session_multipliers: Dict[str, float] = {
            s.name: s.spread_multiplier for s in profile.sessions
        }

    # ── Public API ───────────────────────────────────────────────────────────────

    @property
    def profile(self) -> BrokerProfile:
        """The currently active broker profile."""
        return self._profile

    def compute(
        self,
        symbol: str,
        volume: float,
        direction: str,
        session: str | None = None,
        held_overnight: bool = False,
    ) -> CostBreakdown:
        """Compute full cost breakdown for a single trade.

        Parameters
        ----------
        symbol:
            Traded symbol (e.g. ``"EURUSD"``).
        volume:
            Trade volume in units.
        direction:
            Trade direction — ``"LONG"`` or ``"SHORT"``.
        session:
            Optional trading session name for session-aware spreads
            and slippage.
        held_overnight:
            Whether the position is held overnight (swap applies).

        Returns
        -------
        CostBreakdown
            Structured breakdown with all cost components.
        """
        p = self._profile
        notional = volume

        # Compute individual cost components
        commission = p.commission.compute(volume, notional)
        swap = p.swap.compute(direction) if held_overnight else 0.0
        slippage = p.slippage.get_slippage(session)

        # Base spread from SpreadConfig (already applies session_overrides)
        spread = p.spread_config.effective_spread(session)
        # Apply BrokerProfile session multiplier if a matching session exists
        if session and session in self._session_multipliers:
            spread *= self._session_multipliers[session]

        total_pips = swap + slippage + spread
        pip_val = _pip_value(symbol, volume)
        total_cost = commission + (total_pips * pip_val)

        breakdown = CostBreakdown(
            symbol=symbol,
            volume=volume,
            direction=direction,
            commission=round(commission, 4),
            swap=round(swap, 4),
            slippage=round(slippage, 4),
            spread=round(spread, 4),
            total_pips=round(total_pips, 4),
            total_cost=round(total_cost, 4),
        )

        # Record in history for compute_symbol aggregation
        self._history.setdefault(symbol, []).append(breakdown)

        return breakdown

    def compute_symbol(self, symbol: str) -> dict:
        """Aggregate costs across all recorded trades for a symbol.

        Parameters
        ----------
        symbol:
            Symbol to aggregate (e.g. ``"EURUSD"``).

        Returns
        -------
        dict
            Aggregated totals with keys:
            ``total_cost``, ``avg_cost_per_trade``, ``min_commission``,
            ``max_commission``, ``trade_count``, and per-component min/max.
        """
        trades = self._history.get(symbol, [])
        if not trades:
            return {
                "total_cost": 0.0,
                "avg_cost_per_trade": 0.0,
                "min_commission": 0.0,
                "max_commission": 0.0,
                "min_swap": 0.0,
                "max_swap": 0.0,
                "min_slippage": 0.0,
                "max_slippage": 0.0,
                "min_spread": 0.0,
                "max_spread": 0.0,
                "trade_count": 0,
            }

        total_cost = sum(t.total_cost for t in trades)
        commissions = [t.commission for t in trades]
        swaps = [t.swap for t in trades]
        slippages = [t.slippage for t in trades]
        spreads = [t.spread for t in trades]

        return {
            "total_cost": round(total_cost, 4),
            "avg_cost_per_trade": round(total_cost / len(trades), 4),
            "min_commission": round(min(commissions), 4),
            "max_commission": round(max(commissions), 4),
            "min_swap": round(min(swaps), 4),
            "max_swap": round(max(swaps), 4),
            "min_slippage": round(min(slippages), 4),
            "max_slippage": round(max(slippages), 4),
            "min_spread": round(min(spreads), 4),
            "max_spread": round(max(spreads), 4),
            "trade_count": len(trades),
        }

    def set_profile(self, profile: str | BrokerProfile) -> None:
        """Switch the active broker profile at runtime.

        Parameters
        ----------
        profile:
            A ``BrokerProfile`` instance, or a string name
            (``"dukascopy"``, ``"ib"``, ``"interactive_brokers"``,
            ``"oanda"``).

        Raises
        ------
        ValueError
            If the profile name is not recognised.
        """
        if isinstance(profile, BrokerProfile):
            self._profile = profile
        else:
            self._profile = _resolve_profile(profile)
