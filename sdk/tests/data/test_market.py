"""WU1 RED tests: Market data normalization (REQ-301).

Covers Bar model round-trip, UTC normalization, adjusted-close mapping for
Yahoo, partial-bar rejection, and empty-input handling for MarketDataProvider.

Strict TDD: written first — FAIL (RED) until market models/providers exist.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quantlab.data.market import Bar, MarketDataProvider, YahooProvider, DukascopyProvider


# ── Bar model ────────────────────────────────────────────────────────────────


class TestBarModel:
    def test_six_field_round_trip(self) -> None:
        """GIVEN a Bar with all six fields
        WHEN model_dump / model_validate round-trips
        THEN every field is preserved exactly.
        """
        bar = Bar(
            timestamp=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc),
            open=1.10,
            high=1.12,
            low=1.09,
            close=1.11,
            volume=1000.0,
        )
        dumped = bar.model_dump()
        restored = Bar.model_validate(dumped)

        assert restored.timestamp == bar.timestamp
        assert restored.open == bar.open
        assert restored.high == bar.high
        assert restored.low == bar.low
        assert restored.close == bar.close
        assert restored.volume == bar.volume

    def test_utc_normalization(self) -> None:
        """GIVEN a naive timestamp or non-UTC tzinfo
        WHEN Bar is constructed
        THEN timestamp is stored in UTC (or accepted as UTC-aware).
        """
        naive = datetime(2024, 1, 2, 0, 0)
        bar = Bar(
            timestamp=naive,
            open=1.10,
            high=1.12,
            low=1.09,
            close=1.11,
            volume=1000.0,
        )
        assert bar.timestamp.tzinfo is not None
        assert bar.timestamp.utcoffset().total_seconds() == 0

    def test_adjusted_close_mapping(self) -> None:
        """GIVEN a Yahoo raw bar with 'adj_close'
        WHEN YahooProvider normalizes it
        THEN the resulting Bar.close equals the adjusted close value
        (not the raw close).
        """
        raw_yahoo = {
            "Date": "2024-01-02",
            "Open": 1.10,
            "High": 1.12,
            "Low": 1.09,
            "Close": 1.15,
            "Adj Close": 1.11,
            "Volume": 1000,
        }
        bars = YahooProvider.normalize([raw_yahoo])
        assert len(bars) == 1
        assert bars[0].close == pytest.approx(1.11)


# ── MarketDataProvider ────────────────────────────────────────────────────────


class TestMarketDataProvider:
    def test_yahoo_normalization(self) -> None:
        """GIVEN raw Yahoo OHLCV rows
        WHEN YahooProvider.normalize is called
        THEN each row becomes a Bar with correct fields and UTC timestamp.
        """
        raw = [
            {
                "Date": "2024-01-02",
                "Open": 1.10,
                "High": 1.12,
                "Low": 1.09,
                "Close": 1.11,
                "Adj Close": 1.11,
                "Volume": 1000,
            }
        ]
        bars = YahooProvider.normalize(raw)
        assert len(bars) == 1
        assert bars[0].open == pytest.approx(1.10)
        assert bars[0].high == pytest.approx(1.12)
        assert bars[0].low == pytest.approx(1.09)
        assert bars[0].close == pytest.approx(1.11)
        assert bars[0].volume == pytest.approx(1000.0)
        assert bars[0].timestamp.tzinfo is not None

    def test_dukascopy_normalization(self) -> None:
        """GIVEN raw Dukascopy OHLCV rows
        WHEN DukascopyProvider.normalize is called
        THEN each row becomes a Bar with correct fields and UTC timestamp.
        """
        raw = [
            {
                "timestamp": "2024-01-02T00:00:00Z",
                "open": 1.10,
                "high": 1.12,
                "low": 1.09,
                "close": 1.11,
                "volume": 1000.0,
            }
        ]
        bars = DukascopyProvider.normalize(raw)
        assert len(bars) == 1
        assert bars[0].open == pytest.approx(1.10)
        assert bars[0].high == pytest.approx(1.12)
        assert bars[0].low == pytest.approx(1.09)
        assert bars[0].close == pytest.approx(1.11)
        assert bars[0].volume == pytest.approx(1000.0)
        assert bars[0].timestamp.tzinfo is not None

    def test_partial_bar_rejection(self) -> None:
        """GIVEN bars where some miss the 'high' field
        WHEN normalization runs
        THEN incomplete bars are skipped and no exception is raised.
        """
        raw = [
            {
                "Date": "2024-01-02",
                "Open": 1.10,
                "High": 1.12,
                "Low": 1.09,
                "Close": 1.11,
                "Adj Close": 1.11,
                "Volume": 1000,
            },
            {
                "Date": "2024-01-03",
                "Open": 1.11,
                # 'High' missing on purpose
                "Low": 1.10,
                "Close": 1.12,
                "Adj Close": 1.12,
                "Volume": 1000,
            },
        ]
        bars = YahooProvider.normalize(raw)
        assert len(bars) == 1
        assert bars[0].high == pytest.approx(1.12)

    def test_empty_input_returns_empty_list(self) -> None:
        """GIVEN empty raw input
        WHEN normalization runs
        THEN an empty list is returned (no exception).
        """
        assert YahooProvider.normalize([]) == []
        assert DukascopyProvider.normalize([]) == []
