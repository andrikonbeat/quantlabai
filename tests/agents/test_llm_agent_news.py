"""Tests for news provider integration (Tasks 1.1-3.1 of web-research-for-llm-agent).

Covers:
- Lazy-init singleton pattern for WebSearchProvider and RSSNewsProvider
- fetch_data() populates news_data from both providers
- Graceful degradation when providers fail
- build_prompt() includes URLs in news articles
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from quantlab.agents.llm_research_agent import LLMResearchAgent
from quantlab.data.news.models import NewsItem, WebResult


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def agent() -> LLMResearchAgent:
    return LLMResearchAgent()


# ── Task 1.2/1.3: Lazy-init singleton for providers ──────────────────────────


class TestProviderLazyInit:
    """Tasks 1.2-1.3: Instance vars + lazy-init singleton methods."""

    def test_web_search_var_none_initially(self, agent: LLMResearchAgent) -> None:
        """_web_search is None on a fresh instance."""
        # RED: attribute doesn't exist yet → will fail with AttributeError
        assert agent._web_search is None

    def test_rss_news_var_none_initially(self, agent: LLMResearchAgent) -> None:
        """_rss_news is None on a fresh instance."""
        # RED: attribute doesn't exist yet → will fail with AttributeError
        assert agent._rss_news is None

    def test_get_web_search_returns_web_search_provider(
        self, agent: LLMResearchAgent
    ) -> None:
        """_get_web_search() returns a WebSearchProvider-like instance."""
        provider = agent._get_web_search()
        # Check for the key interface method rather than type
        assert hasattr(provider, "search_web")

    def test_get_rss_news_returns_rss_provider(
        self, agent: LLMResearchAgent
    ) -> None:
        """_get_rss_news() returns an RSSNewsProvider-like instance."""
        provider = agent._get_rss_news()
        assert hasattr(provider, "fetch_news")

    def test_get_web_search_singleton(self, agent: LLMResearchAgent) -> None:
        """Repeated calls to _get_web_search() return the same instance."""
        p1 = agent._get_web_search()
        p2 = agent._get_web_search()
        assert p1 is p2

    def test_get_rss_news_singleton(self, agent: LLMResearchAgent) -> None:
        """Repeated calls to _get_rss_news() return the same instance."""
        p1 = agent._get_rss_news()
        p2 = agent._get_rss_news()
        assert p1 is p2


# ── Task 2.1/2.2: fetch_data wires providers into news_data ──────────────────


def _make_web_results(n: int = 2) -> list[WebResult]:
    return [
        WebResult(
            title=f"Result {i}",
            url=f"https://example.com/{i}",
            snippet=f"Snippet for result {i}",
            source="duckduckgo",
        )
        for i in range(n)
    ]


def _make_news_items(n: int = 2) -> list[NewsItem]:
    return [
        NewsItem(
            title=f"News {i}",
            url=f"https://news.example.com/{i}",
            source="Yahoo Finance",
            published_date=datetime(2026, 7, 30),
            summary=f"Summary for news {i}",
        )
        for i in range(n)
    ]


class TestFetchDataNews:
    """Task 2.1-2.2: fetch_data() populates news_data from providers."""

    @pytest.mark.asyncio
    async def test_fetch_data_calls_web_search(self, agent: LLMResearchAgent) -> None:
        """fetch_data() calls search_web with market_context market."""
        web_results = _make_web_results()
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=web_results)
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_rss.fetch_news = AsyncMock(return_value=[])
                mock_get_rss.return_value = mock_rss

                data = await agent.fetch_data(
                    objective="find tech opportunities",
                    market_context={"market": "technology sector", "ticker": "AAPL"},
                )

        mock_web.search_web.assert_called_once()
        assert data["news"] is not None

    @pytest.mark.asyncio
    async def test_fetch_data_calls_rss_news_with_ticker(
        self, agent: LLMResearchAgent
    ) -> None:
        """fetch_data() calls fetch_news(ticker) when ticker is non-empty."""
        news_items = _make_news_items()
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=[])
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_rss.fetch_news = AsyncMock(return_value=news_items)
                mock_get_rss.return_value = mock_rss

                data = await agent.fetch_data(
                    objective="test",
                    market_context={"ticker": "AAPL"},
                )

        mock_rss.fetch_news.assert_called_once_with("AAPL")
        assert len(data["news"]) == 2

    @pytest.mark.asyncio
    async def test_both_providers_contribute_to_news_data(
        self, agent: LLMResearchAgent
    ) -> None:
        """When both providers return data, news_data contains merged results."""
        web_results = _make_web_results(2)
        news_items = _make_news_items(3)

        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=web_results)
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_rss.fetch_news = AsyncMock(return_value=news_items)
                mock_get_rss.return_value = mock_rss

                data = await agent.fetch_data(
                    objective="test",
                    market_context={"market": "tech", "ticker": "AAPL"},
                )

        assert len(data["news"]) == 5

    @pytest.mark.asyncio
    async def test_news_items_have_expected_keys(
        self, agent: LLMResearchAgent
    ) -> None:
        """Each news entry dict has title, url, summary, source keys."""
        web_results = _make_web_results(1)
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=web_results)
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_rss.fetch_news = AsyncMock(return_value=[])
                mock_get_rss.return_value = mock_rss

                data = await agent.fetch_data(
                    objective="test",
                    market_context={"market": "tech"},
                )

        if data["news"]:
            entry = data["news"][0]
            assert "title" in entry
            assert "url" in entry
            assert "summary" in entry
            assert "source" in entry

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_web_search_failure(
        self, agent: LLMResearchAgent
    ) -> None:
        """When search_web raises, fetch_data still succeeds and news may be from RSS only."""
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(
                side_effect=RuntimeError("Web search down")
            )
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_rss.fetch_news = AsyncMock(return_value=[])
                mock_get_rss.return_value = mock_rss

                # Should NOT raise
                data = await agent.fetch_data(
                    objective="test",
                    market_context={"market": "tech"},
                )
                assert "news" in data
                assert isinstance(data["news"], list)

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_rss_failure(
        self, agent: LLMResearchAgent
    ) -> None:
        """When fetch_news raises, fetch_data still succeeds."""
        web_results = _make_web_results(2)
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=web_results)
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_rss.fetch_news = AsyncMock(
                    side_effect=RuntimeError("RSS down")
                )
                mock_get_rss.return_value = mock_rss

                data = await agent.fetch_data(
                    objective="test",
                    market_context={"ticker": "AAPL"},
                )
                # Should still have web results
                assert len(data["news"]) == 2

    @pytest.mark.asyncio
    async def test_no_ticker_skips_rss_news(
        self, agent: LLMResearchAgent
    ) -> None:
        """When ticker is empty, fetch_news is not called."""
        web_results = _make_web_results(1)
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=web_results)
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_get_rss.return_value = mock_rss

                data = await agent.fetch_data(
                    objective="test",
                    market_context={"market": "technology sector"},
                )

                mock_rss.fetch_news.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_market_context_graceful(
        self, agent: LLMResearchAgent
    ) -> None:
        """Empty market_context should not crash — fundamental/macro still fetched."""
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=[])
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_get_rss.return_value = mock_rss

                data = await agent.fetch_data(
                    objective="test",
                    market_context=None,
                )
                assert "news" in data
                assert "fundamental" in data
                assert "macro" in data

    @pytest.mark.asyncio
    async def test_market_query_uses_context_market(
        self, agent: LLMResearchAgent
    ) -> None:
        """market_query should be context.get('market', objective), preferring market."""
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=[])
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_rss.fetch_news = AsyncMock(return_value=[])
                mock_get_rss.return_value = mock_rss

                await agent.fetch_data(
                    objective="find tech opportunities",
                    market_context={"market": "AI sector"},
                )

                # Should have used "AI sector" (from context.market) not objective
                mock_web.search_web.assert_called_once_with("AI sector")

    @pytest.mark.asyncio
    async def test_market_query_falls_back_to_objective(
        self, agent: LLMResearchAgent
    ) -> None:
        """When context has no 'market', fall back to objective."""
        with patch.object(agent, "_get_web_search") as mock_get_web:
            mock_web = AsyncMock()
            mock_web.search_web = AsyncMock(return_value=[])
            mock_get_web.return_value = mock_web

            with patch.object(agent, "_get_rss_news") as mock_get_rss:
                mock_rss = AsyncMock()
                mock_rss.fetch_news = AsyncMock(return_value=[])
                mock_get_rss.return_value = mock_rss

                await agent.fetch_data(
                    objective="generic objective",
                    market_context={"ticker": "AAPL"},
                )

                mock_web.search_web.assert_called_once_with("generic objective")


# ── Task 3.1: URL visibility in build_prompt ─────────────────────────────────


class TestBuildPromptNewsURLs:
    """Task 3.1: build_prompt() includes URLs in articles_text."""

    def test_articles_text_includes_url(self, agent: LLMResearchAgent) -> None:
        """When news_data has entries with urls, the formatted text includes them."""
        data: dict[str, Any] = {
            "ticker": "AAPL",
            "fundamental": {"ticker": "AAPL"},
            "macro": {},
            "news": [
                {
                    "title": "Apple Hits Record High",
                    "url": "https://finance.yahoo.com/aapl",
                    "summary": "Apple stock reached new heights",
                    "source": "Yahoo Finance",
                },
            ],
        }
        prompt = agent.build_prompt("test objective", data)
        # The format string should include the URL in the articles_text
        assert "https://finance.yahoo.com/aapl" in prompt
        assert "Apple Hits Record High" in prompt
        assert "Apple stock reached new heights" in prompt

    def test_articles_without_url_shows_no_url(self, agent: LLMResearchAgent) -> None:
        """When news_data entries have no url, handle gracefully (empty string)."""
        data: dict[str, Any] = {
            "ticker": "AAPL",
            "fundamental": {"ticker": "AAPL"},
            "macro": {},
            "news": [
                {
                    "title": "News Without URL",
                    "url": "",
                    "summary": "Some content",
                    "source": "Test",
                },
            ],
        }
        prompt = agent.build_prompt("test objective", data)
        # Should contain the title but URL should be empty
        assert "News Without URL" in prompt
        assert "Some content" in prompt
        # The format should still handle it without error

    def test_empty_news_skips_section(self, agent: LLMResearchAgent) -> None:
        """When news_data is empty, the news section is not included."""
        data: dict[str, Any] = {
            "ticker": "AAPL",
            "fundamental": {"ticker": "AAPL"},
            "macro": {},
            "news": [],
        }
        prompt = agent.build_prompt("test objective", data)
        # If news section were included, it would have "No news articles available"
        assert "No news articles available" not in prompt
