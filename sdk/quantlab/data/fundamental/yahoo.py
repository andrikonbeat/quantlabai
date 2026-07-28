"""Yahoo Finance data provider using yfinance."""

from __future__ import annotations

import asyncio
from typing import Any

import yfinance as yf

from quantlab.data.fundamental.base import AbstractDataProvider, ProviderError
from quantlab.data.fundamental.cache import SqliteCache
from quantlab.data.fundamental.rate_limit import TokenBucket


class YahooFinanceProvider(AbstractDataProvider):
    """Fundamental data provider for Yahoo Finance.

    Fetches OHLCV prices, company info, and financial ratios via the
    ``yfinance`` library. All synchronous library calls are offloaded
    to a thread pool so they do not block the event loop.

    Default rate limit: 5 requests/second, burst up to 10.
    Default cache TTL: 300 seconds (5 minutes).

    Args:
        cache: A ``SqliteCache`` instance. Created with ``default_ttl=300``
            if omitted.
        rate_limiter: A ``TokenBucket`` instance. Created with
            ``rate=5.0, capacity=10`` if omitted.
        default_ttl: Override the default cache TTL (seconds).
    """

    def __init__(
        self,
        cache: SqliteCache | None = None,
        rate_limiter: TokenBucket | None = None,
        default_ttl: int = 300,
    ) -> None:
        self.cache = cache or SqliteCache(default_ttl=default_ttl)
        self.rate_limiter = rate_limiter or TokenBucket(rate=5.0, capacity=10)
        self.default_ttl = default_ttl

    async def fetch(self, query: str, **params: Any) -> dict[str, Any]:
        """Fetch stock data from Yahoo Finance.

        Args:
            query: Ticker symbol (e.g. ``"AAPL"``).
            **params:
                start: Start date string (``YYYY-MM-DD``). Optional.
                end:   End date string (``YYYY-MM-DD``). Optional.

        Returns:
            A dictionary with keys ``ticker``, ``prices`` (list of OHLCV
            dicts), ``fundamentals``, and ``info`` (raw ``yfinance`` info).

        Raises:
            ProviderError: On any network or API failure.
        """
        ticker = query.upper()
        start = params.get("start")
        end = params.get("end")

        cache_key = f"yahoo:{ticker}:{start or ''}:{end or ''}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        await self.rate_limiter.acquire()

        try:
            data = await asyncio.to_thread(self._fetch_sync, ticker, start, end)
        except Exception as exc:
            raise ProviderError(
                message=f"Yahoo Finance fetch failed for {ticker}: {exc}",
                code="YAHOO_ERROR",
                details={"ticker": ticker, "start": start, "end": end},
            ) from exc

        await self.cache.set(cache_key, data, ttl=self.default_ttl)
        return data

    def _fetch_sync(
        self,
        ticker: str,
        start: str | None,
        end: str | None,
    ) -> dict[str, Any]:
        """Synchronous yfinance call, run in a thread pool."""
        ticker_obj = yf.Ticker(ticker)

        hist_kwargs: dict[str, Any] = {}
        if start:
            hist_kwargs["start"] = start
        if end:
            hist_kwargs["end"] = end

        hist = ticker_obj.history(**hist_kwargs)
        info = ticker_obj.info or {}

        prices = []
        for date, row in hist.iterrows():
            prices.append({
                "date": str(date.date()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            })

        fundamentals = {
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": info.get("dividendYield"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

        return {
            "ticker": ticker,
            "prices": prices,
            "fundamentals": fundamentals,
            "info": info,
        }

    async def get_ratios(self, ticker: str) -> dict[str, Any]:
        """Fetch key financial ratios for a ticker.

        Convenience method that extracts P/E, P/B, ROE, ROA, and
        Debt/Equity from the cached/retrieved data.
        """
        data = await self.fetch(ticker)
        info = data.get("info", {})
        return {
            "ticker": ticker,
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
        }
