"""Market data models for OHLCV bar normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class Bar(BaseModel):
    """Normalized OHLCV bar.

    All timestamps are stored in UTC. Naive datetimes are assumed UTC.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @field_validator("timestamp", mode="before")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class MarketDataConfig(BaseModel):
    """Configuration for a market data fetch."""

    source: Literal["yahoo", "dukascopy"]
    symbol: str
    timeframe: str
    start: datetime | None = None
    end: datetime | None = None
