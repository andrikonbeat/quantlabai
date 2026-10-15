"""E5: Asset Evaluator.

Evaluates financial-asset possibilities considering small-capital technical
limits, ultra-tight stop losses, and market moves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetScore:
    """Scored instrument with tight-SL feasibility analysis."""

    symbol: str
    market: str
    score: float  # 0.0–1.0
    tight_sl_feasible: bool
    min_viable_sl_pips: float
    spread_cost_pct_of_sl: float  # spread / min SL (lower = better)
    tick_value_usd: float
    min_lot: float
    risk_usd_at_min_lot: float  # risk with min SL at min lot
    capital_utilization_pct: float  # risk / capital (lower = better)
    rationale: str
    metadata: dict[str, Any]


class AssetEvaluator:
    """Evaluates instruments given small capital, ultra-tight SL, moves (E5)."""

    # Instrument metadata: typical spreads, tick values, broker min stop.
    # pip_value is per 1.0 lot; risk scales linearly with lot size.
    INSTRUMENT_META = {
        # Majors (forex)
        "EURUSD": {
            "market": "forex", "spread_pips": 0.8, "pip_value": 10.0,
            "min_lot": 0.01, "min_stop_pips": 5, "atr_pips": 60,
        },
        "GBPUSD": {
            "market": "forex", "spread_pips": 1.2, "pip_value": 10.0,
            "min_lot": 0.01, "min_stop_pips": 5, "atr_pips": 80,
        },
        "USDJPY": {
            "market": "forex", "spread_pips": 0.9, "pip_value": 9.0,
            "min_lot": 0.01, "min_stop_pips": 5, "atr_pips": 55,
        },
        "AUDUSD": {
            "market": "forex", "spread_pips": 1.0, "pip_value": 10.0,
            "min_lot": 0.01, "min_stop_pips": 5, "atr_pips": 55,
        },
        "USDCAD": {
            "market": "forex", "spread_pips": 1.3, "pip_value": 7.5,
            "min_lot": 0.01, "min_stop_pips": 5, "atr_pips": 65,
        },
        "USDCHF": {
            "market": "forex", "spread_pips": 1.1, "pip_value": 10.5,
            "min_lot": 0.01, "min_stop_pips": 5, "atr_pips": 55,
        },
        "NZDUSD": {
            "market": "forex", "spread_pips": 1.4, "pip_value": 10.0,
            "min_lot": 0.01, "min_stop_pips": 5, "atr_pips": 60,
        },
        # Metals
        "XAUUSD": {
            "market": "metals", "spread_pips": 2.5, "pip_value": 1.0,
            "min_lot": 0.01, "min_stop_pips": 20, "atr_pips": 150,
        },
        "XAGUSD": {
            "market": "metals", "spread_pips": 3.0, "pip_value": 5.0,
            "min_lot": 0.01, "min_stop_pips": 15, "atr_pips": 100,
        },
        # Indices (CFD)
        "US30": {
            "market": "indices", "spread_pips": 2.0, "pip_value": 1.0,
            "min_lot": 0.10, "min_stop_pips": 15, "atr_pips": 200,
        },
        "NAS100": {
            "market": "indices", "spread_pips": 1.5, "pip_value": 1.0,
            "min_lot": 0.10, "min_stop_pips": 12, "atr_pips": 180,
        },
        "SPX500": {
            "market": "indices", "spread_pips": 0.5, "pip_value": 2.5,
            "min_lot": 0.10, "min_stop_pips": 10, "atr_pips": 60,
        },
        # Crypto
        "BTCUSD": {
            "market": "crypto", "spread_pips": 15.0, "pip_value": 1.0,
            "min_lot": 0.001, "min_stop_pips": 80, "atr_pips": 2500,
        },
        "ETHUSD": {
            "market": "crypto", "spread_pips": 2.0, "pip_value": 1.0,
            "min_lot": 0.01, "min_stop_pips": 25, "atr_pips": 150,
        },
    }

    def __init__(
        self,
        capital_usd: float,
        max_risk_per_trade_pct: float = 1.0,
        max_spread_pct_of_sl: float = 0.20,
        allowed_markets: list[str] | None = None,
    ) -> None:
        self.capital_usd = capital_usd
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_spread_pct_of_sl = max_spread_pct_of_sl
        self.allowed_markets = allowed_markets

    def evaluate(self, symbols: list[str] | None = None) -> list[AssetScore]:
        """Score candidate instruments for tight-SL feasibility."""
        candidates = symbols or list(self.INSTRUMENT_META.keys())
        risk_budget_usd = self.capital_usd * (self.max_risk_per_trade_pct / 100.0)
        results: list[AssetScore] = []

        for symbol in candidates:
            meta = self.INSTRUMENT_META.get(symbol)
            if not meta:
                continue
            if self.allowed_markets and meta["market"] not in self.allowed_markets:
                continue

            spread = meta["spread_pips"]
            pip_value = meta["pip_value"]
            min_lot = meta["min_lot"]
            broker_min_sl = meta["min_stop_pips"]

            # Tight SL candidate: broker minimum.
            min_viable_sl = broker_min_sl
            # Risk at min lot with min SL.
            risk_at_min = min_lot * min_viable_sl * pip_value
            capital_util = risk_at_min / max(self.capital_usd, 1e-9) * 100.0
            # Spread cost as fraction of SL.
            spread_pct = spread / max(min_viable_sl, 1e-9)
            # Feasibility: risk fits budget AND spread is a small share of SL.
            tight_sl_feasible = (
                risk_at_min <= risk_budget_usd
                and spread_pct <= self.max_spread_pct_of_sl
            )

            # Score components.
            fit_score = max(0.0, 1.0 - risk_at_min / max(risk_budget_usd, 1e-9))
            spread_score = max(0.0, 1.0 - spread_pct / self.max_spread_pct_of_sl)
            score = round(0.6 * fit_score + 0.4 * spread_score, 3)

            rationale = (
                f"min lot {min_lot}, min SL {broker_min_sl} pips, "
                f"risk ${risk_at_min:.2f} of ${risk_budget_usd:.2f} budget "
                f"({capital_util:.1f}% capital), spread {spread_pct:.0%} of SL"
            )

            results.append(AssetScore(
                symbol=symbol,
                market=meta["market"],
                score=score,
                tight_sl_feasible=tight_sl_feasible,
                min_viable_sl_pips=float(min_viable_sl),
                spread_cost_pct_of_sl=round(spread_pct, 4),
                tick_value_usd=pip_value,
                min_lot=min_lot,
                risk_usd_at_min_lot=round(risk_at_min, 2),
                capital_utilization_pct=round(capital_util, 2),
                rationale=rationale,
                metadata=meta,
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results
