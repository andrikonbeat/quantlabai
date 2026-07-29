"""Abstract base class for news and web search providers.

Follows the same ``AbstractDataProvider`` pattern from
``quantlab.data.fundamental.base`` with additional news-specific
abstract methods.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from quantlab.data.fundamental.base import AbstractDataProvider, ProviderError

from quantlab.data.news.models import NewsItem, WebResult

__all__ = [
    "NewsProvider",
    "ProviderError",
]


class NewsProvider(AbstractDataProvider):
    """Abstract base for all news and web search providers.

    Extends ``AbstractDataProvider`` with news-specific methods:
    ``fetch_news`` for financial news articles and ``search_web`` for
    general web search results.

    The inherited ``fetch`` method is implemented to delegate to
    ``fetch_news`` by default so that concrete subclasses only need
    to implement ``fetch_news`` and/or ``search_web``.
    """

    @abstractmethod
    async def fetch_news(self, query: str, **params: Any) -> list[NewsItem]:
        """Fetch financial news articles matching the query.

        Args:
            query: Search term (ticker, topic, or free text).
            **params: Provider-specific parameters.

        Returns:
            A list of ``NewsItem`` instances.

        Raises:
            ValueError: If query is empty or ``None``.
            ProviderError: On provider-level failures.
        """
        ...

    @abstractmethod
    async def search_web(self, query: str, **params: Any) -> list[WebResult]:
        """Search the web for general information.

        Args:
            query: Search query string.
            **params: Provider-specific parameters.

        Returns:
            A list of ``WebResult`` instances.

        Raises:
            ValueError: If query is empty or ``None``.
            ProviderError: On provider-level failures.
        """
        ...

    async def fetch(self, query: str, **params: Any) -> dict[str, Any]:
        """Fetch method required by ``AbstractDataProvider``.

        Delegates to ``fetch_news`` and wraps the result as a dict
        for backward compatibility with the ``AbstractDataProvider``
        interface. Subclasses may override this for custom behaviour.
        """
        items = await self.fetch_news(query, **params)
        return {
            "query": query,
            "articles": [item.__dict__ for item in items],
            "count": len(items),
        }
