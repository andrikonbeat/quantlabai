"""Tests for QuantBlogProvider (T9 task 2.3)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Quant Blog</title>
<item>
<title>RSI Mean Reversion That Works</title>
<link>https://blog.example.com/rsi-mean-reversion</link>
<description>Backtest of RSI(2) on SPY.</description>
<author>jane@blog.example.com (Jane Doe)</author>
<pubDate>Mon, 02 Jan 2024 00:00:00 GMT</pubDate>
<category>mean-reversion</category>
</item>
<item>
<title>Trend Following with Donchian Channels</title>
<link>https://blog.example.com/donchian-trend</link>
<description>Breakout entries on N-day highs.</description>
<pubDate>Tue, 03 Jan 2024 00:00:00 GMT</pubDate>
<category>trend</category>
</item>
</channel>
</rss>
"""


@contextlib.contextmanager
def _patched_feed(text: str = SAMPLE_RSS):
    import httpx

    response = MagicMock()
    response.text = text
    response.status_code = 200
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "quantlab.data.literature.blogs.httpx.AsyncClient",
        return_value=client,
    ):
        yield client


class TestQuantBlogProvider:
    def test_fetches_and_maps_items(self) -> None:
        import asyncio

        from quantlab.data.literature.blogs import QuantBlogProvider

        provider = QuantBlogProvider(
            feed_urls=["https://blog.example.com/feed"]
        )
        with _patched_feed():
            papers = asyncio.run(provider.fetch_papers("rsi"))

        assert len(papers) == 1
        paper = papers[0]
        assert paper.title == "RSI Mean Reversion That Works"
        assert paper.url == "https://blog.example.com/rsi-mean-reversion"
        assert paper.source.startswith("blog:")
        assert "mean-reversion" in paper.categories

    def test_empty_query_raises(self) -> None:
        import asyncio

        from quantlab.data.literature.blogs import QuantBlogProvider

        with pytest.raises(ValueError):
            asyncio.run(
                QuantBlogProvider(feed_urls=["https://x.example/feed"]).fetch_papers("")
            )

    def test_dedup_by_url_across_feeds(self) -> None:
        import asyncio

        from quantlab.data.literature.blogs import QuantBlogProvider

        provider = QuantBlogProvider(
            feed_urls=[
                "https://a.example/feed",
                "https://b.example/feed",
            ]
        )
        with _patched_feed():
            papers = asyncio.run(provider.fetch_papers("donchian"))

        urls = [p.url for p in papers]
        assert len(urls) == len(set(urls)) == 1

    def test_feed_failure_isolated(self) -> None:
        import asyncio

        import httpx

        from quantlab.data.literature.blogs import QuantBlogProvider

        # Build a client whose first feed fails and second succeeds
        response_ok = MagicMock()
        response_ok.text = SAMPLE_RSS
        response_ok.status_code = 200
        response_ok.raise_for_status = MagicMock()
        client = AsyncMock()

        async def _get(url, **kwargs):
            if "a.example" in str(url):
                raise httpx.ConnectError("down")
            return response_ok

        client.get = AsyncMock(side_effect=_get)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        provider = QuantBlogProvider(
            feed_urls=["https://a.example/feed", "https://b.example/feed"]
        )
        with patch(
            "quantlab.data.literature.blogs.httpx.AsyncClient",
            return_value=client,
        ):
            papers = asyncio.run(provider.fetch_papers("rsi"))
        assert len(papers) == 1

    def test_auto_registered(self) -> None:
        from quantlab.data.fundamental.base import AbstractDataProvider
        from quantlab.data.literature.blogs import QuantBlogProvider

        assert (
            AbstractDataProvider._registry["QuantBlogProvider"]
            is QuantBlogProvider
        )
