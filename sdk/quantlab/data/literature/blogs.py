"""Quant blog provider (RSS feeds, deduplicated by URL)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from quantlab.data.fundamental.base import ProviderError
from quantlab.data.fundamental.rate_limit import TokenBucket
from quantlab.data.literature.base import LiteratureProvider
from quantlab.data.literature.models import PaperItem

try:
    import feedparser
except ImportError:  # pragma: no cover
    feedparser = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_DEFAULT_BLOG_FEEDS: list[str] = [
    "https://quantpedia.com/feed/",
    "https://www.quantstart.com/rss.xml",
]

__all__ = ["QuantBlogProvider"]


class QuantBlogProvider(LiteratureProvider):
    """Quant-blog provider consuming configurable RSS feeds.

    Entries matching the query are mapped to ``PaperItem`` (blogs have no
    arXiv id; ``source`` is ``blog:<domain>``). Results are deduplicated
    by URL across feeds. A failing feed is skipped with a warning so one
    down blog never blocks the others.
    """

    def __init__(
        self,
        feed_urls: list[str] | None = None,
        rate_limiter: TokenBucket | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.feed_urls = feed_urls or list(_DEFAULT_BLOG_FEEDS)
        self.rate_limiter = rate_limiter or TokenBucket(rate=1.0, capacity=3)
        self.timeout = timeout

    async def fetch_papers(self, query: str, **params: Any) -> list[PaperItem]:
        """Fetch blog posts matching the query from the configured feeds.

        Args:
            query: Free-text query; every whitespace-separated term must
                appear (case-insensitive) in the entry title/summary/tags.
            **params:
                max_results: Maximum posts to return (default 10).
                feed_urls: Optional per-call feed override.

        Returns:
            Deduplicated list of ``PaperItem`` (empty when feedparser is
            unavailable).
        """
        query = await self._require_query(query)
        max_results: int = int(params.get("max_results", 10))
        feed_urls: list[str] = params.get("feed_urls") or self.feed_urls
        terms = query.lower().split()

        if feedparser is None:
            logger.warning("feedparser not installed; returning no blog posts")
            return []

        papers: list[PaperItem] = []
        seen_urls_set: set[str] = set()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for feed_url in feed_urls:
                    await self.rate_limiter.acquire()
                    try:
                        response = await client.get(feed_url, follow_redirects=True)
                        response.raise_for_status()
                    except (
                        httpx.HTTPStatusError,
                        httpx.TimeoutException,
                        httpx.RequestError,
                    ) as exc:
                        logger.warning("Blog feed failed for %s: %s", feed_url, exc)
                        continue
                    feed = feedparser.parse(response.text)
                    source = f"blog:{urlparse(feed_url).netloc}"
                    for entry in feed.entries:
                        paper = self._entry_to_paper(entry, source)
                        if paper is None:
                            continue
                        if paper.url in seen_urls_set:
                            continue
                        haystack = " ".join(
                            [paper.title, paper.abstract, " ".join(paper.categories)]
                        ).lower()
                        if all(term in haystack for term in terms):
                            seen_urls_set.add(paper.url)
                            papers.append(paper)
                            if len(papers) >= max_results:
                                return papers
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"Blog fetch failed for {query!r}: {exc}",
                code="BLOG_ERROR",
                details={"query": query},
            ) from exc
        return papers

    @staticmethod
    def _entry_to_paper(entry: Any, source: str) -> PaperItem | None:
        """Map one RSS entry to ``PaperItem``; None when it has no URL."""
        url = str(getattr(entry, "link", "") or "").strip()
        if not url:
            return None
        authors: list[str] = []
        author = getattr(entry, "author", None)
        if author:
            authors = [str(author).strip()]
        categories = [
            str(t.get("term", "")) for t in getattr(entry, "tags", [])
        ]
        published_at = None
        published = getattr(entry, "published", None)
        if published:
            try:
                published_at = datetime.fromisoformat(
                    str(published).replace("GMT", "+00:00").replace("Z", "+00:00")
                )
            except ValueError:
                # Fall back to feedparser's parsed struct when available
                parsed = getattr(entry, "published_parsed", None)
                if parsed is not None:
                    try:
                        published_at = datetime(*parsed[:6])
                    except (TypeError, ValueError):
                        published_at = None
        return PaperItem(
            title=str(getattr(entry, "title", "")).strip(),
            authors=authors,
            abstract=str(getattr(entry, "summary", "") or getattr(entry, "description", "")).strip(),
            url=url,
            arxiv_id=None,
            categories=[c for c in categories if c],
            published_at=published_at,
            source=source,
        )
