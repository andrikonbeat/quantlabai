"""Tests for StockScreenerProvider (T9 task 2.5)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SAMPLE_TOP = {
    "metadata": "Top gainers, losers, and most actively traded US tickers",
    "last_updated": "2024-01-02 16:15:59 US/Eastern",
    "top_gainers": [
        {"ticker": "AAA", "price": "12.5", "change_percentage": "8.1%",
         "change_amount": "0.94", "volume": "1500000"},
        {"ticker": "BBB", "price": "3.2", "change_percentage": "5.4%",
         "change_amount": "0.16", "volume": "800000"},
    ],
    "top_losers": [
        {"ticker": "CCC", "price": "45.0", "change_percentage": "-6.2%",
         "change_amount": "-2.97", "volume": "2300000"},
    ],
    "most_actively_traded": [
        {"ticker": "DDD", "price": "210.0", "change_percentage": "1.1%",
         "change_amount": "2.3", "volume": "9900000"},
    ],
}


@contextlib.contextmanager
def _patched_api(payload: dict = SAMPLE_TOP, status: int = 200):
    import httpx

    response = MagicMock()
    response.json = MagicMock(return_value=payload)
    response.status_code = status
    if status != 200:
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "server error",
                request=AsyncMock(spec=httpx.Request),
                response=AsyncMock(spec=httpx.Response),
            )
        )
    else:
        response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "quantlab.data.screening.screener.httpx.AsyncClient",
        return_value=client,
    ):
        yield client


class TestStockScreenerProvider:
    def test_gainers_preset(self) -> None:
        import asyncio

        from quantlab.data.screening.screener import StockScreenerProvider

        with _patched_api():
            result = asyncio.run(
                StockScreenerProvider(api_key="test-key").fetch("gainers")
            )
        assert result["preset"] == "gainers"
        assert result["count"] == 2
        assert result["results"][0]["symbol"] == "AAA"
        assert result["results"][0]["price"] == 12.5

    def test_min_price_filter(self) -> None:
        import asyncio

        from quantlab.data.screening.screener import StockScreenerProvider

        with _patched_api():
            result = asyncio.run(
                StockScreenerProvider(api_key="k").fetch("gainers", min_price=10.0)
            )
        assert result["count"] == 1
        assert result["results"][0]["symbol"] == "AAA"

    def test_limit(self) -> None:
        import asyncio

        from quantlab.data.screening.screener import StockScreenerProvider

        with _patched_api():
            result = asyncio.run(
                StockScreenerProvider(api_key="k").fetch("gainers", limit=1)
            )
        assert result["count"] == 1

    def test_unknown_preset_raises(self) -> None:
        import asyncio

        from quantlab.data.fundamental.base import ProviderError
        from quantlab.data.screening.screener import StockScreenerProvider

        with (
            _patched_api(),
            pytest.raises(ProviderError),
        ):
            asyncio.run(StockScreenerProvider(api_key="k").fetch("penny_stocks_moon"))

    def test_missing_key_raises_with_env_hint(self) -> None:
        import asyncio
        import os

        from quantlab.data.fundamental.base import ProviderError
        from quantlab.data.screening.screener import StockScreenerProvider

        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ProviderError, match="ALPHAVANTAGE_API_KEY"),
        ):
            asyncio.run(StockScreenerProvider().fetch("gainers"))

    def test_env_key_used(self) -> None:
        import asyncio
        import os

        from quantlab.data.screening.screener import StockScreenerProvider

        with (
            patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "env-key"}),
            _patched_api() as client,
        ):
            asyncio.run(StockScreenerProvider().fetch("losers"))
        requested_url = str(client.get.call_args[0][0])
        assert "env-key" in requested_url

    def test_http_error_raises_provider_error(self) -> None:
        import asyncio

        from quantlab.data.fundamental.base import ProviderError
        from quantlab.data.screening.screener import StockScreenerProvider

        with (
            _patched_api(status=500),
            pytest.raises(ProviderError),
        ):
            asyncio.run(StockScreenerProvider(api_key="k").fetch("gainers"))

    def test_auto_registered(self) -> None:
        from quantlab.data.fundamental.base import AbstractDataProvider
        from quantlab.data.screening.screener import StockScreenerProvider

        assert (
            AbstractDataProvider._registry["StockScreenerProvider"]
            is StockScreenerProvider
        )
