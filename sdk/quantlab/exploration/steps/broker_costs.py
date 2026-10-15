"""E9: Broker Costs Fetcher.

Fetches updated broker info (commissions, slippage, spread, swap,
rollovers, triple swap) via local profiles first, then an optional
pluggable web/API fetch hook.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from quantlab.exploration.models import BrokerCostSnapshot

# Pluggable web fetch hook: async or sync callable receiving a query
# string and returning a dict of cost fields. Injected by callers/tests;
# the fetcher degrades gracefully to local data when absent.
WebFetchFn = Callable[[str], Any]


class BrokerCostsFetcher:
    """Fetches updated broker costs via local profiles + web/API (E9)."""

    def __init__(
        self,
        web_fetch_fn: WebFetchFn | None = None,
        local_collector: Any | None = None,
        broker_profile: Any | None = None,
    ) -> None:
        self.web_fetch_fn = web_fetch_fn
        self.local_collector = local_collector
        self.broker_profile = broker_profile

    def fetch(
        self,
        symbol: str,
        broker: str = "dukascopy",
    ) -> BrokerCostSnapshot:
        """Fetch a cost snapshot for one symbol.

        Order: broker profile → local collector → web hook → defaults.
        Never raises on fetch failure; records the source used.
        """
        snapshot = BrokerCostSnapshot(source="defaults")
        profile = self.broker_profile
        if profile is None and self.local_collector is not None:
            engine = getattr(self.local_collector, "_engine", None)
            profile = getattr(engine, "profile", None)

        if profile is not None:
            self._apply_profile(snapshot, profile, symbol)
            snapshot.source = "local-profile"

        if self.local_collector is not None:
            try:
                snapshot.spread_pips = float(
                    self.local_collector.spread_pips(symbol)
                )
                snapshot.slippage_pips = float(
                    self.local_collector.get_recent_slippage(symbol)
                )
                if snapshot.source == "defaults":
                    snapshot.source = "local-collector"
            except Exception:
                pass

        if self.web_fetch_fn is not None:
            try:
                data = self.web_fetch_fn(f"{broker} {symbol} commission swap rollover")
                if isinstance(data, dict):
                    self._apply_web(snapshot, data)
                    snapshot.source = "web"
            except Exception:
                pass

        snapshot.fetched_at = datetime.now(UTC).isoformat()
        return snapshot

    @staticmethod
    def _apply_profile(
        snapshot: BrokerCostSnapshot, profile: Any, symbol: str
    ) -> None:
        spread_cfg = getattr(profile, "spread_config", None)
        if spread_cfg is not None:
            try:
                snapshot.spread_pips = float(spread_cfg.effective_spread())
            except Exception:
                pass
        slippage = getattr(profile, "slippage", None)
        if slippage is not None:
            try:
                snapshot.slippage_pips = float(slippage.get_slippage())
            except Exception:
                pass
        commission = getattr(profile, "commission", None)
        if commission is not None:
            for attr in ("per_lot", "per_lot_round_trip", "rate"):
                if hasattr(commission, attr):
                    try:
                        snapshot.commission_per_lot = float(getattr(commission, attr))
                        break
                    except Exception:
                        continue
        swap = getattr(profile, "swap", None)
        if swap is not None:
            for attr, field in (("long_rate", "swap_long"), ("short_rate", "swap_short")):
                if hasattr(swap, attr):
                    try:
                        setattr(snapshot, field, float(getattr(swap, attr)))
                    except Exception:
                        continue
            if hasattr(swap, "triple_day"):
                snapshot.triple_swap_day = str(swap.triple_day)
        rollover = getattr(profile, "rollover_days", None)
        if isinstance(rollover, int):
            snapshot.rollover_days = rollover

    @staticmethod
    def _apply_web(snapshot: BrokerCostSnapshot, data: dict[str, Any]) -> None:
        mapping = {
            "commission_per_lot": "commission_per_lot",
            "commission": "commission_per_lot",
            "slippage_pips": "slippage_pips",
            "slippage": "slippage_pips",
            "spread_pips": "spread_pips",
            "spread": "spread_pips",
            "swap_long": "swap_long",
            "swap_short": "swap_short",
            "rollover_days": "rollover_days",
            "triple_swap_day": "triple_swap_day",
            "triple_day": "triple_swap_day",
        }
        for key, field in mapping.items():
            if key in data and data[key] is not None:
                try:
                    if field in ("triple_swap_day",):
                        setattr(snapshot, field, str(data[key]))
                    else:
                        setattr(snapshot, field, float(data[key]))
                except (TypeError, ValueError):
                    continue
