"""Normalised result models for news and web search providers.

These dataclasses define the contract between news providers and
consumers (e.g. ``LLMResearchAgent``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, order=True)
class NewsItem:
    """A single news article from any provider.

    Attributes:
        title: Article headline.
        url: Link to the full article.
        source: Provider or publication name (e.g. "Yahoo Finance").
        published_date: Article publication timestamp.
        summary: Article body or excerpt.
        sentiment: Optional sentiment score -1.0 (negative) to 1.0 (positive).
    """

    title: str
    url: str
    source: str
    published_date: datetime
    summary: str
    sentiment: float | None = None


@dataclass(frozen=True, order=True)
class WebResult:
    """A single web search result.

    Attributes:
        title: Result headline.
        url: Link to the result.
        snippet: Brief excerpt or description.
        source: Provider identifier (e.g. ``"duckduckgo"``).
    """

    title: str
    url: str
    snippet: str
    source: str
