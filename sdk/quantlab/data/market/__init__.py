"""Market data normalization package.

Provides OHLCV bar models and provider adapters for Yahoo Finance and
Dukascopy feeds, following the project's AbstractDataProvider pattern.
"""

from quantlab.data.market.models import Bar, MarketDataConfig
from quantlab.data.market.providers import (
    DukascopyProvider,
    MarketDataProvider,
    YahooProvider,
)
from quantlab.data.market.registry import MarketDataProviderRegistry

__all__ = [
    "Bar",
    "DukascopyProvider",
    "MarketDataConfig",
    "MarketDataProvider",
    "MarketDataProviderRegistry",
    "YahooProvider",
]
