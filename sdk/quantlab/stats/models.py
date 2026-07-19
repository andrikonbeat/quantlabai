"""Pydantic models for statistics engine output and aggregation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StatsResult(BaseModel):
    """Container for all computed trading metrics.

    Returned by ``StatisticsEngine.compute_all()`` to provide a single
    structured result with typed metric values.
    """

    profit_factor: Optional[float] = Field(default=None, description="Gross profit / abs(gross loss)")
    sharpe_ratio: Optional[float] = Field(default=None, description="Annualised Sharpe ratio")
    sortino_ratio: Optional[float] = Field(default=None, description="Annualised Sortino ratio")
    max_drawdown: Optional[float] = Field(default=None, description="Maximum drawdown as a percentage")
    mar_ratio: Optional[float] = Field(default=None, description="CAGR / max drawdown")
    recovery_factor: Optional[float] = Field(default=None, description="Net profit / max drawdown")
    expectancy: Optional[float] = Field(default=None, description="Average expected trade outcome")
    expectancy_ratio: Optional[float] = Field(default=None, description="Expectancy / avg loss")
    win_rate: Optional[float] = Field(default=None, description="Percentage of winning trades")
    total_trades: Optional[int] = Field(default=None, description="Total number of trades")


class AggregateStats(BaseModel):
    """Per-metric aggregate statistics across multiple campaigns/cycles."""

    mean: float
    median: float
    std: float
    min: float
    max: float
    p25: float
    p75: float
    count: int


class RollingMetrics(BaseModel):
    """Rolling window metrics over time."""

    timestamps: list[datetime]
    values: list[float]
    window: int
    metric_name: str


class BenchmarkComparison(BaseModel):
    """Strategy vs benchmark performance comparison."""

    alpha: float = 0.0
    beta: float = 1.0
    information_ratio: float = 0.0
    correlation: float = 0.0
    tracking_error: float = 0.0
