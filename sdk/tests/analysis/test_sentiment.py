"""WU4 RED tests: SentimentScorer (REQ-304).

Covers rule-based sentiment scoring with bullish/bearish/neutral keywords.

Strict TDD: written first — FAIL (RED) until `SentimentScorer` exists.
"""

from __future__ import annotations

import pytest

from quantlab.data.news.models import NewsItem

# ── Helpers ────────────────────────────────────────────────────────────────────


def _news_item(title: str, summary: str = "") -> NewsItem:
    return NewsItem(
        title=title,
        url="https://example.com/article",
        source="test",
        published_date="2024-01-01T00:00:00Z",
        summary=summary or title,
    )


# ── TestSentimentScorer ────────────────────────────────────────────────────────


class TestSentimentScorer:
    def test_bullish_keywords_positive_score(self) -> None:
        """GIVEN NewsItems with bullish keywords ("beat", "upgraded")
        WHEN SentimentScorer.score is called
        THEN sentiment_score > 0.
        """
        from quantlab.analysis.sentiment import SentimentScorer

        news = [
            _news_item("Company beats earnings expectations"),
            _news_item("Analyst upgraded the stock to buy"),
        ]
        scorer = SentimentScorer()
        result = scorer.score(news)

        assert result.score > 0

    def test_bearish_keywords_negative_score(self) -> None:
        """GIVEN NewsItems with bearish keywords ("missed", "downgrade")
        WHEN SentimentScorer.score is called
        THEN sentiment_score < 0.
        """
        from quantlab.analysis.sentiment import SentimentScorer

        news = [
            _news_item("Company missed revenue estimates"),
            _news_item("Analyst downgraded the stock to sell"),
        ]
        scorer = SentimentScorer()
        result = scorer.score(news)

        assert result.score < 0

    def test_empty_input_returns_zero(self) -> None:
        """GIVEN an empty NewsItem list
        WHEN SentimentScorer.score is called
        THEN sentiment_score is 0.0.
        """
        from quantlab.analysis.sentiment import SentimentScorer

        scorer = SentimentScorer()
        result = scorer.score([])

        assert result.score == 0.0

    def test_rationale_non_empty_when_score_nonzero(self) -> None:
        """GIVEN NewsItems with non-zero sentiment
        WHEN SentimentScorer.score is called
        THEN rationale is non-empty.
        """
        from quantlab.analysis.sentiment import SentimentScorer

        news = [_news_item("Strong earnings beat drives stock higher")]
        scorer = SentimentScorer()
        result = scorer.score(news)

        assert result.score != 0.0
        assert result.rationale != ""
