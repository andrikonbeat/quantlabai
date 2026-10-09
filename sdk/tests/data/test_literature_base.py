"""Tests for data/literature/ base package (T9 task 2.1)."""

from __future__ import annotations

from datetime import datetime, UTC

import pytest

from quantlab.data.fundamental.base import AbstractDataProvider


class TestPaperItem:
    def test_fields(self) -> None:
        from quantlab.data.literature.models import PaperItem

        item = PaperItem(
            title="Attention Is All You Need",
            authors=["Vaswani et al."],
            abstract="Transformers...",
            url="https://arxiv.org/abs/1706.03762",
            arxiv_id="1706.03762",
            categories=["cs.CL", "cs.LG"],
            published_at=datetime(2017, 6, 12, tzinfo=UTC),
            source="arxiv",
        )
        assert item.arxiv_id == "1706.03762"
        assert item.categories == ["cs.CL", "cs.LG"]

    def test_frozen(self) -> None:
        from quantlab.data.literature.models import PaperItem

        item = PaperItem(
            title="t", authors=[], abstract="a", url="u",
            arxiv_id=None, categories=[], published_at=None, source="arxiv",
        )
        with pytest.raises(Exception):
            item.title = "changed"  # type: ignore[misc]


class TestLiteratureProvider:
    def test_is_abstract(self) -> None:
        from quantlab.data.literature.base import LiteratureProvider

        with pytest.raises(TypeError):
            LiteratureProvider()  # type: ignore[abstract]

    def test_subclass_auto_registers(self) -> None:
        from quantlab.data.literature.base import LiteratureProvider

        class _DummyLit(LiteratureProvider):
            async def fetch_papers(self, query: str, **params):  # type: ignore[no-untyped-def]
                return []

            async def fetch(self, query: str, **params):  # type: ignore[no-untyped-def]
                return {"query": query, "papers": [], "count": 0}

        assert AbstractDataProvider._registry["_DummyLit"] is _DummyLit

    def test_fetch_delegates_to_fetch_papers(self) -> None:
        import asyncio

        from quantlab.data.literature.base import LiteratureProvider
        from quantlab.data.literature.models import PaperItem

        paper = PaperItem(
            title="t", authors=["a"], abstract="ab", url="u",
            arxiv_id="1", categories=["q-fin"], published_at=None, source="test",
        )

        class _OnePaper(LiteratureProvider):
            async def fetch_papers(self, query: str, **params):  # type: ignore[no-untyped-def]
                return [paper]

        provider = _OnePaper()
        result = asyncio.run(provider.fetch("momentum"))
        assert result["count"] == 1
        assert result["query"] == "momentum"

    def test_fetch_empty_query_raises(self) -> None:
        import asyncio

        from quantlab.data.literature.base import LiteratureProvider

        class _Empty(LiteratureProvider):
            async def fetch_papers(self, query: str, **params):  # type: ignore[no-untyped-def]
                return []

        provider = _Empty()
        with pytest.raises(ValueError):
            asyncio.run(provider.fetch(""))
