"""Web search provider — wraps duckduckgo-search for free web search.

Follows the same ``AbstractDataProvider`` pattern with caching and
rate limiting from ``quantlab.data.fundamental``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from quantlab.data.fundamental.cache import SqliteCache
from quantlab.data.fundamental.rate_limit import TokenBucket

from quantlab.data.news.base import NewsProvider, ProviderError
from quantlab.data.news.models import WebResult

logger = logging.getLogger(__name__)

try:
    from duckduckgo_search import DDGS
except ImportError:  # pragma: no cover
    DDGS = None  # type: ignore[assignment]


class WebSearchProvider(NewsProvider):
    """Web search provider wrapping duckduckgo-search.

    Provides free web search without an API key. Results are cached
    with a configurable TTL, and rate-limited with a token bucket.

    Default rate limit: 3 requests/second, burst up to 5.
    Default cache TTL: 600 seconds (10 minutes).

    Args:
        cache: A ``SqliteCache`` instance. Created with
            ``default_ttl=600`` if omitted.
        rate_limiter: A ``TokenBucket`` instance. Created with
            ``rate=3.0, capacity=5`` if omitted.
        default_ttl: Override the default cache TTL (seconds).
    """

    def __init__(
        self,
        cache: SqliteCache | None = None,
        rate_limiter: TokenBucket | None = None,
        default_ttl: int = 600,
    ) -> None:
        self.cache = cache or SqliteCache(default_ttl=default_ttl)
        self.rate_limiter = rate_limiter or TokenBucket(rate=3.0, capacity=5)
        self.default_ttl = default_ttl

    async def search_web(self, query: str, **params: Any) -> list[WebResult]:
        """Search the web for the given query.

        Results are cached per query string. On rate-limit errors, the
        provider retries once; on second failure, ``ProviderError`` is
        raised.

        Args:
            query: Search query string.
            **params: Currently unused; provided for extensibility.

        Returns:
            A list of ``WebResult`` instances.

        Raises:
            ValueError: If query is empty or ``None``.
            ProviderError: On provider-level failures after retry.
        """
        if not query:
            raise ValueError("query must not be empty")

        cache_key = f"web:{query}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return [WebResult(**r) for r in cached]

        await self.rate_limiter.acquire()

        results = await self._do_search(query)
        # Cache as serialisable dicts
        await self.cache.set(
            cache_key,
            [{"title": r.title, "url": r.url, "snippet": r.snippet, "source": r.source}
             for r in results],
            ttl=self.default_ttl,
        )
        return results

    async def _do_search(self, query: str) -> list[WebResult]:
        """Execute the web search, with one retry on failure."""
        try:
            raw = await self._search_ddgs(query)
            return [
                WebResult(
                    title=item.get("title", ""),
                    url=item.get("href", ""),
                    snippet=item.get("body", ""),
                    source="duckduckgo",
                )
                for item in raw
            ]
        except Exception as exc:
            logger.warning("Web search failed (retrying): %s", exc)
            try:
                raw = await self._search_ddgs(query)
                return [
                    WebResult(
                        title=item.get("title", ""),
                        url=item.get("href", ""),
                        snippet=item.get("body", ""),
                        source="duckduckgo",
                    )
                    for item in raw
                ]
            except Exception as exc2:
                raise ProviderError(
                    message=f"Web search failed for '{query}' after retry: {exc2}",
                    code="WEB_SEARCH_ERROR",
                    details={"query": query},
                ) from exc2

    def _search_sync(self, query: str) -> list[dict[str, Any]]:
        """Run the duckduckgo-search text query (sync API)."""
        if DDGS is None:
            return []
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=10))

    async def _search_ddgs(self, query: str) -> list[dict[str, Any]]:
        """Run the duckduckgo-search text query, off the event loop."""
        return await asyncio.to_thread(self._search_sync, query)

    async def fetch_news(self, query: str, **params: Any) -> list:
        """News fetching is not supported by WebSearchProvider.

        Raises:
            NotImplementedError: Always — use ``RSSNewsProvider`` instead.
        """
        raise NotImplementedError(
            "WebSearchProvider does not support news feeds. Use RSSNewsProvider."
        )

    async def fetch(self, query: str, **params: Any) -> dict[str, Any]:
        """Override fetch to delegate to ``search_web``."""
        results = await self.search_web(query, **params)
        return {
            "query": query,
            "results": [r.__dict__ for r in results],
            "count": len(results),
        }
