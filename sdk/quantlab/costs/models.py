"""Pydantic models for broker cost computation: commissions, swaps, slippage, spreads."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────


class CommissionType(str, Enum):
    """Supported commission calculation types."""

    FIXED = "fixed"
    PERCENT = "percent"
    TIERED = "tiered"


class SlippageMode(str, Enum):
    """Slippage computation mode."""

    STATIC = "static"
    SESSION = "session"


# ── Commission ─────────────────────────────────────────────────────────────────


class CommissionSchema(BaseModel):
    """Commission configuration supporting fixed, percentage, and tiered rates.

    For ``fixed``: ``value`` is a flat fee per trade.
    For ``percent``: ``value`` is a percentage of notional.
    For ``tiered``: ``tiers`` is a list of ``(min_notional, max_notional, rate_per_100k)``.
    """

    type: CommissionType
    value: float = Field(default=0.0, description="Flat fee or percentage rate")
    tiers: list[tuple[float, float, float]] = Field(
        default_factory=list,
        description="List of (min_notional, max_notional, rate) tuples for tiered commissions",
    )
    currency: str = Field(default="USD", description="Commission currency")

    def compute(self, volume: float, notional: float | None = None) -> float:
        """Compute commission cost for a trade.

        Parameters
        ----------
        volume:
            Trade volume in lots.
        notional:
            Trade notional value in account currency. Required for percent
            and tiered modes.

        Returns
        -------
        float
            Computed commission cost.
        """
        if self.type == CommissionType.FIXED:
            return self.value

        if self.type == CommissionType.PERCENT:
            return (notional or 0.0) * self.value / 100.0

        # TIERED — rates expressed per 100k notional
        if self.type == CommissionType.TIERED and notional:
            total = 0.0
            remaining = notional
            for min_n, max_n, rate in sorted(self.tiers, key=lambda t: t[0]):
                if remaining <= 0:
                    break
                bracket_size = max_n - min_n
                applicable = min(bracket_size, remaining)
                total += applicable * rate / 100_000.0
                remaining -= applicable
            return total

        return 0.0


# ── Swap ────────────────────────────────────────────────────────────────────────


class SwapRule(BaseModel):
    """Overnight swap / rollover rate configuration.

    Triple-swap is applied when the held-over day matches ``triple_day``.
    """

    long_rate: float = Field(..., description="Swap rate for LONG positions in pips")
    short_rate: float = Field(..., description="Swap rate for SHORT positions in pips")
    triple_day: str = Field(default="Wednesday", description="Day when triple swap applies")
    currency: str = Field(default="USD", description="Swap currency")

    def compute(self, direction: str, weekday: str | None = None) -> float:
        """Compute swap rate for a given direction and weekday.

        Parameters
        ----------
        direction:
            Trade direction — ``"LONG"`` or ``"SHORT"``.
        weekday:
            Day of the week. Defaults to ``"Tuesday"`` (non-triple day).

        Returns
        -------
        float
            Swap rate in pips.
        """
        effective_day = weekday or "Tuesday"
        rate = self.long_rate if direction.upper() == "LONG" else self.short_rate
        if effective_day == self.triple_day:
            rate *= 3
        return rate


# ── Slippage ────────────────────────────────────────────────────────────────────


class SlippageProfile(BaseModel):
    """Slippage configuration per symbol or broker.

    In ``static`` mode, ``fixed_pips`` is always returned.
    In ``session`` mode, per-session overrides from ``session_pips`` take
    precedence; unknown sessions fall back to ``fixed_pips``.
    """

    mode: SlippageMode = SlippageMode.STATIC
    fixed_pips: float = Field(default=0.5, description="Fixed slippage in pips")
    session_pips: dict[str, float] = Field(
        default_factory=dict,
        description="Per-session slippage pips (e.g. ``{'London': 0.3}``)",
    )

    def get_slippage(self, session: str | None = None) -> float:
        """Return slippage in pips for an optional trading session."""
        if self.mode == SlippageMode.SESSION and session and session in self.session_pips:
            return self.session_pips[session]
        return self.fixed_pips


# ── Market Session ──────────────────────────────────────────────────────────────


class MarketSession(BaseModel):
    """A named trading session with a spread multiplier.

    Used to adjust spreads during high or low liquidity windows
    (e.g. London open, New York close).
    """

    name: str = Field(..., description="Session name (e.g. ``London``, ``NewYork``)")
    open_time: str = Field(default="00:00", description="Session open time in HH:MM")
    close_time: str = Field(default="00:00", description="Session close time in HH:MM")
    spread_multiplier: float = Field(
        default=1.0, ge=0.0, description="Spread multiplier for this session"
    )


# ── Spread ──────────────────────────────────────────────────────────────────────


class SpreadConfig(BaseModel):
    """Spread configuration with base, session overrides, and asset defaults."""

    base_spread: float = Field(default=1.0, ge=0.0, description="Base spread in pips")
    session_overrides: dict[str, float] = Field(
        default_factory=dict,
        description="Per-session spread multipliers (e.g. ``{'London': 0.8}``)",
    )
    asset_defaults: dict[str, float] = Field(
        default_factory=dict,
        description="Per-symbol base spread overrides",
    )

    def effective_spread(self, session: str | None = None) -> float:
        """Compute effective spread for an optional trading session.

        Multiplies ``base_spread`` by the session-specific multiplier if
        one exists, otherwise uses 1.0.
        """
        multiplier = self.session_overrides.get(session, 1.0) if session else 1.0
        return round(self.base_spread * multiplier, 4)


# ── Cost Breakdown ──────────────────────────────────────────────────────────────


class CostBreakdown(BaseModel):
    """Detailed cost breakdown for a single trade."""

    symbol: str = Field(..., description="Traded symbol")
    volume: float = Field(..., description="Trade volume in lots")
    direction: str = Field(..., description="Trade direction (``LONG`` / ``SHORT``)")
    commission: float = Field(default=0.0, description="Commission cost in account currency")
    swap: float = Field(default=0.0, description="Swap cost in pips")
    slippage: float = Field(default=0.0, description="Slippage cost in pips")
    spread: float = Field(default=0.0, description="Spread cost in pips")
    total_pips: float = Field(default=0.0, description="Total cost in pips")
    total_cost: float = Field(default=0.0, description="Total cost in account currency")


# ── DSL Config ─────────────────────────────────────────────────────────────────


class CostsConfig(BaseModel):
    """DSL-level cost configuration for a research campaign.

    Embedded in ``ResearchConfig`` to enable broker-aware cost modelling
    per campaign.
    """

    broker: str = Field(
        ...,
        description="Broker identifier (``dukascopy``, ``ib``, ``oanda``)",
    )
    commission_override: Optional[CommissionSchema] = Field(
        default=None,
        description="Override the broker's default commission schema",
    )
    slippage_mode: str = Field(
        default="static",
        description="Slippage mode: ``static`` or ``session``",
    )
    spread_config: Optional[SpreadConfig] = Field(
        default=None,
        description="Override the broker's default spread config",
    )
