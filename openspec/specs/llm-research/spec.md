# LLM Research Specification

## Purpose

LLM-powered agent for generating grounded, data-informed trading hypotheses from fundamental data, news, and macro indicators.

## Requirements

### Requirement: LLMResearchAgent

The system MUST provide an `LLMResearchAgent` that accepts `objective: str` and `market_context: dict`, queries providers, builds structured prompts, and returns `ResearchConfig` with hypotheses.

#### Scenario: Happy path — hypotheses generated

- GIVEN an objective "find long opportunities in tech" with market_context containing FRED + YahooFinance data
- WHEN LLMResearchAgent.execute() is called
- THEN a ResearchConfig is returned with 1+ HypothesisConfig entries
- AND each entry has llm_rationale, source_urls, and data_sources

#### Scenario: No hypotheses returned

- GIVEN a contradictory objective with no supporting data
- WHEN the LLM returns an empty hypotheses array
- THEN ResearchConfig.hypotheses is empty
- AND the agent does not raise an error

### Requirement: Prompt Templates

The system MUST provide structured prompt templates by analysis type: technical, fundamental, macro, and news-based. Each template SHALL include relevant data context; the news-based template SHALL include fetched news articles. (Previously: templates existed but had no news-provider data source to include)

#### Scenario: Fundamental prompt includes financial data
- GIVEN a fundamental analysis objective with PE ratio, revenue, and debt data
- WHEN the fundamental template is selected
- THEN the prompt includes structured financial metrics

#### Scenario: Technical prompt excludes macro data
- GIVEN a technical analysis objective (price, volume, indicators)
- WHEN the technical template is selected
- THEN the prompt omits macroeconomic indicators

#### Scenario: News-based prompt includes articles
- GIVEN fetched news articles
- WHEN the news-based template is selected
- THEN the prompt includes the article text and URLs

**Acceptance**: news-based template consumes NWS-03 output.

### Requirement: Audit Trail

Each hypothesis MUST carry `llm_rationale: str`, `source_urls: list[str]`, and `data_sources: list[str]` for verifiability.

#### Scenario: Source URLs populated from provider data

- GIVEN YahooFinanceProvider returns ticker data with source URLs
- WHEN HypothesisConfig is constructed
- THEN source_urls contains the provider's source URLs

### Requirement: Error Handling — Fallback

If the LLM call fails (timeout, API error, parse error), the system MUST fall back to the classic `ResearchAgent` and log the failure.

#### Scenario: LLM timeout triggers fallback

- GIVEN the LLM API call exceeds the configured timeout
- WHEN LLMResearchAgent.execute() runs
- THEN classic ResearchAgent generates hypotheses instead
- AND a warning is logged

#### Scenario: Parse error in LLM response

- GIVEN the LLM returns malformed JSON
- WHEN parse_response() fails
- THEN fallback to classic ResearchAgent
- AND the error is logged for debugging

### Requirement: Rate Limiting & Caching

The system MUST reuse `TokenBucket` for LLM API call rate limiting and `SqliteCache` for response caching, keyed by prompt hash.

#### Scenario: Rate limited request

- GIVEN TokenBucket is exhausted
- WHEN an LLM API call is attempted
- THEN the system waits until tokens are available or returns cached response
- AND does not raise a rate-limit error to the caller

#### Scenario: Cached response hit

- GIVEN an identical prompt was sent within TTL
- WHEN the agent requests LLM completion
- THEN the cached response is returned without calling the API

### Requirement: NWS-01 Guarded provider singletons

`LLMResearchAgent` MUST expose `_get_web_search()` / `_get_rss_news()` returning lazily-initialized singleton providers, guarded by ImportError (missing duckduckgo-search/feedparser → None). Fresh instances SHALL have `_web_search` and `_rss_news` attributes set to None.

#### Scenario: Fresh instance attrs are None
- GIVEN a new LLMResearchAgent
- WHEN attributes are inspected
- THEN `_web_search is None` and `_rss_news is None`

#### Scenario: Providers are singletons
- GIVEN providers importable
- WHEN `_get_web_search()` / `_get_rss_news()` are called twice
- THEN each returns the same instance on repeat calls

#### Scenario: Missing provider degrades to None
- GIVEN the provider library is not installed
- WHEN the getter is called
- THEN it returns None without raising ImportError

**Acceptance**: 17 RED tests in tests/agents/test_llm_agent_news.py turn green.

### Requirement: NWS-02 fetch_data orchestration

`fetch_data()` MUST query web search and RSS (ticker-scoped; RSS skipped when no ticker), merge results into news items with expected keys, tolerate provider failures, and handle empty market context gracefully.

#### Scenario: Both providers contribute
- GIVEN mocked providers returning items
- WHEN fetch_data runs
- THEN news data contains items from both sources with expected keys

#### Scenario: Web search failure degrades
- GIVEN web search raises
- WHEN fetch_data runs
- THEN RSS still contributes and no exception propagates

#### Scenario: RSS failure degrades
- GIVEN RSS raises
- WHEN fetch_data runs
- THEN web results still contribute and no exception propagates

#### Scenario: No ticker skips RSS
- GIVEN no ticker in market context
- WHEN fetch_data runs
- THEN RSS is not invoked; web search still runs

#### Scenario: Empty context is graceful
- GIVEN an empty market context
- WHEN fetch_data runs
- THEN it completes without raising

#### Scenario: Query source precedence
- GIVEN context with a market
- WHEN fetch_data runs
- THEN the query uses context.market; with no market it falls back to the objective

**Acceptance**: fetch_data robust in all six cases.

### Requirement: NWS-03 News in prompt

`build_prompt` MUST include fetched articles as text with their URLs; articles without a URL SHALL show text without a URL line.

#### Scenario: Articles include URLs
- GIVEN articles with URLs
- WHEN build_prompt runs
- THEN the prompt contains article text and the URL

#### Scenario: Article without URL
- GIVEN an article missing a URL
- WHEN build_prompt runs
- THEN the prompt shows the text with no URL line

**Acceptance**: news-in-prompt behavior asserted by the tests.
