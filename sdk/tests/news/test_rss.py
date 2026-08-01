"""Strict TDD — RED phase: RSSNewsProvider tests.

Covers spec scenarios from:
- openspec/specs/news-analysis/spec.md
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestRSSNewsProvider:
    """RSSNewsProvider — RSS feed consumption, dedup, error handling."""

    def test_init_defaults(self):
        """GIVEN RSSNewsProvider without args
        WHEN instantiated
        THEN default RSS sources are configured.
        """
        from quantlab.data.news.rss import RSSNewsProvider

        provider = RSSNewsProvider()
        assert len(provider.rss_urls) > 0

    def test_init_custom_sources(self):
        """GIVEN custom RSS URLs
        WHEN instantiated
        THEN custom sources override defaults.
        """
        from quantlab.data.news.rss import RSSNewsProvider

        urls = ["https://example.com/rss"]
        provider = RSSNewsProvider(rss_urls=urls)
        assert provider.rss_urls == urls

    @pytest.mark.asyncio
    async def test_empty_query_raises_error(self):
        """GIVEN empty query string
        WHEN fetch_news() called
        THEN ValueError raised.
        """
        from quantlab.data.news.rss import RSSNewsProvider

        provider = RSSNewsProvider()
        with pytest.raises(ValueError, match="empty"):
            await provider.fetch_news("")
        with pytest.raises(ValueError, match="empty"):
            await provider.fetch_news(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_fetch_news_returns_news_items(self):
        """GIVEN RSSNewsProvider with valid RSS URLs
        WHEN fetch_news("AAPL") called
        THEN articles matching the query are returned as NewsItems.
        """
        from quantlab.data.news.rss import RSSNewsProvider
        from quantlab.data.news.models import NewsItem

        # Mock httpx.AsyncClient.get + feedparser to avoid external deps
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "<rss version='2.0'><channel></channel></rss>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response

        urls = ["https://example.com/finance.rss"]
        provider = RSSNewsProvider(rss_urls=urls)

        def make_feed(entries_list):
            """Create a feedparser-like result with .entries attribute."""
            return SimpleNamespace(entries=[
                SimpleNamespace(
                    title=e["title"],
                    link=e["link"],
                    description=e.get("description", ""),
                    published_parsed=e["published_parsed"],
                    source=SimpleNamespace(title=e.get("source", {}).get("title", "")),
                )
                for e in entries_list
            ])

        feed = make_feed([
            {
                "title": "AAPL Stock Rises on Strong Earnings",
                "link": "https://example.com/aapl-earnings",
                "description": "AAPL shares rose 5% after reporting strong Q2 earnings.",
                "published_parsed": (2026, 7, 28, 10, 0, 0, 1, 209, 0),
                "source": {"title": "Yahoo Finance"},
            },
            {
                "title": "Market Overview: Tech Stocks Rally",
                "link": "https://example.com/tech-rally",
                "description": "Technology stocks rallied across the board.",
                "published_parsed": (2026, 7, 28, 9, 30, 0, 1, 209, 0),
                "source": {"title": "Yahoo Finance"},
            },
        ])

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("quantlab.data.news.rss.feedparser", MagicMock()) as mock_fp:
            mock_fp.parse.return_value = feed
            results = await provider.fetch_news("AAPL")

        assert len(results) >= 1
        assert isinstance(results[0], NewsItem)
        assert "AAPL" in results[0].title
        assert "https://example.com/aapl-earnings" == results[0].url
        assert results[0].source == "Yahoo Finance"
        assert results[0].summary is not None
        assert results[0].published_date is not None

    @pytest.mark.asyncio
    async def test_deduplicates_by_url(self):
        """GIVEN RSS feed with duplicate URL
        WHEN fetch_news() called
        THEN duplicate items are removed.
        """
        from quantlab.data.news.rss import RSSNewsProvider

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "<rss version='2.0'><channel></channel></rss>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response

        urls = ["https://example.com/finance.rss"]
        provider = RSSNewsProvider(rss_urls=urls)

        def make_feed(entries_list):
            return SimpleNamespace(entries=[
                SimpleNamespace(
                    title=e["title"],
                    link=e["link"],
                    description=e.get("description", ""),
                    published_parsed=e["published_parsed"],
                    source=SimpleNamespace(title=e.get("source", {}).get("title", "")),
                )
                for e in entries_list
            ])

        feed = make_feed([
            {
                "title": "AAPL Stock Rises",
                "link": "https://example.com/aapl",
                "description": "AAPL stock rises.",
                "published_parsed": (2026, 7, 28, 10, 0, 0, 1, 209, 0),
                "source": {"title": "Yahoo Finance"},
            },
            {
                "title": "AAPL Stock Rises (duplicate)",
                "link": "https://example.com/aapl",
                "description": "AAPL stock rises again.",
                "published_parsed": (2026, 7, 28, 10, 0, 0, 1, 209, 0),
                "source": {"title": "Yahoo Finance"},
            },
        ])

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("quantlab.data.news.rss.feedparser", MagicMock()) as mock_fp:
            mock_fp.parse.return_value = feed
            results = await provider.fetch_news("AAPL")

        unique_urls = {r.url for r in results}
        assert len(unique_urls) == 1

    @pytest.mark.asyncio
    async def test_rss_feed_unavailable_continues(self):
        """GIVEN an RSS feed that returns 500
        WHEN fetch_news() called
        THEN the provider skips that source and continues with others.
        """
        from quantlab.data.news.rss import RSSNewsProvider

        # First URL fails with HTTP 500
        failing_response = AsyncMock()
        failing_response.status_code = 500
        failing_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 error", request=MagicMock(), response=MagicMock()
        )

        # Second URL succeeds
        good_response = AsyncMock()
        good_response.status_code = 200
        good_response.text = "<rss version='2.0'><channel></channel></rss>"
        good_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()

        async def get_side_effect(url, *a, **kw):
            if "failing" in str(url):
                return failing_response
            return good_response

        mock_client.__aenter__.return_value.get = AsyncMock(side_effect=get_side_effect)

        # Use SimpleNamespace for feed entries (mimics feedparser's object interface)
        def make_feed(entries_list):
            return SimpleNamespace(entries=[
                SimpleNamespace(
                    title=e["title"],
                    link=e["link"],
                    description=e.get("description", ""),
                    published_parsed=e["published_parsed"],
                    source=SimpleNamespace(title=e.get("source", {}).get("title", "")),
                )
                for e in entries_list
            ])

        good_feed = make_feed([
            {
                "title": "AAPL Good",
                "link": "https://example.com/aapl-good",
                "description": "AAPL is good.",
                "published_parsed": (2026, 7, 28, 10, 0, 0, 1, 209, 0),
                "source": {"title": "Finance"},
            },
        ])

        urls = ["https://example.com/failing.rss", "https://example.com/good.rss"]
        provider = RSSNewsProvider(rss_urls=urls)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("quantlab.data.news.rss.feedparser", MagicMock()) as mock_fp:
            mock_fp.parse.return_value = good_feed
            results = await provider.fetch_news("AAPL")

        assert len(results) == 1
        assert results[0].title == "AAPL Good"

    @pytest.mark.asyncio
    async def test_rss_feed_timeout_continues(self):
        """GIVEN an RSS feed that times out
        WHEN fetch_news() called
        THEN the provider skips that source and continues.
        """
        from quantlab.data.news.rss import RSSNewsProvider

        good_response = AsyncMock()
        good_response.status_code = 200
        good_response.text = "<rss version='2.0'><channel></channel></rss>"
        good_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()

        async def get_side_effect(url, *a, **kw):
            if "timeout" in str(url):
                raise httpx.TimeoutException("Timeout", request=MagicMock())
            return good_response

        mock_client.__aenter__.return_value.get = AsyncMock(side_effect=get_side_effect)

        def make_feed(entries_list):
            return SimpleNamespace(entries=[
                SimpleNamespace(
                    title=e["title"],
                    link=e["link"],
                    description=e.get("description", ""),
                    published_parsed=e["published_parsed"],
                    source=SimpleNamespace(title=e.get("source", {}).get("title", "")),
                )
                for e in entries_list
            ])

        good_feed = make_feed([
            {
                "title": "Working Article",
                "link": "https://example.com/working",
                "description": "Working article.",
                "published_parsed": (2026, 7, 28, 10, 0, 0, 1, 209, 0),
                "source": {"title": "Finance"},
            },
        ])

        urls = ["https://example.com/timeout.rss", "https://example.com/good.rss"]
        provider = RSSNewsProvider(rss_urls=urls)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("quantlab.data.news.rss.feedparser", MagicMock()) as mock_fp:
            mock_fp.parse.return_value = good_feed
            results = await provider.fetch_news("AAPL")

        assert len(results) == 1
        assert results[0].title == "Working Article"
