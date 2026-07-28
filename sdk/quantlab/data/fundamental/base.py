"""Abstract base class for fundamental data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderError(Exception):
    """Structured error from a data provider.

    Attributes:
        code: Machine-readable error code (e.g. "YAHOO_ERROR", "FRED_ERROR").
        details: Additional context about the failure.
    """

    def __init__(
        self,
        message: str,
        code: str = "PROVIDER_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)


class AbstractDataProvider(ABC):
    """Abstract base for all data providers.

    Subclasses register automatically via ``__init_subclass__`` into
    ``_registry``, enabling discovery without manual registration.

    The single abstract method is ``fetch`` — all provider-specific
    functionality maps through this interface.
    """

    _registry: dict[str, type[AbstractDataProvider]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        AbstractDataProvider._registry[cls.__name__] = cls

    @abstractmethod
    async def fetch(self, query: str, **params: Any) -> dict[str, Any]:
        """Fetch data from the provider.

        Subclasses MUST implement this method. Implementation should
        interact with a cache layer and rate limiter when available.

        Args:
            query: The query key — ticker symbol for Yahoo, series ID for FRED.
            **params: Provider-specific parameters (e.g. start/end dates).

        Returns:
            Normalized data as a dictionary.

        Raises:
            ProviderError: On API or network failure.
        """
