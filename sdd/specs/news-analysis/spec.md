# News Analysis Specification

## Purpose

Data provider for ingesting financial news and web search results, following the same `AbstractDataProvider` pattern as fundamental providers.

## Requirements

### Requirement: NewsProvider ABC

The system MUST provide an abstract `NewsProvider` base class extending `AbstractDataProvider` with methods `fetch_news(query: str) -> list[NewsItem]` and `search_web(query: str) -> list[WebResult]`.

#### Scenario: NewsProvider subclass contract

- GIVEN a subclass of NewsProvider
- WHEN fetch_news() is called with a query
- THEN a list of NewsItem objects is returned
- AND each NewsItem has title, url, source, published_date, summary

#### Scenario: Empty query raises error

- GIVEN an empty or None query string
- WHEN fetch_news() or search_web() is called
- THEN a ValueError is raised

### Requirement: RSSNewsProvider

The system MUST provide `RSSNewsProvider` that consumes RSS feeds from configurable financial news sources (Yahoo Finance RSS, Google News finance).

#### Scenario: RSS feed returns articles

- GIVEN RSSNewsProvider configured with valid RSS URLs
- WHEN fetch_news("AAPL") is called
- THEN articles matching the query are returned
- AND results are deduplicated by URL

#### Scenario: RSS feed unavailable

- GIVEN an RSS feed URL returns 500 or timeout
- WHEN fetch_news() is called
- THEN the provider skips that source and continues with others
- AND logs a warning

### Requirement: WebSearchProvider

The system MUST provide `WebSearchProvider` wrapping duckduckgo-search for web search without an API key.

#### Scenario: Web search returns results

- GIVEN WebSearchProvider
- WHEN search_web("AAPL earnings Q2 2026") is called
- THEN a list of WebResult is returned with title, url, snippet, source

#### Scenario: Search rate limited

- GIVEN duckduckgo-search rate limits are hit
- WHEN search_web() is called
- THEN the provider waits and retries once
- AND raises ProviderError on second failure

### Requirement: Normalized Result Models

The system MUST provide `NewsItem(title, url, source, published_date, summary, sentiment: float | None)` and `WebResult(title, url, snippet, source)` as dataclass models.

#### Scenario: Sentiment is optional

- GIVEN a NewsItem without sentiment data
- WHEN the model is constructed
- THEN sentiment is None
- AND the model is still valid

### Requirement: Caching & Rate Limiting

The system MUST reuse `SqliteCache` for news responses and `TokenBucket` for rate limiting, same pattern as fundamental providers.

#### Scenario: Cached news returned fast

- GIVEN a previously fetched query within cache TTL
- WHEN fetch_news() is called again
- THEN the cached response is returned
- AND no external request is made

#### Scenario: Rate limit blocks burst

- GIVEN 50 rapid fetch_news() calls
- WHEN the 51st call exceeds TokenBucket capacity
- THEN the call is delayed, not dropped
- AND eventually returns results
