"""E3: Market Evaluator.

Scores markets by capital, user limits, risk, and gathered info.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MarketScore:
    """Scored market with rationale."""

    market: str
    score: float  # 0.0–1.0
    rationale: str
    capital_fit: float  # 0.0–1.0
    risk_fit: float  # 0.0–1.0
    liquidity_score: float  # 0.0–1.0
    spread_typical_pips: float
    avg_daily_range_pips: float
    trading_hours_overlap: str  # e.g. "London/NY overlap"
    metadata: dict[str, Any]


class MarketEvaluator:
    """Evaluates market possibilities given capital, user limits, info, risks (E3)."""

    # Market metadata (simplified; could be loaded from KB)
    MARKET_META = {
        "EURUSD": {
            "spread_pips": 0.8,
            "daily_range_pips": 70,
            "liquidity": 1.0,
            "session": "London/NY",
            "min_lot": 0.01,
            "pip_value": 10.0,
        },
        "GBPUSD": {
            "spread_pips": 1.2,
            "daily_range_pips": 90,
            "liquidity": 0.95,
            "session": "London/NY",
            "min_lot": 0.01,
            "pip_value": 10.0,
        },
        "USDJPY": {
            "spread_pips": 0.9,
            "daily_range_pips": 65,
            "liquidity": 0.95,
            "session": "Tokyo/London",
            "min_lot": 0.01,
            "pip_value": 9.0,
        },
        "AUDUSD": {
            "spread_pips": 1.0,
            "daily_range_pips": 60,
            "liquidity": 0.85,
            "session": "Sydney/Tokyo",
            "min_lot": 0.01,
            "pip_value": 10.0,
        },
        "USDCAD": {
            "spread_pips": 1.3,
            "daily_range_pips": 70,
            "liquidity": 0.85,
            "session": "NY",
            "min_lot": 0.01,
            "pip_value": 7.5,
        },
        "XAUUSD": {
            "spread_pips": 2.5,
            "daily_range_pips": 150,
            "liquidity": 0.9,
            "session": "London/NY",
            "min_lot": 0.01,
            "pip_value": 1.0,  # per ounce
        },
        "SP500": {
            "spread_pips": 0.5,
            "daily_range_pips": 3000,  # index points
            "liquidity": 1.0,
            "session": "NY",
            "min_lot": 0.1,  # CFD lots
            "pip_value": 1.0,
        },
        "NASDAQ": {
            "spread_pips": 1.0,
            "daily_range_pips": 4000,
            "liquidity": 0.95,
            "session": "NY",
            "min_lot": 0.1,
            "pip_value": 1.0,
        },
        "BTCUSD": {
            "spread_pips": 15.0,
            "daily_range_pips": 3000,  # USD
            "liquidity": 0.8,
            "session": "24/7",
            "min_lot": 0.001,
            "pip_value": 1.0,
        },
    }

    def __init__(
        self,
        capital_usd: float,
        user_risk_pct: float = 1.0,
        max_spread_pips: float | None = None,
        forbidden_markets: list[str] | None = None,
        required_sessions: list[str] | None = None,
    ) -> None:
        self.capital_usd = capital_usd
        self.user_risk_pct = user_risk_pct
        self.max_spread_pips = max_spread_pips
        self.forbidden_markets = set(forbidden_markets or [])
        self.required_sessions = required_sessions or []

    def evaluate(self, markets: list[str] | None = None) -> list[MarketScore]:
        """Score candidate markets."""
        candidates = markets or list(self.MARKET_META.keys())
        results = []

        for market in candidates:
            if market in self.forbidden_markets:
                continue

            meta = self.MARKET_META.get(market)
            if not meta:
                continue

            # Session filter
            if self.required_sessions:
                if not any(s in meta["session"] for s in self.required_sessions):
                    continue

            # Spread filter
            if self.max_spread_pips and meta["spread_pips"] > self.max_spread_pips:
                continue

            # Capital fit: can we trade min lot with 1% risk?
            min_lot = meta["min_lot"]
            pip_value = meta["pip_value"]
            risk_usd = self.capital_usd * 0.01
            sl_pips_for_risk = (risk_usd / (min_lot * pip_value)) if pip_value > 0 else 999

            # Typical SL for this market (2x daily ATR ≈ 20% daily range)
            typical_sl = meta["daily_range_pips"] * 0.2
            capital_fit = min(1.0, typical_sl / max(sl_pips_for_risk, 1))

            # Risk fit: spread vs daily range
            spread_ratio = meta["spread_pips"] / max(meta["daily_range_pips"], 1)
            risk_fit = max(0.0, 1.0 - spread_ratio * 10)  # penalize high spread

            # Liquidity score
            liquidity_score = meta["liquidity"]

            # Composite score
            score = (
                capital_fit * 0.4 +
                risk_fit * 0.3 +
                liquidity_score * 0.3
            )

            rationale = (
                f"Spread {meta['spread_pips']} pips, daily range {meta['daily_range_pips']} pips, "
                f"session {meta['session']}, min lot {min_lot}, "
                f"capital fit {capital_fit:.0%}, risk fit {risk_fit:.0%}"
            )

            results.append(MarketScore(
                market=market,
                score=round(score, 3),
                rationale=rationale,
                capital_fit=round(capital_fit, 3),
                risk_fit=round(risk_fit, 3),
                liquidity_score=round(liquidity_score, 3),
                spread_typical_pips=meta["spread_pips"],
                avg_daily_range_pips=meta["daily_range_pips"],
                trading_hours_overlap=meta["session"],
                metadata=meta,
            ))

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results