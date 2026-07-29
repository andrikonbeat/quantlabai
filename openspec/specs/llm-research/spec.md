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

The system MUST provide structured prompt templates by analysis type: technical, fundamental, macro, and news-based. Each template SHALL include relevant data context.

#### Scenario: Fundamental prompt includes financial data

- GIVEN a fundamental analysis objective with PE ratio, revenue, and debt data
- WHEN the fundamental template is selected
- THEN the prompt includes structured financial metrics

#### Scenario: Technical prompt excludes macro data

- GIVEN a technical analysis objective (price, volume, indicators)
- WHEN the technical template is selected
- THEN the prompt omits macroeconomic indicators

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
