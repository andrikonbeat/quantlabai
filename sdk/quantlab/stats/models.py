"""Pydantic models for statistics engine output."""

from __future__ import annotations

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
