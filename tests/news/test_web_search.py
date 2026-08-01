"""Tests for WebSearchProvider."""

from __future__ import annotations

import pytest

from quantlab.data.news.web_search import WebSearchProvider


class TestWebSearchProvider:
    async def test_search_web_empty_query_raises(self) -> None:
        provider = WebSearchProvider()
        with pytest.raises(ValueError, match="query must not be empty"):
            await provider.search_web("")

    async def test_search_web_no_module_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate missing duckduckgo-search: the provider guards the import
        # (DDGS = None) and falls back to an empty result set instead of
        # crashing or hitting the network.
        monkeypatch.setattr("quantlab.data.news.web_search.DDGS", None)
        provider = WebSearchProvider()
        result = await provider.search_web("EURUSD breakout 2026")
        assert result == []

    async def test_fetch_news_not_supported(self) -> None:
        provider = WebSearchProvider()
        with pytest.raises(NotImplementedError):
            await provider.fetch_news("test")

    async def test_fetch_delegates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = WebSearchProvider()
        monkeypatch.setattr("quantlab.data.news.web_search.DDGS", None)
        result = await provider.fetch("EURUSD")
        assert "results" in result
