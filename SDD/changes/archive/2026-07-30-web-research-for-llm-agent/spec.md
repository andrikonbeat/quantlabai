# Delta: Web Research for LLM Agent

Closes the implementation gap between the `llm-research` spec and `LLMResearchAgent.fetch_data()` — wires existing `WebSearchProvider` and `RSSNewsProvider` into the fetch path so `news_data` is populated with real results and `source_urls` are available for LLM citation context.

## ADDED Requirements

### Requirement: Web Search Integration

The system MUST call `WebSearchProvider.search_web(market_context.get("market", objective))` inside `fetch_data()` and merge results into `news_data`.

#### Scenario: Happy path — web search + RSS both succeed

- GIVEN `market_context` contains a valid market description
- WHEN `fetch_data()` is called
- THEN `search_web()` is called with the market context as query
- AND `fetch_news(ticker)` is called with the extracted ticker
- AND `news_data` contains merged entries from both providers
- AND `news_data` is non-empty when providers return results

#### Scenario: Web search rate-limited, succeeds eventually

- GIVEN DuckDuckGo rate limits are hit (TokenBucket delays)
- WHEN `search_web()` waits and retries
- THEN the delay is transparent to `fetch_data()`
- AND results are returned eventually
- AND the agent does not raise a rate-limit error

### Requirement: Source URL Extraction

The system MUST extract `url` from each `WebResult` and `NewsItem` so the `build_prompt()` news section and the LLM response instructions can include real citation URLs.

#### Scenario: Source URLs merged into prompt context

- GIVEN web search and RSS return results with valid URLs
- WHEN `build_prompt()` processes `data["news"]`
- THEN the news section includes article titles and summaries
- AND the LLM prompt contains the source URLs for citation context

#### Scenario: Source URLs populate hypothesis citations

- GIVEN LLM returns hypotheses with `source_urls` referencing the news results
- WHEN `validate_output()` runs
- THEN each hypothesis has non-empty `source_urls` from the news providers
- AND `validate_output()` passes

### Requirement: Provider Lazy-Init Pattern

The system MUST provide `_get_web_search()` and `_get_rss_news()` lazy-init methods in `LLMResearchAgent`, mirroring the existing `_get_yahoo()` / `_get_fred()` pattern.

#### Scenario: Providers reused across calls

- GIVEN `fetch_data()` is called multiple times
- WHEN `_get_web_search()` or `_get_rss_news()` is invoked
- THEN the same provider instance is reused (lazy-init singleton)
- AND provider caching and rate-limit state is preserved across calls

### Requirement: Graceful Degradation on Provider Failure

Provider failures MUST be non-fatal — logged as warnings, and `fetch_data()` continues with available data. The LLM agent MUST still generate hypotheses from fundamental and macro data when news providers return empty.

#### Scenario: RSS feed down — returns empty

- GIVEN `RSSNewsProvider.fetch_news()` returns `[]` (all feeds down or timeout)
- WHEN `fetch_data()` runs
- THEN `news_data` is populated from web search only (if available)
- OR `news_data` is empty if both providers fail
- THEN `build_prompt()` skips the news section
- AND `validate_output()` still passes if fundamental/macro `source_urls` exist

#### Scenario: All providers fail — LLM still works

- GIVEN `search_web()` raises `ProviderError` AND `fetch_news()` returns `[]`
- WHEN `fetch_data()` completes
- THEN `data["news"]` is empty
- AND `generate_config()` produces hypotheses from fundamental and macro data only
- AND no exception propagates from the provider failures

#### Scenario: Empty market_context — graceful handling

- GIVEN `market_context` is `None` or empty
- WHEN `fetch_data()` is called
- THEN `search_web()` is called with `None` query
- AND the call returns empty gracefully (no crash)
- AND `fetch_news("")` returns `[]` gracefully
- AND fundamental/macro data is still fetched as before

## Unchanged Behavior

The following existing requirements in the `llm-research` spec remain unchanged and are now REALIZED by the wiring above:
- `Requirement: LLMResearchAgent` — returns `ResearchConfig` with `source_urls` and `data_sources` per hypothesis
- `Requirement: Audit Trail` — `source_urls` populated from provider data
- `Requirement: Error Handling — Fallback` — classic `ResearchAgent` fallback on any LLM failure
- `Requirement: Rate Limiting & Caching` — `TokenBucket` and `SqliteCache` already in providers

All existing tests pass unchanged. The fallback to classic `ResearchAgent` still works on provider failure.

## Acceptance Criteria

- [ ] `fetch_data()` returns non-empty `news` field when providers succeed
- [ ] `build_prompt()` includes the news section in the formatted prompt
- [ ] `validate_output()` passes with `source_urls` from web/RSS results
- [ ] All existing tests pass unchanged
- [ ] Fallback to classic `ResearchAgent` works when all providers fail
