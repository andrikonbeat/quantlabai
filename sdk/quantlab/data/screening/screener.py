"""Stock screener provider (AlphaVantage TOP_GAINERS_LOSERS backend).

Finviz is intentionally not scraped: it offers no official API and HTML
scraping is fragile. AlphaVantage's free ``TOP_GAINERS_LOSERS`` endpoint
covers the gainers/losers/most-active presets without extra dependencies.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from quantlab.data.fundamental.base import AbstractDataProvider, ProviderError
from quantlab.data.fundamental.rate_limit import TokenBucket

logger = logging.getLogger(__name__)

_ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"
_API_KEY_ENV = "ALPHAVANTAGE_API_KEY"

_PRESETS: dict[str, str] = {
    "gainers": "top_gainers",
    "losers": "top_losers",
    "most_active": "most_actively_traded",
    "most_actively_traded": "most_actively_traded",
}

__all__ = ["StockScreenerProvider"]


class StockScreenerProvider(AbstractDataProvider):
    """Stock screener over the AlphaVantage gainers/losers endpoint.

    The query selects a preset (``gainers`` / ``losers`` / ``most_active``).
    Results are dicts with ``symbol``, ``price``, ``change_pct`` and
    ``volume``. API key comes from the constructor or the
    ``ALPHAVANTAGE_API_KEY`` env var (precedent: ``data_manager.py``
    ``SQCLI_PATH`` handling).
    """

    def __init__(
        self,
        api_key: str | None = None,
        rate_limiter: TokenBucket | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv(_API_KEY_ENV, "")
        self.rate_limiter = rate_limiter or TokenBucket(rate=0.2, capacity=2)
        self.timeout = timeout

    async def fetch(self, query: str, **params: Any) -> dict[str, Any]:
        """Run a screener preset and return ranked symbols.

        Args:
            query: Preset name — ``gainers``, ``losers`` or ``most_active``.
            **params:
                min_price: Drop symbols below this price (default none).
                limit: Maximum symbols to return (default 20).

        Raises:
            ValueError: If query is empty.
            ProviderError: On unknown preset, missing API key, or API failure.
        """
        if query is None or not str(query).strip():
            raise ValueError("query must be a non-empty string")
        preset = str(query).strip().lower()
        if preset not in _PRESETS:
            raise ProviderError(
                f"Unknown screener preset: {preset!r} "
                f"(expected one of {sorted(_PRESETS)})",
                code="SCREENER_PRESET_ERROR",
                details={"query": query},
            )
        if not self.api_key:
            raise ProviderError(
                "AlphaVantage API key missing: pass api_key or set "
                f"{_API_KEY_ENV}",
                code="SCREENER_AUTH_ERROR",
                details={"env_var": _API_KEY_ENV},
            )

        limit: int = int(params.get("limit", 20))
        min_price: float | None = params.get("min_price")
        if min_price is not None:
            min_price = float(min_price)

        url = (
            f"{_ALPHAVANTAGE_URL}?function=TOP_GAINERS_LOSERS"
            f"&apikey={self.api_key}"
        )
        await self.rate_limiter.acquire()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as exc:
            raise ProviderError(
                f"Screener fetch failed for {preset!r}: {exc}",
                code="SCREENER_ERROR",
                details={"query": query},
            ) from exc
        except Exception as exc:
            raise ProviderError(
                f"Screener fetch failed for {preset!r}: {exc}",
                code="SCREENER_ERROR",
                details={"query": query},
            ) from exc

        entries = payload.get(_PRESETS[preset], []) or []
        results: list[dict[str, Any]] = []
        for entry in entries:
            try:
                price = float(str(entry.get("price", "0")).replace(",", ""))
            except (TypeError, ValueError):
                continue
            if min_price is not None and price < min_price:
                continue
            try:
                volume = int(float(str(entry.get("volume", "0")).replace(",", "")))
            except (TypeError, ValueError):
                volume = 0
            results.append(
                {
                    "symbol": str(entry.get("ticker", "")),
                    "price": price,
                    "change_pct": str(entry.get("change_percentage", "")),
                    "volume": volume,
                }
            )
            if len(results) >= limit:
                break
        return {"query": query, "preset": preset, "results": results, "count": len(results)}
