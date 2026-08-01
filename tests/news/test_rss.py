"""Tests for RSSNewsProvider using mocked HTTP responses."""

from __future__ import annotations

import pytest

from quantlab.data.news.rss import RSSNewsProvider


class TestRSSNewsProvider:
    async def test_fetch_news_empty_query_raises(self) -> None:
        provider = RSSNewsProvider()
        with pytest.raises(ValueError, match="query must not be empty"):
            await provider.fetch_news("")

    async def test_fetch_news_no_feedparser_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate missing feedparser: the provider guards the import
        # (feedparser = None) and returns an empty list without networking.
        monkeypatch.setattr("quantlab.data.news.rss.feedparser", None)
        provider = RSSNewsProvider()
        result = await provider.fetch_news("EURUSD")
        assert result == []

    async def test_search_web_not_supported(self) -> None:
        provider = RSSNewsProvider()
        with pytest.raises(NotImplementedError):
            await provider.search_web("test")

    async def test_fetch_delegates_to_fetch_news(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = RSSNewsProvider()
        monkeypatch.setattr("quantlab.data.news.rss.feedparser", None)
        result = await provider.fetch("EURUSD")
        assert "articles" in result
        assert result["query"] == "EURUSD"
