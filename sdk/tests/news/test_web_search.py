"""Strict TDD — RED phase: WebSearchProvider tests.

Covers spec scenarios from:
- openspec/specs/news-analysis/spec.md
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestWebSearchProvider:
    """WebSearchProvider — duckduckgo-search wrapper, rate limiting."""

    def test_init_defaults(self):
        """GIVEN WebSearchProvider without args
        WHEN instantiated
        THEN default cache and rate limiter are configured.
        """
        from quantlab.data.news.web_search import WebSearchProvider

        provider = WebSearchProvider()
        assert provider.rate_limiter is not None
        assert provider.cache is not None

    @pytest.mark.asyncio
    async def test_empty_query_raises_error(self):
        """GIVEN empty query string
        WHEN search_web() called
        THEN ValueError raised.
        """
        from quantlab.data.news.web_search import WebSearchProvider

        provider = WebSearchProvider()
        with pytest.raises(ValueError, match="empty"):
            await provider.search_web("")
        with pytest.raises(ValueError, match="empty"):
            await provider.search_web(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_search_web_returns_results(self):
        """GIVEN WebSearchProvider
        WHEN search_web('AAPL earnings Q2 2026') called
        THEN a list of WebResult is returned with title, url, snippet, source.
        """
        from quantlab.data.news.web_search import WebSearchProvider
        from quantlab.data.news.models import WebResult

        provider = WebSearchProvider()

        # Mock _search_ddgs to return dicts like real DDGS would
        async def fake_search_ddgs(query):
            return [
                {"title": "AAPL Earnings Q2 2026 - Apple Reports Strong Results",
                 "href": "https://example.com/aapl-earnings",
                 "body": "Apple reported revenue of $124B for Q2 2026..."},
                {"title": "Apple Stock Surges on Earnings Beat",
                 "href": "https://example.com/aapl-surge",
                 "body": "AAPL shares jumped 8% after hours..."},
            ]

        # Direct assignment — no mock complexity
        await provider.cache.clear()
        original = provider._search_ddgs
        provider._search_ddgs = fake_search_ddgs
        try:
            results = await provider.search_web("AAPL earnings Q2 2026")
        finally:
            provider._search_ddgs = original

        assert len(results) == 2
        for r in results:
            assert isinstance(r, WebResult)
            assert r.title
            assert r.url
            assert r.snippet
            assert r.source == "duckduckgo"

    @pytest.mark.asyncio
    async def test_rate_limit_retry_then_raise(self):
        """GIVEN duckduckgo-search rate limits are hit
        WHEN search_web() called
        THEN the provider waits and retries once AND raises ProviderError on second failure.
        """
        from quantlab.data.news.base import ProviderError as NewsProviderError
        from quantlab.data.news.web_search import WebSearchProvider

        provider = WebSearchProvider()
        await provider.cache.clear()

        async def always_fails(query):
            raise Exception("Rate limit exceeded (500)")

        original = provider._search_ddgs
        provider._search_ddgs = always_fails
        try:
            with pytest.raises(NewsProviderError, match="search failed"):
                await provider.search_web("AAPL")
        finally:
            provider._search_ddgs = original

    @pytest.mark.asyncio
    async def test_cache_returns_cached(self):
        """GIVEN a previously fetched query within cache TTL
        WHEN search_web() called again
        THEN the cached response is returned AND no external request is made.
        """
        from quantlab.data.news.web_search import WebSearchProvider
        from quantlab.data.news.models import WebResult

        provider = WebSearchProvider()

        call_count = 0

        async def fake_search_ddgs(query):
            nonlocal call_count
            call_count += 1
            return [
                {"title": "AAPL News",
                 "href": "https://example.com/aapl",
                 "body": "AAPL news body"},
            ]

        original = provider._search_ddgs
        provider._search_ddgs = fake_search_ddgs
        try:
            # First call — populates cache
            results1 = await provider.search_web("AAPL cached test")
            assert len(results1) == 1
            assert call_count == 1

            # Second call — should use cache
            results2 = await provider.search_web("AAPL cached test")
            assert len(results2) == 1
            assert results2[0].title == "AAPL News"
            assert call_count == 1  # Not called again — cache hit
        finally:
            provider._search_ddgs = original
