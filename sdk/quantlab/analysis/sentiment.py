"""Sentiment scorer — rule-based news-to-sentiment pipeline.

Outputs are contextual sentiment scores, NOT trading signals.
Perception layer only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from quantlab.data.news.models import NewsItem


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SentimentResult:
    """Sentiment scoring result."""

    score: float
    rationale: str
    source_count: int


# ---------------------------------------------------------------------------
# Lexicon
# ---------------------------------------------------------------------------

_BULLISH_WORDS: set[str] = {
    "beat",
    "upgraded",
    "buy",
    "strong",
    "growth",
    "profit",
    "gains",
    "outperform",
    "upgrade",
    "bullish",
    "positive",
    "surge",
    "rally",
    "boom",
    "expansion",
}

_BEARISH_WORDS: set[str] = {
    "missed",
    "downgrade",
    "sell",
    "weak",
    "loss",
    "decline",
    "underperform",
    "downgraded",
    "bearish",
    "negative",
    "plunge",
    "crash",
    "contraction",
    "recession",
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SentimentScorer:
    """Rule-based sentiment scorer for NewsItem lists."""

    def score(self, news: list[NewsItem]) -> SentimentResult:
        """Return sentiment score in [-1, 1] with rationale.

        Args:
            news: List of NewsItem instances.

        Returns:
            SentimentResult with score, rationale, and source_count.
        """
        if not news:
            return SentimentResult(score=0.0, rationale="insufficient data", source_count=0)

        total_score = 0.0
        matched_keywords: list[str] = []

        for item in news:
            text = f"{item.title} {item.summary}".lower()
            words = set(text.split())
            bullish_hits = words & _BULLISH_WORDS
            bearish_hits = words & _BEARISH_WORDS

            if bullish_hits:
                total_score += 1.0
                matched_keywords.extend(sorted(bullish_hits))
            if bearish_hits:
                total_score -= 1.0
                matched_keywords.extend(sorted(bearish_hits))

        if not matched_keywords:
            return SentimentResult(score=0.0, rationale="no sentiment keywords detected", source_count=len(news))

        # Average across items that had sentiment.
        scored_items = sum(1 for item in news if (set(f"{item.title} {item.summary}".lower().split()) & (_BULLISH_WORDS | _BEARISH_WORDS)))
        avg = total_score / max(scored_items, 1)

        # Clamp to [-1, 1].
        score = max(-1.0, min(1.0, avg))
        rationale = ", ".join(sorted(set(matched_keywords)))

        return SentimentResult(score=score, rationale=rationale, source_count=len(news))
