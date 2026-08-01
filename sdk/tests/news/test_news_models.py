"""Strict TDD — RED phase: NewsItem, WebResult models + NewsProvider ABC.

Covers spec scenarios from:
- openspec/specs/news-analysis/spec.md
"""

from __future__ import annotations

import pytest
from datetime import datetime

from quantlab.data.fundamental.base import ProviderError


class TestNewsItem:
    """NewsItem dataclass — creation, sentiment optional."""

    def test_news_item_created(self):
        """GIVEN a valid NewsItem
        WHEN constructed with all fields
        THEN all fields are set correctly.
        """
        from quantlab.data.news.models import NewsItem

        pub_date = datetime(2026, 7, 28, 10, 30, 0)
        item = NewsItem(
            title="AAPL Stock Rises",
            url="https://example.com/aapl",
            source="Yahoo Finance",
            published_date=pub_date,
            summary="AAPL stock rose 2% in trading today.",
            sentiment=0.75,
        )
        assert item.title == "AAPL Stock Rises"
        assert item.url == "https://example.com/aapl"
        assert item.source == "Yahoo Finance"
        assert item.published_date == pub_date
        assert item.summary == "AAPL stock rose 2% in trading today."
        assert item.sentiment == 0.75

    def test_sentiment_optional(self):
        """GIVEN a NewsItem without sentiment
        WHEN constructed
        THEN sentiment is None.
        """
        from quantlab.data.news.models import NewsItem

        item = NewsItem(
            title="No Sentiment",
            url="https://example.com/no-sent",
            source="Google News",
            published_date=datetime(2026, 7, 28),
            summary="No sentiment data available.",
        )
        assert item.sentiment is None
        assert item.title == "No Sentiment"

    def test_deduplication_by_url(self):
        """NewsItem dedup — same URL means same item for dedup purposes."""
        from quantlab.data.news.models import NewsItem

        d = datetime(2026, 7, 28)
        a = NewsItem(title="A", url="https://example.com/a", source="S", published_date=d, summary="Sum A")
        b = NewsItem(title="A (dupe)", url="https://example.com/a", source="S", published_date=d, summary="Sum A")
        # Same URL should be considered duplicate for dedup
        assert a.url == b.url
        urls = {item.url for item in [a, b]}
        assert len(urls) == 1


class TestWebResult:
    """WebResult dataclass — creation, optional fields."""

    def test_web_result_created(self):
        """GIVEN a valid WebResult
        WHEN constructed with all fields
        THEN all fields are set correctly.
        """
        from quantlab.data.news.models import WebResult

        result = WebResult(
            title="AAPL Earnings Q2 2026",
            url="https://duckduckgo.com/?q=aapl+earnings",
            snippet="Apple reported strong Q2 2026 earnings...",
            source="duckduckgo",
        )
        assert result.title == "AAPL Earnings Q2 2026"
        assert result.url == "https://duckduckgo.com/?q=aapl+earnings"
        assert result.snippet == "Apple reported strong Q2 2026 earnings..."
        assert result.source == "duckduckgo"

    def test_web_result_frozen(self):
        """WebResult should be immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError
        from quantlab.data.news.models import WebResult

        result = WebResult(
            title="Test", url="https://example.com", snippet="Snippet", source="test"
        )
        with pytest.raises(FrozenInstanceError):
            result.title = "Changed"


class TestProviderError:
    """ProviderError is importable from news package."""

    def test_provider_error_importable(self):
        """ProviderError should be importable from news package."""
        from quantlab.data.news.base import ProviderError as NewsProviderError
        assert issubclass(NewsProviderError, Exception)

    def test_provider_error_with_code(self):
        """GIVEN a ProviderError with code
        WHEN raised
        THEN code and details are accessible.
        """
        from quantlab.data.news.base import ProviderError as NewsProviderError

        err = NewsProviderError(
            "RSS fetch failed",
            code="RSS_ERROR",
            details={"url": "https://example.com/feed.xml"},
        )
        assert err.code == "RSS_ERROR"
        assert err.details["url"] == "https://example.com/feed.xml"
        assert "RSS fetch failed" in str(err)


class TestNewsProviderABC:
    """NewsProvider ABC — contract enforcement."""

    def test_extends_abstract_data_provider(self):
        """NewsProvider should extend AbstractDataProvider."""
        from quantlab.data.news.base import NewsProvider
        from quantlab.data.fundamental.base import AbstractDataProvider

        assert issubclass(NewsProvider, AbstractDataProvider)

    def test_cannot_instantiate_news_provider(self):
        """NewsProvider should not be instantiable directly."""
        from quantlab.data.news.base import NewsProvider

        with pytest.raises(TypeError, match="abstract"):
            NewsProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_fetch_news(self):
        """GIVEN a subclass without fetch_news
        WHEN instantiated
        THEN TypeError raised.
        """
        from quantlab.data.news.base import NewsProvider

        class Incomplete(NewsProvider):
            async def search_web(self, query: str, **params):  # type: ignore[empty-body]
                ...

        with pytest.raises(TypeError, match="abstract"):
            Incomplete()

    def test_subclass_must_implement_search_web(self):
        """GIVEN a subclass without search_web
        WHEN instantiated
        THEN TypeError raised.
        """
        from quantlab.data.news.base import NewsProvider

        class Incomplete(NewsProvider):
            async def fetch_news(self, query: str, **params):  # type: ignore[empty-body]
                ...

        with pytest.raises(TypeError, match="abstract"):
            Incomplete()

    def test_valid_subclass_instantiates(self):
        """GIVEN a complete NewsProvider subclass
        WHEN instantiated
        THEN no error.
        """
        from quantlab.data.news.base import NewsProvider

        class Concrete(NewsProvider):
            async def fetch_news(self, query: str, **params):
                return []

            async def search_web(self, query: str, **params):
                return []

        provider = Concrete()
        assert isinstance(provider, NewsProvider)

    def test_query_empty_error(self):
        """GIVEN an empty query string
        WHEN fetch_news or search_web is called
        THEN ValueError raised.
        """
        from quantlab.data.news.base import NewsProvider

        class Concrete(NewsProvider):
            async def fetch_news(self, query: str, **params):
                if not query:
                    raise ValueError("query must not be empty")
                return []

            async def search_web(self, query: str, **params):
                if not query:
                    raise ValueError("query must not be empty")
                return []

        provider = Concrete()
        import asyncio

        with pytest.raises(ValueError, match="empty"):
            asyncio.run(provider.fetch_news(""))
        with pytest.raises(ValueError, match="empty"):
            asyncio.run(provider.search_web(""))
        with pytest.raises(ValueError, match="empty"):
            asyncio.run(provider.fetch_news(None))  # type: ignore[arg-type]
