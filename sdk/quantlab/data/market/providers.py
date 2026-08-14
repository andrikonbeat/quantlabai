"""Market data provider adapters for Yahoo Finance and Dukascopy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from quantlab.data.market.models import Bar


class MarketDataProvider(ABC):
    """Abstract base for market data providers.

    Each provider normalizes raw provider-specific rows into a common
    ``list[Bar]`` representation. Providers skip incomplete rows rather
    than raising.
    """

    @classmethod
    @abstractmethod
    def normalize(cls, raw: list[dict[str, Any]]) -> list[Bar]:
        """Normalize raw provider rows into Bar instances.

        Args:
            raw: Provider-specific row dicts.

        Returns:
            List of normalized Bars. Incomplete rows are silently skipped.
        """


class YahooProvider(MarketDataProvider):
    """Yahoo Finance OHLCV normalizer.

    Expects dicts with keys: Date, Open, High, Low, Close, Adj Close, Volume.
    Maps ``Adj Close`` to ``Bar.close``.
    """

    _REQUIRED_YAHOO = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}

    @classmethod
    def normalize(cls, raw: list[dict[str, Any]]) -> list[Bar]:
        bars: list[Bar] = []
        for row in raw:
            if not cls._REQUIRED_YAHOO.issubset(row.keys()):
                continue
            try:
                timestamp = cls._parse_yahoo_date(row["Date"])
                bars.append(
                    Bar(
                        timestamp=timestamp,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Adj Close"]),
                        volume=float(row["Volume"]),
                    )
                )
            except (TypeError, ValueError):
                continue
        return bars

    @staticmethod
    def _parse_yahoo_date(value: str) -> datetime:
        from datetime import datetime, timezone

        # Yahoo dates may be "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(str(value), fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"Unparseable Yahoo date: {value!r}")


class DukascopyProvider(MarketDataProvider):
    """Dukascopy OHLCV normalizer.

    Expects dicts with keys: timestamp, open, high, low, close, volume.
    The timestamp may be an ISO-8601 string or a datetime object.
    """

    _REQUIRED_DUKAS = {"open", "high", "low", "close", "volume"}

    @classmethod
    def normalize(cls, raw: list[dict[str, Any]]) -> list[Bar]:
        bars: list[Bar] = []
        for row in raw:
            if "timestamp" not in row or not cls._REQUIRED_DUKAS.issubset(row.keys()):
                continue
            try:
                timestamp = cls._parse_timestamp(row["timestamp"])
                bars.append(
                    Bar(
                        timestamp=timestamp,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )
            except (TypeError, ValueError):
                continue
        return bars

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        from datetime import datetime, timezone

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
