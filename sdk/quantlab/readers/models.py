"""Pydantic models for Databank export parsing.

Defines the structured representations of backtest results:
individual trades, equity curve points, and summary statistics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

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

    net_profit: Optional[float] = Field(default=None, description="Total net profit")
    total_trades: Optional[int] = Field(default=None, description="Total number of trades")
    win_rate: Optional[float] = Field(default=None, description="Win rate as a decimal (0.0–1.0)")
    max_drawdown: Optional[float] = Field(
        default=None, description="Maximum drawdown as a percentage"
    )
    profit_factor: Optional[float] = Field(default=None, description="Profit factor (gross profit / gross loss)")
    sharpe_ratio: Optional[float] = Field(default=None, description="Annualised Sharpe ratio")
