"""RSS news provider — consumes RSS feeds via httpx + feedparser.

Follows the same ``AbstractDataProvider`` pattern with caching and
rate limiting from ``quantlab.data.fundamental``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from quantlab.data.news.base import NewsProvider, ProviderError
from quantlab.data.news.models import NewsItem

logger = logging.getLogger(__name__)

try:
    import feedparser
except ImportError:  # pragma: no cover
    feedparser = None  # type: ignore[assignment]


_DEFAULT_RSS_URLS: list[str] = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={query}&region=US&lang=en-US",
    "https://news.google.com/rss/search?q={query}+finance&hl=en-US&gl=US&ceid=US:en",
]


class RSSNewsProvider(NewsProvider):
    """News provider that consumes RSS feeds from configurable sources.

    Fetches articles from RSS feed URLs, parses them with
    ``feedparser``, and returns deduplicated ``NewsItem`` objects.

    Default RSS sources are Yahoo Finance RSS and Google News finance.
    Sources that return errors are silently skipped and logged.

    Args:
        rss_urls: List of RSS feed URL templates. Each URL may contain
            a ``{query}`` placeholder that is replaced with the search
            term. Defaults to Yahoo Finance and Google News.
        **kwargs: Additional arguments forwarded to ``NewsProvider``.
    """

    def __init__(
        self,
        rss_urls: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.rss_urls = rss_urls or list(_DEFAULT_RSS_URLS)
        super().__init__(**kwargs)  # type: ignore[call-arg]

    async def fetch_news(self, query: str, **params: Any) -> list[NewsItem]:
        """Fetch news articles matching the query from configured RSS feeds.

        Each RSS URL is tried in order. If a feed fails (HTTP error,
        timeout, or parse error), it is skipped and the next source
        is attempted. Results are deduplicated by URL.

        Args:
            query: Search term (ticker or free text).
            **params: Currently unused; provided for extensibility.

        Returns:
            A list of ``NewsItem`` instances, deduplicated by URL.

        Raises:
            ValueError: If query is empty or ``None``.
        """
        if not query:
            raise ValueError("query must not be empty")

        if feedparser is None:
            logger.warning("feedparser is not installed; RSS feeds cannot be parsed")
            return []

        seen_urls: set[str] = set()
        results: list[NewsItem] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            for url_template in self.rss_urls:
                url = url_template.format(query=query)
                try:
                    response = await client.get(url, follow_redirects=True)
                    response.raise_for_status()
                except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as exc:
                    logger.warning("RSS fetch failed for %s: %s", url, exc)
                    continue

                feed = feedparser.parse(response.text)
                for entry in feed.entries:
                    # feedparser entries support both attribute and dict access
                    article_url = entry.link if hasattr(entry, "link") else entry.get("link", "")
                    if article_url in seen_urls:
                        continue
                    seen_urls.add(article_url)

                    title = entry.title if hasattr(entry, "title") else entry.get("title", "")
                    summary = (
                        (entry.description if hasattr(entry, "description") else entry.get("description"))
                        or (entry.summary if hasattr(entry, "summary") else entry.get("summary", ""))
                    )
                    published = (
                        (entry.published_parsed if hasattr(entry, "published_parsed") else entry.get("published_parsed"))
                        or (entry.updated_parsed if hasattr(entry, "updated_parsed") else entry.get("updated_parsed"))
                    )
                    pub_date: datetime | None = None
                    if published:
                        try:
                            pub_date = datetime(*published[:6])
                        except (TypeError, ValueError):
                            pub_date = datetime.now()
                    src = entry.source if hasattr(entry, "source") else entry.get("source", {})
                    source = (src.title if hasattr(src, "title") else src.get("title", url)) if src else url

                    results.append(
                        NewsItem(
                            title=title,
                            url=article_url,
                            source=source,
                            published_date=pub_date or datetime.now(),
                            summary=summary,
                        )
                    )

        return results

    async def search_web(self, query: str, **params: Any) -> list:
        """Web search is not supported by RSSNewsProvider.

        Raises:
            NotImplementedError: Always — use ``WebSearchProvider`` instead.
        """
        raise NotImplementedError(
            "RSSNewsProvider does not support web search. Use WebSearchProvider."
        )
