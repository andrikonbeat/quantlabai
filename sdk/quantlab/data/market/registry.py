"""Registry for market data providers.

Provides discovery by provider name, following the project's existing
``AbstractDataProvider._registry`` pattern adapted for the market data
package.
"""

from __future__ import annotations

from quantlab.data.market.providers import DukascopyProvider, MarketDataProvider, YahooProvider


class MarketDataProviderRegistry:
    """Registry mapping provider names to MarketDataProvider classes.

    Names are lowercase identifiers (e.g. ``"yahoo"``, ``"dukascopy"``).
    """

    _registry: dict[str, type[MarketDataProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[MarketDataProvider]) -> None:
        """Register a provider class under a lowercase name."""
        cls._registry[name.lower()] = provider_class

    @classmethod
    def get(cls, name: str) -> type[MarketDataProvider] | None:
        """Return the provider class for a given name, or None."""
        return cls._registry.get(name.lower())

    @classmethod
    def names(cls) -> list[str]:
        """Return all registered provider names."""
        return sorted(cls._registry.keys())


MarketDataProviderRegistry.register("yahoo", YahooProvider)
MarketDataProviderRegistry.register("dukascopy", DukascopyProvider)
