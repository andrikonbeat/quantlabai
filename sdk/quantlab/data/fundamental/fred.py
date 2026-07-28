"""FRED economic data provider using pandas-datareader."""

from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd
from pandas_datareader import data as pdr_data

from quantlab.data.fundamental.base import AbstractDataProvider, ProviderError
from quantlab.data.fundamental.cache import SqliteCache
from quantlab.data.fundamental.rate_limit import TokenBucket


class FredProvider(AbstractDataProvider):
    """Economic data provider for FRED (Federal Reserve Economic Data).

    Retrieves series such as GDP, UNRATE, and CPIAUCSL via
    ``pandas-datareader``. All synchronous calls are offloaded to a
    thread pool.

    Default rate limit: 10 requests/second, burst up to 20.
    Default cache TTL: 3600 seconds (1 hour).

    Args:
        cache: A ``SqliteCache`` instance. Created with
            ``default_ttl=3600`` if omitted.
        rate_limiter: A ``TokenBucket`` instance. Created with
            ``rate=10.0, capacity=20`` if omitted.
        default_ttl: Override the default cache TTL (seconds).
    """

    def __init__(
        self,
        cache: SqliteCache | None = None,
        rate_limiter: TokenBucket | None = None,
        default_ttl: int = 3600,
    ) -> None:
        self.cache = cache or SqliteCache(default_ttl=default_ttl)
        self.rate_limiter = rate_limiter or TokenBucket(rate=10.0, capacity=20)
        self.default_ttl = default_ttl

    async def fetch(self, query: str, **params: Any) -> dict[str, Any]:
        """Fetch an economic series from FRED.

        Args:
            query: FRED series ID (e.g. ``"GDP"``, ``"UNRATE"``,
                ``"CPIAUCSL"``).
            **params:
                start: Start date string (``YYYY-MM-DD``). Optional.
                end:   End date string (``YYYY-MM-DD``). Optional.

        Returns:
            A dictionary with keys ``series_id``, ``observations`` (list of
            ``{"date": …, "value": …}`` dicts), and ``latest`` (the most
            recent observation).

        Raises:
            ProviderError: On any network or API failure.
        """
        series_id = query.upper()
        start = params.get("start")
        end = params.get("end")

        cache_key = f"fred:{series_id}:{start or ''}:{end or ''}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        await self.rate_limiter.acquire()

        try:
            data = await asyncio.to_thread(self._fetch_sync, series_id, start, end)
        except Exception as exc:
            raise ProviderError(
                message=f"FRED fetch failed for {series_id}: {exc}",
                code="FRED_ERROR",
                details={"series_id": series_id, "start": start, "end": end},
            ) from exc

        await self.cache.set(cache_key, data, ttl=self.default_ttl)
        return data

    def _fetch_sync(
        self,
        series_id: str,
        start: str | None,
        end: str | None,
    ) -> dict[str, Any]:
        """Synchronous pandas-datareader call, run in a thread pool."""
        kwargs: dict[str, Any] = {}
        if start:
            kwargs["start"] = start
        if end:
            kwargs["end"] = end

        df = pdr_data.DataReader(series_id, "fred", **kwargs)

        observations: list[dict[str, Any]] = []
        for date, row in df.iterrows():
            value = row.iloc[0]
            observations.append({
                "date": str(date.date()),
                "value": float(value) if pd.notna(value) else None,
            })

        return {
            "series_id": series_id,
            "observations": observations,
            "latest": observations[-1] if observations else None,
        }
