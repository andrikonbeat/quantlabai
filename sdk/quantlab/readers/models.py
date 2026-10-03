"""Pydantic models for Databank export parsing.

Defines the structured representations of backtest results:
individual trades, equity curve points, and summary statistics.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Trade(BaseModel):
    """A single trade from a backtest result.

    Represents one opened-and-closed position with entry/exit timing,
    direction, size, net profit, and maximum adverse excursion.
    """

    entry_time: datetime = Field(..., description="Trade entry timestamp")
    exit_time: datetime = Field(..., description="Trade exit timestamp")
    direction: str = Field(..., description="Trade direction: LONG or SHORT")
    lots: float = Field(..., description="Trade size in lots")
    profit: float = Field(..., description="Net profit in account currency")
    drawdown: float = Field(
        default=0.0,
        description="Maximum drawdown during the trade (positive value)",
    )


class EquityPoint(BaseModel):
    """A single equity curve data point."""

    timestamp: datetime = Field(..., description="Equity measurement timestamp")
    equity: float = Field(..., description="Account equity at this point")


class SummaryStats(BaseModel):
    """Summary statistics from a Databank backtest export.

    All fields are optional because different Databank exports may
    include different subsets of summary metrics. Missing fields
    default to ``None`` rather than raising a parse error.
    """

    net_profit: float | None = Field(default=None, description="Total net profit")
    total_trades: int | None = Field(default=None, description="Total number of trades")
    win_rate: float | None = Field(default=None, description="Win rate as a decimal (0.0–1.0)")
    max_drawdown: float | None = Field(
        default=None, description="Maximum drawdown as a percentage"
    )
    profit_factor: float | None = Field(default=None, description="Profit factor (gross profit / gross loss)")
    sharpe_ratio: float | None = Field(default=None, description="Annualised Sharpe ratio")


class StrategySummary(BaseModel):
    """Per-strategy metrics from a Databank strategies export.

    All fields are optional because different SQX exports may include
    different subsets of strategy metrics. Missing fields default to
    ``None`` rather than raising a parse error.
    """

    strategy_name: str | None = Field(default=None, description="Strategy name")
    profit_factor: float | None = Field(default=None, description="Profit factor")
    sharpe_ratio: float | None = Field(default=None, description="Sharpe ratio")
    win_rate: float | None = Field(default=None, description="Win rate as a decimal (0.0–1.0)")
    total_trades: int | None = Field(default=None, description="Total number of trades")
    max_drawdown: float | None = Field(default=None, description="Maximum drawdown as a percentage")
    mc_p10: float | None = Field(default=None, description="Monte Carlo p10 metric")
    wf_is_sharpe: float | None = Field(default=None, description="Walk-forward in-sample Sharpe")
    wf_oos_sharpe: float | None = Field(default=None, description="Walk-forward out-of-sample Sharpe")
    wf_cycles: int | None = Field(default=None, description="Number of walk-forward cycles")
