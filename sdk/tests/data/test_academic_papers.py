"""Tests for AcademicPapersProvider (T9 task 2.2)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <title>Attention Is All You Need</title>
    <summary>We propose the Transformer.</summary>
    <author><name>Vaswani, Ashish</name></author>
    <author><name>Shazeer, Noam</name></author>
    <published>2017-06-12T00:00:00Z</published>
    <category term="cs.CL" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Mean Reversion in Crypto Markets</title>
    <summary>We study RSI signals.</summary>
    <author><name>Doe, Jane</name></author>
    <published>2024-01-02T00:00:00Z</published>
    <category term="q-fin.CP" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
"""


@contextlib.contextmanager
def _patched_client(text: str = SAMPLE_ATOM, status: int = 200):
    """Patch httpx.AsyncClient with a canned Atom response; yield the client."""
    import httpx

    response = AsyncMock()
    response.text = text
    response.status_code = status
    if status != 200:
        # raise_for_status is synchronous in real httpx
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "server error",
                request=AsyncMock(spec=httpx.Request),
                response=AsyncMock(spec=httpx.Response),
            )
        )
    else:
        response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "quantlab.data.literature.papers.httpx.AsyncClient",
        return_value=client,
    ):
        yield client


class TestAcademicPapersProvider:
    def test_parses_arxiv_feed(self) -> None:
        import asyncio

        from quantlab.data.literature.papers import AcademicPapersProvider

        with _patched_client():
            papers = asyncio.run(
                AcademicPapersProvider().fetch_papers("transformer")
            )

        assert len(papers) == 2
        first = papers[0]
        assert first.title == "Attention Is All You Need"
        assert first.arxiv_id == "1706.03762"
        assert "Vaswani, Ashish" in first.authors
        assert set(first.categories) == {"cs.CL", "cs.LG"}
        assert first.source == "arxiv"
        assert first.url == "http://arxiv.org/abs/1706.03762v7"

    def test_empty_query_raises(self) -> None:
        import asyncio

        from quantlab.data.literature.papers import AcademicPapersProvider

        with pytest.raises(ValueError):
            asyncio.run(AcademicPapersProvider().fetch_papers("  "))

    def test_category_filter_in_request(self) -> None:
        import asyncio

        from quantlab.data.literature.papers import AcademicPapersProvider

        with _patched_client() as client:
            asyncio.run(
                AcademicPapersProvider().fetch_papers(
                    "momentum", categories=["q-fin.CP"]
                )
            )
        requested_url = str(client.get.call_args[0][0])
        assert "q-fin.CP" in requested_url

    def test_http_error_raises_provider_error(self) -> None:
        import asyncio

        from quantlab.data.fundamental.base import ProviderError
        from quantlab.data.literature.papers import AcademicPapersProvider

        with (
            _patched_client(status=500),
            pytest.raises(ProviderError),
        ):
            asyncio.run(AcademicPapersProvider().fetch_papers("momentum"))

    def test_ssrn_source_warns_and_returns_empty(self) -> None:
        import asyncio

        from quantlab.data.literature.papers import AcademicPapersProvider

        with pytest.warns(UserWarning, match="[Ss][Ss][Rr][Nn]"):
            papers = asyncio.run(
                AcademicPapersProvider().fetch_papers("momentum", source="ssrn")
            )
        assert papers == []

    def test_fetch_wraps_as_dict(self) -> None:
        import asyncio

        from quantlab.data.literature.papers import AcademicPapersProvider

        with _patched_client():
            result = asyncio.run(
                AcademicPapersProvider().fetch("momentum", max_results=2)
            )
        assert result["count"] == 2
        assert result["query"] == "momentum"

    def test_auto_registered(self) -> None:
        from quantlab.data.fundamental.base import AbstractDataProvider
        from quantlab.data.literature.papers import AcademicPapersProvider

        assert (
            AbstractDataProvider._registry["AcademicPapersProvider"]
            is AcademicPapersProvider
        )
