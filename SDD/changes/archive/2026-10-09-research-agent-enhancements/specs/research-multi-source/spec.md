# Research Multi-Source Specification

## Purpose

Provider abstraction layer for external quantitative knowledge sources: academic papers, quantitative blogs, SQX documentation, and stock screeners. Each provider returns structured data that `LLMResearchAgent` can merge into its prompt context.

## Requirements

### Requirement: Provider Interface

All providers MUST implement the async interface:
```python
async def fetch(self, query: str, context: dict | None = None) -> list[dict[str, Any]]:
    ...
```
Each returned dict MUST contain at least `{title, url, summary, source}`. Providers MUST NOT raise on empty results; they MUST return an empty list.

#### Scenario: Provider returns structured items

- GIVEN a query "momentum equities"
- WHEN `provider.fetch(query)` completes
- THEN a list of dicts with title, url, summary, source is returned

#### Scenario: Provider returns empty list on no results

- GIVEN a query with no matching content
- WHEN `provider.fetch(query)` completes
- THEN an empty list is returned without raising

### Requirement: Academic Papers Provider

`AcademicPapersProvider` MUST query arXiv/SSRN for quantitative finance papers. It SHOULD filter by categories: `q-fin.PM`, `q-fin.TR`, `q-fin.ST`. Results MUST include paper ID, title, authors, abstract, and URL. Rate limiting and polite crawling MUST be respected.

#### Scenario: Papers fetched for mean-reversion query

- GIVEN arXiv is reachable and has matching papers
- WHEN `AcademicPapersProvider.fetch("mean reversion")` runs
- THEN results include paper metadata with `source="arxiv"`

### Requirement: Quantitative Blog Provider

`QuantBlogProvider` MUST consume RSS feeds from known quantitative trading blogs (e.g., Quantocracy, QuantStart). It SHOULD deduplicate by URL. Results MUST include publish date when available.

#### Scenario: Blog RSS items parsed

- GIVEN a blog RSS feed contains 5 items
- WHEN `QuantBlogProvider.fetch()` runs
- THEN 5 parsed items with title, url, summary, source, published_at are returned

### Requirement: SQX Documentation Provider

`SQXDocProvider` MUST scan `knowledge/structured/sqx-kb/` and local SQX installation documentation for indicator definitions, parameter ranges, and strategy examples. It MUST return structured snippets with `{title, url, summary, source="sqx-docs", indicator_name, parameter_ranges}`.

#### Scenario: SQX docs scanned for RSI

- GIVEN `sqx-kb/` contains RSI documentation
- WHEN `SQXDocProvider.fetch("RSI")` runs
- THEN a snippet with indicator_name="RSI" and parameter_ranges is returned

### Requirement: Stock Screener Provider

`StockScreenerProvider` MUST query Finviz or AlphaVantage for screened equities matching fundamental criteria (sector, market cap, PE, PB, ROE). It MUST return `{ticker, name, sector, pe, pb, roe, market_cap, source}`. The provider MUST handle API key configuration via environment variables and MUST NOT hardcode credentials.

#### Scenario: Screener returns matching equities

- GIVEN Finviz is reachable and API key is configured
- WHEN `StockScreenerProvider.fetch({"sector": "Technology", "pe_max": 20})` runs
- THEN a list of matching equities with fundamental metrics is returned

### Requirement: Circuit Breaker and Caching

All providers MUST integrate with `LLMCircuitBreaker` and `SqliteCache` (or equivalent) to prevent runaway failures and redundant requests. Cache keys MUST include the query string and context hash. TTL MUST be configurable per provider type.

#### Scenario: Repeated identical query returns cached result

- GIVEN a query was previously fetched within TTL
- WHEN the same query is made again
- THEN the cached result is returned without network I/O
