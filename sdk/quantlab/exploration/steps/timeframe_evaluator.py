"""E4: Timeframe Evaluator.

Evaluates timeframe possibilities given capital limits and avg SL pips per timeframe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TimeframeScore:
    """Scored timeframe with SL-pips analysis."""

    timeframe: str
    score: float  # 0.0–1.0
    avg_sl_pips: int
    typical_sl_pips: int
    capital_fit: float  # 0.0–1.0
    noise_ratio: float  # spread / avg_range (lower = better)
    trades_per_month_est: int
    rationale: str
    metadata: dict[str, Any]


class TimeframeEvaluator:
    """Evaluates timeframe possibilities given capital limits and avg SL pips (E4)."""

    # Timeframe metadata (broker/KB typical values)
    TIMEFRAME_META = {
        "M1": {
            "avg_range_pips": 8,
            "spread_pips": 0.8,
            "trades_per_day": 50,
            "noise_level": "very_high",
            "min_sl_pips": 5,
        },
        "M5": {
            "avg_range_pips": 15,
            "spread_pips": 0.8,
            "trades_per_day": 20,
            "noise_level": "high",
            "min_sl_pips": 10,
        },
        "M15": {
            "avg_range_pips": 25,
            "spread_pips": 0.8,
            "trades_per_day": 8,
            "noise_level": "high",
            "min_sl_pips": 15,
        },
        "M30": {
            "avg_range_pips": 35,
            "spread_pips": 0.8,
            "trades_per_day": 4,
            "noise_level": "medium",
            "min_sl_pips": 20,
        },
        "H1": {
            "avg_range_pips": 50,
            "spread_pips": 0.8,
            "trades_per_day": 2,
            "noise_level": "medium",
            "min_sl_pips": 25,
        },
        "H4": {
            "avg_range_pips": 90,
            "spread_pips": 0.8,
            "trades_per_day": 0.5,
            "noise_level": "low",
            "min_sl_pips": 40,
        },
        "D1": {
            "avg_range_pips": 150,
            "spread_pips": 0.8,
            "trades_per_day": 0.2,
            "noise_level": "very_low",
            "min_sl_pips": 60,
        },
        "W1": {
            "avg_range_pips": 400,
            "spread_pips": 0.8,
            "trades_per_day": 0.03,
            "noise_level": "very_low",
            "min_sl_pips": 120,
        },
    }

    def __init__(
        self,
        capital_usd: float,
        spread_pips: float = 0.8,
        risk_per_trade_pct: float = 1.0,
        min_lot: float = 0.01,
        pip_value: float = 10.0,
    ) -> None:
        self.capital_usd = capital_usd
        self.spread_pips = spread_pips
        self.risk_per_trade_pct = risk_per_trade_pct
        self.min_lot = min_lot
        self.pip_value = pip_value

    def evaluate(self, timeframes: list[str] | None = None) -> list[TimeframeScore]:
        """Score candidate timeframes."""
        candidates = timeframes or list(self.TIMEFRAME_META.keys())
        results = []

        risk_usd = self.capital_usd * (1.0 / 100.0)  # 1% risk per trade

        for tf in candidates:
            meta = self.TIMEFRAME_META.get(tf)
            if not meta:
                continue

            # Capital fit: can we place min lot with SL = typical SL for this TF?
            typical_sl = meta["min_sl_pips"]
            risk_usd = self.capital_usd * 0.01
            # For min lot: required SL pips = risk / (lot * pip_value)
            # Actually we need SL that keeps risk at 1%: SL = risk / (lot * pip_value)
            required_sl_for_risk = risk_usd / (0.01 * 10.0)  # assuming min_lot=0.01, pip_value=10

            # Use the larger of typical SL and required SL
            actual_sl = max(meta["min_sl_pips"], int(required_sl_for_risk))

            # Capital fit: can we afford the SL with min lot?
            capital_fit = min(1.0, meta["avg_range_pips"] / max(actual_sl, 1))

            # Noise ratio: spread / avg_range
            noise_ratio = self.spread_pips / max(meta["avg_range_pips"], 1)

            # Estimated trades per month
            trades_per_month = int(meta["trades_per_day"] * 20)

            # Score: capital fit (40%), noise (30%), trade frequency (30%)
            # Lower noise = better, higher trades = better (for stats)
            freq_score = min(1.0, meta["trades_per_day"] / 10.0)
            score = (
                capital_fit * 0.4 +
                (1.0 - min(noise_ratio * 5, 1.0)) * 0.3 +
                freq_score * 0.3
            )

            rationale = (
                f"Range {meta['avg_range_pips']} pips, min SL {meta['min_sl_pips']} pips, "
                f"actual SL {actual_sl} pips, spread {self.spread_pips} pips, "
                f"noise ratio {noise_ratio:.2f}, ~{trades_per_month} trades/mo"
            )

            results.append(TimeframeScore(
                timeframe=tf,
                score=round(score, 3),
                avg_sl_pips=meta["avg_range_pips"],
                typical_sl_pips=actual_sl,
                capital_fit=round(min(1.0, capital_fit), 3),
                noise_ratio=round(noise_ratio, 3),
                trades_per_month_est=trades_per_month,
                rationale=rationale,
                metadata=meta,
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results