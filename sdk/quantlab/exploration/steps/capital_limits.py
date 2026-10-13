"""E7: Capital Limits Resolver.

Understands capital limits and operational restrictions, mirroring the
contracts consumed by `_apply_capital_constraints` so the exploration
decision can carry them into the campaign pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapitalLimits:
    """Resolved capital limits for a campaign."""

    max_drawdown_pct: float
    risk_per_trade_usd: float
    risk_per_trade_pct: float
    max_concurrent_positions: int
    min_lot_size: float
    max_lot_size: float
    instruments: list[str]
    timeframe: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_drawdown_pct": self.max_drawdown_pct,
            "risk_per_trade_usd": round(self.risk_per_trade_usd, 2),
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_concurrent_positions": self.max_concurrent_positions,
            "min_lot_size": self.min_lot_size,
            "max_lot_size": self.max_lot_size,
            "instruments": self.instruments,
            "timeframe": self.timeframe,
        }


@dataclass(frozen=True)
class OperationalRestrictions:
    """User operational restrictions for a campaign."""

    trading_hours_utc: str = "00:00-23:59"
    forbidden_days: list[str] = None  # type: ignore[assignment]
    max_daily_trades: int = 0  # 0 = unlimited
    news_filter: bool = False
    max_spread_pips: float = 0.0  # 0.0 = no limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "trading_hours_utc": self.trading_hours_utc,
            "forbidden_days": self.forbidden_days or [],
            "max_daily_trades": self.max_daily_trades,
            "news_filter": self.news_filter,
            "max_spread_pips": self.max_spread_pips,
        }


class CapitalLimitsResolver:
    """Resolves capital limits and operational restrictions (E7).

    Mirrors the semantics of `research_agent._apply_capital_constraints`:
    capital under 15% max-drawdown context tightens drawdown; risk per
    trade defaults to 1% of capital unless overridden.
    """

    def __init__(
        self,
        min_lot_size: float = 0.01,
        default_leverage: float = 30.0,
    ) -> None:
        self.min_lot_size = min_lot_size
        self.default_leverage = default_leverage

    def resolve(
        self,
        capital_usd: float,
        max_drawdown_pct: float = 15.0,
        risk_per_trade_pct: float = 1.0,
        risk_per_trade_usd: float | None = None,
        max_concurrent_positions: int = 3,
        instruments: list[str] | None = None,
        timeframe: str = "H1",
        leverage: float | None = None,
    ) -> CapitalLimits:
        """Resolve concrete capital limits."""
        if capital_usd <= 0:
            raise ValueError("capital_usd must be > 0")
        lev = leverage or self.default_leverage
        # Tighten drawdown for small capital (mirrors _apply_capital_constraints).
        dd = max_drawdown_pct
        if max_drawdown_pct < 15.0 or capital_usd < 500:
            dd = min(max_drawdown_pct, 10.0)
        # Risk per trade: explicit USD wins, else pct of capital.
        risk_usd = risk_per_trade_usd
        if risk_usd is None:
            risk_usd = capital_usd * (risk_per_trade_pct / 100.0)
        # Max lot by margin: lots ≈ C * leverage / 100_000.
        max_lot = max(self.min_lot_size, round((capital_usd * lev) / 100_000, 2))
        return CapitalLimits(
            max_drawdown_pct=dd,
            risk_per_trade_usd=round(risk_usd, 2),
            risk_per_trade_pct=risk_per_trade_pct,
            max_concurrent_positions=max_concurrent_positions,
            min_lot_size=self.min_lot_size,
            max_lot_size=max_lot,
            instruments=instruments or [],
            timeframe=timeframe,
        )

    def resolve_restrictions(
        self,
        trading_hours_utc: str = "00:00-23:59",
        forbidden_days: list[str] | None = None,
        max_daily_trades: int = 0,
        news_filter: bool = False,
        max_spread_pips: float = 0.0,
    ) -> OperationalRestrictions:
        """Resolve user operational restrictions."""
        return OperationalRestrictions(
            trading_hours_utc=trading_hours_utc,
            forbidden_days=forbidden_days or [],
            max_daily_trades=max_daily_trades,
            news_filter=news_filter,
            max_spread_pips=max_spread_pips,
        )
