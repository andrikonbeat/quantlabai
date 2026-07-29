"""News and web search data providers.

Provides RSS feed consumption and web search following the same
``AbstractDataProvider`` pattern as fundamental data providers,
with SQLite caching and token-bucket rate limiting.
"""

from quantlab.data.news.base import NewsProvider, ProviderError
from quantlab.data.news.models import NewsItem, WebResult
from quantlab.data.news.rss import RSSNewsProvider
from quantlab.data.news.web_search import WebSearchProvider

__all__ = [
    "NewsItem",
    "NewsProvider",
    "ProviderError",
    "RSSNewsProvider",
    "WebResult",
    "WebSearchProvider",
]
