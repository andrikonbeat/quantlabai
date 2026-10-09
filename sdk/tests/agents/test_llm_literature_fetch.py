"""Tests for literature/screener integration in fetch_data (T9 task 2.6)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from quantlab.agents.llm_research_agent import LLMResearchAgent
from quantlab.data.literature.models import PaperItem


def _paper(title: str) -> PaperItem:
    return PaperItem(
        title=title, authors=["a"], abstract="ab", url=f"https://x.example/{title}",
        arxiv_id=None, categories=["q-fin"], published_at=None, source="test",
    )


class _StubPapers:
    def __init__(self, papers, fail: bool = False):
        self._papers = papers
        self._fail = fail

    async def fetch_papers(self, query: str, **params):
        if self._fail:
            raise RuntimeError("papers down")
        return self._papers


class _StubScreener:
    def __init__(self, payload=None, fail: bool = False):
        self._payload = payload or {"query": "gainers", "preset": "gainers",
                                    "results": [{"symbol": "AAA"}], "count": 1}
        self._fail = fail

    async def fetch(self, query: str, **params):
        if self._fail:
            raise RuntimeError("screener down")
        return self._payload


class TestFetchDataLiterature:
    def test_includes_literature_and_screener(self) -> None:
        agent = LLMResearchAgent()
        with (
            patch.object(LLMResearchAgent, "_get_yahoo", side_effect=RuntimeError("offline")),
            patch.object(LLMResearchAgent, "_get_fred", side_effect=RuntimeError("offline")),
            patch.object(LLMResearchAgent, "_get_web_search", return_value=None),
            patch.object(
                LLMResearchAgent, "_get_papers",
                return_value=_StubPapers([_paper("p1"), _paper("p2")]),
            ),
            patch.object(
                LLMResearchAgent, "_get_blogs",
                return_value=_StubPapers([_paper("b1")]),
            ),
            patch.object(
                LLMResearchAgent, "_get_screener", return_value=_StubScreener()
            ),
        ):
            data = asyncio.run(agent.fetch_data("momentum"))

        assert len(data["literature"]) == 3
        assert data["literature"][0]["title"] == "p1"
        assert data["screener"]["results"][0]["symbol"] == "AAA"

    def test_failing_provider_isolated(self) -> None:
        agent = LLMResearchAgent()
        with (
            patch.object(LLMResearchAgent, "_get_yahoo", side_effect=RuntimeError("offline")),
            patch.object(LLMResearchAgent, "_get_fred", side_effect=RuntimeError("offline")),
            patch.object(LLMResearchAgent, "_get_web_search", return_value=None),
            patch.object(
                LLMResearchAgent, "_get_papers", return_value=_StubPapers([], fail=True)
            ),
            patch.object(
                LLMResearchAgent, "_get_blogs",
                return_value=_StubPapers([_paper("b1")]),
            ),
            patch.object(
                LLMResearchAgent, "_get_screener",
                return_value=_StubScreener(fail=True),
            ),
        ):
            data = asyncio.run(agent.fetch_data("momentum"))  # must not raise

        assert len(data["literature"]) == 1  # blogs survived
        assert data["screener"] == {}

    def test_unavailable_providers_degrade(self) -> None:
        agent = LLMResearchAgent()
        with (
            patch.object(LLMResearchAgent, "_get_yahoo", side_effect=RuntimeError("offline")),
            patch.object(LLMResearchAgent, "_get_fred", side_effect=RuntimeError("offline")),
            patch.object(LLMResearchAgent, "_get_web_search", return_value=None),
            patch.object(LLMResearchAgent, "_get_papers", return_value=None),
            patch.object(LLMResearchAgent, "_get_blogs", return_value=None),
            patch.object(LLMResearchAgent, "_get_screener", return_value=None),
        ):
            data = asyncio.run(agent.fetch_data("momentum"))

        assert data["literature"] == []
        assert data["screener"] == {}

    def test_parallel_execution(self) -> None:
        """Papers and blogs fetches overlap in time (asyncio.gather)."""
        entered_a = asyncio.Event()
        entered_b = asyncio.Event()

        class _GateA:
            async def fetch_papers(self, query: str, **params):
                entered_a.set()
                await asyncio.wait_for(entered_b.wait(), timeout=5.0)
                return [_paper("a")]

        class _GateB:
            async def fetch_papers(self, query: str, **params):
                entered_b.set()
                await asyncio.wait_for(entered_a.wait(), timeout=5.0)
                return [_paper("b")]

        agent = LLMResearchAgent()
        with (
            patch.object(LLMResearchAgent, "_get_yahoo", side_effect=RuntimeError("offline")),
            patch.object(LLMResearchAgent, "_get_fred", side_effect=RuntimeError("offline")),
            patch.object(LLMResearchAgent, "_get_web_search", return_value=None),
            patch.object(LLMResearchAgent, "_get_papers", return_value=_GateA()),
            patch.object(LLMResearchAgent, "_get_blogs", return_value=_GateB()),
            patch.object(LLMResearchAgent, "_get_screener", return_value=None),
        ):
            # Sequential execution would deadlock here (A waits for B forever).
            data = asyncio.run(agent.fetch_data("momentum"))

        assert {p["title"] for p in data["literature"]} == {"a", "b"}
