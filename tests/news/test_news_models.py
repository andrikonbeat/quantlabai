"""Tests for NewsItem and WebResult dataclasses."""

from __future__ import annotations

from datetime import datetime, timezone

from quantlab.data.news.models import NewsItem, WebResult


class TestNewsItem:
    def test_minimal(self) -> None:
        item = NewsItem(
            title="Test Article",
            url="https://example.com/news/1",
            source="TestSource",
            published_date=datetime(2026, 7, 29, tzinfo=timezone.utc),
            summary="Test summary",
        )
        assert item.title == "Test Article"
        assert item.sentiment is None

    def test_with_sentiment(self) -> None:
        item = NewsItem(
            title="Bullish News",
            url="https://example.com/bullish",
            source="Yahoo Finance",
            published_date=datetime(2026, 7, 29, tzinfo=timezone.utc),
            summary="Markets up",
            sentiment=0.85,
        )
        assert item.sentiment == 0.85

    def test_frozen(self) -> None:
        item = NewsItem(
            title="Frozen",
            url="https://example.com",
            source="S",
            published_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            summary="X",
        )
        with pytest.raises(AttributeError):  # noqa: PT012
            item.title = "Changed"  # type: ignore[misc]

class TestWebResult:
    def test_minimal(self) -> None:
        r = WebResult(
            title="Result",
            url="https://example.com",
            snippet="Snippet text",
            source="duckduckgo",
        )
        assert r.title == "Result"
        assert r.source == "duckduckgo"

    def test_frozen(self) -> None:
        r = WebResult(
            title="Frozen", url="https://example.com", snippet="X", source="S"
        )
        with pytest.raises(AttributeError):  # noqa: PT012
            r.title = "Changed"  # type: ignore[misc]


# Need pytest for the frozen test
import pytest  # noqa: E402 (import after usage OK for test helper)
