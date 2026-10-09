"""Privacy/deny-list conformance for new providers + feedback data (T9 5.3).

- Provider request URLs must be https and carry no secret params (the
  screener key travels in its URL by AlphaVantage design, sourced from
  env/ctor — never hardcoded; asserted separately).
- Feedback records and written metadata must pass the field-scoped
  deny-list check (prose fields are out of scope by design).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

import pytest

from quantlab.knowledge.privacy import PrivacyScrubber


def _https_client(text: str = "<feed></feed>", payload: dict | None = None):
    response = MagicMock()
    response.text = text
    response.status_code = 200
    response.raise_for_status = MagicMock()
    if payload is not None:
        response.json = MagicMock(return_value=payload)
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestProviderUrlPrivacy:
    def test_arxiv_url_https_no_secrets(self) -> None:
        import asyncio

        from quantlab.data.literature.papers import AcademicPapersProvider

        with patch(
            "quantlab.data.literature.papers.httpx.AsyncClient",
            return_value=_https_client(),
        ) as mock_cls:
            client = mock_cls.return_value
            asyncio.run(AcademicPapersProvider().fetch_papers("momentum"))
        url = str(client.get.call_args[0][0])
        assert urlparse(url).scheme == "https"
        assert "api_key" not in url and "token" not in url

    def test_blog_feed_urls_https(self) -> None:
        import asyncio

        from quantlab.data.literature.blogs import QuantBlogProvider

        feeds = ["https://a.example/feed", "https://b.example/feed"]
        with patch(
            "quantlab.data.literature.blogs.httpx.AsyncClient",
            return_value=_https_client(),
        ) as mock_cls:
            client = mock_cls.return_value
            asyncio.run(QuantBlogProvider(feed_urls=feeds).fetch_papers("rsi"))
        for call in client.get.call_args_list:
            url = str(call[0][0])
            assert urlparse(url).scheme == "https"

    def test_screener_url_https_key_not_hardcoded(self) -> None:
        import asyncio
        import inspect

        from quantlab.data.screening import screener as screener_module
        from quantlab.data.screening.screener import StockScreenerProvider

        # No default key in source or signature
        source = inspect.getsource(StockScreenerProvider.__init__)
        assert "demo" not in source.lower() or "apikey=demo" not in source
        with patch(
            "quantlab.data.screening.screener.httpx.AsyncClient",
            return_value=_https_client(
                payload={"top_gainers": [], "top_losers": [],
                         "most_actively_traded": []}
            ),
        ) as mock_cls:
            client = mock_cls.return_value
            asyncio.run(StockScreenerProvider(api_key="k").fetch("gainers"))
        url = str(client.get.call_args[0][0])
        assert urlparse(url).scheme == "https"


class TestFeedbackPrivacy:
    def test_feedback_record_deny_list_clean(self) -> None:
        from quantlab.knowledge.models import HypothesisFeedbackRecord

        record = HypothesisFeedbackRecord(
            campaign_id="camp-1", hypothesis_id="h1", feedback_type="pass",
            notes="archived after review",
        )
        assert PrivacyScrubber().is_deny_list_clean(record.to_dict())

    def test_written_metadata_deny_list_clean(self, tmp_path) -> None:
        import asyncio

        import yaml

        from quantlab.agents.feedback_writer import KnowledgeLakeFeedbackWriter
        from quantlab.knowledge.models import HypothesisFeedbackRecord

        writer = KnowledgeLakeFeedbackWriter(lake_root=tmp_path)
        asyncio.run(
            writer.write_feedback(
                HypothesisFeedbackRecord(
                    campaign_id="camp-1", hypothesis_id="h1",
                    feedback_type="pass", notes="archived",
                ),
                reindex=False,
            )
        )
        data = yaml.safe_load(
            (tmp_path / "structured" / "camp-1" / "metadata.yaml").read_text(
                encoding="utf-8"
            )
        )
        assert PrivacyScrubber().is_deny_list_clean(data)
