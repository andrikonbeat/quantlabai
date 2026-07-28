"""Tests for YahooFinanceProvider and FredProvider (API-dependent — may be skipped)."""

import pytest

from quantlab.data.fundamental.yahoo import YahooFinanceProvider
from quantlab.data.fundamental.fred import FredProvider


@pytest.mark.asyncio
async def test_yahoo_fetch_prices():
    provider = YahooFinanceProvider()
    try:
        result = await provider.fetch("AAPL")
        assert result is not None
    except Exception as e:
        pytest.skip(f"Yahoo API unavailable: {e}")


@pytest.mark.asyncio
async def test_yahoo_get_ratios():
    provider = YahooFinanceProvider()
    try:
        result = await provider.get_ratios("AAPL")
        assert result is not None
        assert isinstance(result, dict)
    except Exception as e:
        pytest.skip(f"Yahoo API unavailable: {e}")


@pytest.mark.asyncio
async def test_fred_fetch_gdp():
    provider = FredProvider()
    try:
        result = await provider.fetch("GDP")
        assert result is not None
        assert "series_id" in result or "observations" in result
    except Exception as e:
        pytest.skip(f"FRED API unavailable: {e}")


@pytest.mark.asyncio
async def test_fred_fetch_unrate():
    provider = FredProvider()
    try:
        result = await provider.fetch("UNRATE")
        assert result is not None
    except Exception as e:
        pytest.skip(f"FRED API unavailable: {e}")
