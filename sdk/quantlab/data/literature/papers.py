"""Academic paper providers (arXiv; SSRN deferred — no public API)."""

from __future__ import annotations

import logging
import warnings
from datetime import datetime
from typing import Any

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

_ARXIV_API_URL = "https://export.arxiv.org/api/query"

__all__ = ["AcademicPapersProvider"]


class AcademicPapersProvider(LiteratureProvider):
    """Academic paper provider backed by the arXiv API.

    Queries the arXiv Atom API (no extra dependency: ``httpx`` +
    ``feedparser`` are already core deps), maps entries to ``PaperItem``,
    and rate-limits politely. ``source="ssrn"`` is accepted but deferred —
    SSRN offers no stable public API — and returns ``[]`` with a warning.
    """

    def __init__(
        self,
        rate_limiter: TokenBucket | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.rate_limiter = rate_limiter or TokenBucket(rate=0.5, capacity=2)
        self.timeout = timeout

    async def fetch_papers(self, query: str, **params: Any) -> list[PaperItem]:
        """Fetch papers from arXiv matching the query.

        Args:
            query: Topic, author, or free-text search.
            **params:
                categories: Optional list of arXiv categories
                    (e.g. ``["q-fin.CP"]``) to restrict the search.
                max_results: Maximum papers to return (default 10).
                source: ``"arxiv"`` (default) or ``"ssrn"`` (deferred).

        Returns:
            List of ``PaperItem`` (empty when feedparser is unavailable
            or when ``source="ssrn"``).
        """
        query = await self._require_query(query)
        source = str(params.get("source", "arxiv")).lower()
        if source == "ssrn":
            warnings.warn(
                "SSRN has no stable public API; source='ssrn' is deferred "
                "and returns no results.",
                UserWarning,
                stacklevel=2,
            )
            return []
        if source != "arxiv":
            raise ProviderError(
                f"Unknown literature source: {source}",
                code="LITERATURE_SOURCE_ERROR",
                details={"source": source},
            )

        categories: list[str] | None = params.get("categories")
        max_results: int = int(params.get("max_results", 10))

        if feedparser is None:
            logger.warning("feedparser not installed; returning no papers")
            return []

        search_query = f"all:{query}"
        if categories:
            cat_expr = "+OR+".join(f"cat:{c}" for c in categories)
            search_query = f"({search_query})+AND+({cat_expr})"
        url = (
            f"{_ARXIV_API_URL}?search_query={search_query}"
            f"&start=0&max_results={max_results}"
            "&sortBy=submitted&sortOrder=descending"
        )

        await self.rate_limiter.acquire()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as exc:
            raise ProviderError(
                f"arXiv fetch failed for {query!r}: {exc}",
                code="ARXIV_ERROR",
                details={"query": query},
            ) from exc
        except Exception as exc:
            raise ProviderError(
                f"arXiv fetch failed for {query!r}: {exc}",
                code="ARXIV_ERROR",
                details={"query": query},
            ) from exc

        feed = feedparser.parse(response.text)
        papers: list[PaperItem] = []
        for entry in feed.entries:
            papers.append(self._entry_to_paper(entry))
        return papers[:max_results]

    @staticmethod
    def _entry_to_paper(entry: Any) -> PaperItem:
        """Map one arXiv Atom entry to ``PaperItem``."""
        entry_id = str(getattr(entry, "id", ""))
        arxiv_id = entry_id.rsplit("/abs/", 1)[-1].split("v")[0] or None
        authors = [
            str(a.get("name", "")) for a in getattr(entry, "authors", [])
        ]
        categories = [
            str(t.get("term", "")) for t in getattr(entry, "tags", [])
        ]
        published_at = None
        published = getattr(entry, "published", None)
        if published:
            try:
                published_at = datetime.fromisoformat(
                    str(published).replace("Z", "+00:00")
                )
            except ValueError:
                published_at = None
        return PaperItem(
            title=str(getattr(entry, "title", "")).strip(),
            authors=authors,
            abstract=str(getattr(entry, "summary", "")).strip(),
            url=entry_id,
            arxiv_id=arxiv_id,
            categories=categories,
            published_at=published_at,
            source="arxiv",
        )
