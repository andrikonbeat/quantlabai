"""Abstract base class for literature providers.

Follows the ``AbstractDataProvider`` pattern from
``quantlab.data.fundamental.base`` with literature-specific methods.
Concrete providers (academic papers, quant blogs) implement
``fetch_papers``; the inherited ``fetch`` delegates to it by default.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from quantlab.data.fundamental.base import AbstractDataProvider, ProviderError
from quantlab.data.literature.models import PaperItem

__all__ = [
    "LiteratureProvider",
    "ProviderError",
]


class LiteratureProvider(AbstractDataProvider):
    """Abstract base for all literature providers.

    Extends ``AbstractDataProvider`` with the literature-specific
    ``fetch_papers`` method. The inherited ``fetch`` method delegates to
    ``fetch_papers`` and wraps the result as a dict, so subclasses only
    need to implement ``fetch_papers``.
    """

    @abstractmethod
    async def fetch_papers(self, query: str, **params: Any) -> list[PaperItem]:
        """Fetch papers matching the query.

        Args:
            query: Search term (topic, author, or free text).
            **params: Provider-specific parameters (e.g. ``categories``,
                ``max_results``).

        Returns:
            A list of ``PaperItem`` instances.

        Raises:
            ValueError: If query is empty or ``None``.
            ProviderError: On provider-level failures.
        """
        ...

    async def _require_query(self, query: str) -> str:
        """Validate and normalize the query string."""
        if query is None or not str(query).strip():
            raise ValueError("query must be a non-empty string")
        return str(query).strip()

    async def fetch(self, query: str, **params: Any) -> dict[str, Any]:
        """Fetch method required by ``AbstractDataProvider``.

        Delegates to ``fetch_papers`` and wraps the result as a dict
        for backward compatibility with the ``AbstractDataProvider``
        interface. Subclasses may override this for custom behaviour.

        Raises:
            ValueError: If query is empty or ``None``.
        """
        query = await self._require_query(query)
        items = await self.fetch_papers(query, **params)
        return {
            "query": query,
            "papers": [item.__dict__ for item in items],
            "count": len(items),
        }
