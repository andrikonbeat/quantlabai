"""Tests for WebSearchProvider."""

from __future__ import annotations

import pytest

from quantlab.data.news.web_search import WebSearchProvider


class TestWebSearchProvider:
    async def test_search_web_empty_query_raises(self) -> None:
        provider = WebSearchProvider()
        with pytest.raises(ValueError, match="query must not be empty"):
            await provider.search_web("")

    async def test_search_web_no_module_returns_empty(self) -> None:
        provider = WebSearchProvider()
        # duckduckgo-search not installed → returns empty list
        result = await provider.search_web("EURUSD breakout 2026")
        assert result == []

    async def test_fetch_news_not_supported(self) -> None:
        provider = WebSearchProvider()
        with pytest.raises(NotImplementedError):
            await provider.fetch_news("test")

    async def test_fetch_delegates(self) -> None:
        provider = WebSearchProvider()
        result = await provider.fetch("EURUSD")
        assert "results" in result
