"""Exploration Decision Artifact — 13-field decision record per spec.

This model captures the output of the exploration pipeline (E1–E11).
It is the canonical artifact that feeds the campaign pipeline via
ResearchDirector prior context.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BrokerCostSnapshot(BaseModel):
    """Updated broker cost snapshot (E9)."""

    commission_per_lot: float | None = Field(
        default=None, description="Commission per lot (round trip)"
    )
    slippage_pips: float | None = Field(
        default=None, description="Average slippage in pips"
    )
    spread_pips: float | None = Field(
        default=None, description="Average spread in pips"
    )
    swap_long: float | None = Field(
        default=None, description="Swap rate for long positions (points)"
    )
    swap_short: float | None = Field(
        default=None, description="Swap rate for short positions (points)"
    )
    rollover_days: int | None = Field(
        default=None, description="Rollover frequency (days)"
    )
    triple_swap_day: str | None = Field(
        default=None, description="Day when triple swap applies (e.g. Wednesday)"
    )
    source: str = Field(
        default="", description="Source of this data (API, web, manual)"
    )
    fetched_at: str = Field(
        default="", description="ISO timestamp when fetched"
    )


class ExplorationDecision(BaseModel):
    """13-field exploration decision artifact per spec.

    This is the canonical output of the exploration pipeline (E1–E11).
    It captures all decisions needed to configure a campaign.
    """

    model_config = ConfigDict(extra="forbid")

    # 1. Capital
    capital_usd: float = Field(
        ..., gt=0, description="Total capital allocated to this campaign (USD)"
    )

    # 2. Market
    market: str = Field(
        ..., min_length=1, description="Market to trade (e.g. EURUSD, SP500, XAUUSD)"
    )

    # 3. Instruments
    instruments: list[str] = Field(
        default_factory=list,
        description="Specific instruments/contracts to trade within the market",
    )

    # 4. Timeframe
    timeframe: str = Field(
        ..., min_length=1, description="Primary chart timeframe (e.g. M5, M15, H1, H4, D1)"
    )

    # 5. Leverage
    leverage: float = Field(
        ..., gt=0, le=500, description="Account leverage (e.g. 30, 50, 100, 500)"
    )

    # 6. Capital limits
    capital_limits: dict[str, Any] = Field(
        default_factory=dict,
        description="Capital constraints: max_drawdown_pct, risk_per_trade_usd, max_concurrent_positions, min_lot_size, max_lot_size",
    )

    # 7. Operational restrictions
    operational_restrictions: dict[str, Any] = Field(
        default_factory=dict,
        description="Operational limits: trading_hours, forbidden_days, max_daily_trades, news_filter, max_spread_pips",
    )

    # 8. Risk management
    risk_management: dict[str, Any] = Field(
        default_factory=dict,
        description="Risk rules: stop_loss_type, stop_loss_pips, take_profit_pips, trailing_stop, max_correlation, portfolio_heat_limit",
    )

    # 9. Money management
    money_management: dict[str, Any] = Field(
        default_factory=dict,
        description="Money management: position_sizing_method, fixed_fractional_pct, kelly_fraction, compounding, withdrawal_schedule",
    )

    # 10. Prior related observations
    prior_observations: list[str] = Field(
        default_factory=list,
        description="Prior observations/learnings from memory lake relevant to this exploration",
    )

    # 11. Statistical edge
    statistical_edge: dict[str, Any] = Field(
        default_factory=dict,
        description="Estimated edge: expected_sharpe, win_rate, profit_factor, avg_win_loss_ratio, expectancy_per_trade, sample_size",
    )

    # 12. Hypothesis to verify
    hypothesis: str = Field(
        ..., min_length=10, description="Testable hypothesis derived from exploration"
    )

    # 13. Updated broker info
    broker_info: BrokerCostSnapshot = Field(
        default_factory=BrokerCostSnapshot,
        description="Updated broker costs: commission, slippage, spread, swap, rollover, triple swap",
    )

    # Meta
    exploration_id: str = Field(
        default="", description="Unique ID for this exploration run"
    )
    created_at: str = Field(
        default="", description="ISO timestamp when exploration completed"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-blocking warnings (e.g. small-capital risk)"
    )