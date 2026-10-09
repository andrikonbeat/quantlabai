# Delta for llm-research

## ADDED Requirements

### Requirement: Multi-Source Provider Orchestration

`LLMResearchAgent.fetch_data()` MUST support extensible provider registration for academic papers, quantitative blogs, SQX documentation, and stock screeners. Providers MUST be lazily initialized singleton factories with graceful ImportError degradation. The orchestrator MAY run providers in parallel and MUST tolerate individual provider failures without failing the entire fetch.

#### Scenario: Academic paper provider contributes context

- GIVEN `AcademicPapersProvider` is registered and returns abstracts for "mean reversion equities"
- WHEN `fetch_data()` runs with objective containing "mean-reversion"
- THEN news_data includes paper titles, URLs, and summaries

#### Scenario: Provider missing degrades gracefully

- GIVEN `FinvizProvider` import fails
- WHEN `fetch_data()` runs
- THEN other providers still contribute and no exception propagates

#### Scenario: Parallel provider execution

- GIVEN three providers are registered
- WHEN `fetch_data()` runs
- THEN all three are queried concurrently and results are merged

## MODIFIED Requirements

### Requirement: Prompt Templates

The system MUST provide structured prompt templates by analysis type. The news-based template MUST include fetched articles. The fundamental template MUST include expanded financial ratios when available. A new research-literature template MUST include paper/blog abstracts and SQX indicator catalog snippets.

(Previously: Templates existed but had no news-provider data source to include; no literature or SQX catalog templates)

#### Scenario: Literature template includes paper abstracts

- GIVEN `AcademicPapersProvider` returns 3 abstracts
- WHEN the research-literature template is selected
- THEN the prompt includes paper titles, summaries, and source URLs

#### Scenario: SQX catalog template includes available indicators

- GIVEN SQX docs are scanned for RSI, BB, MACD definitions
- WHEN the SQX catalog template is selected
- THEN the prompt lists valid SQX indicator names and parameter ranges

## MODIFIED Requirements

### Requirement: Error Handling — Fallback

If the LLM call fails, the system MUST fall back to the classic `ResearchAgent` and log the failure. If a new provider fails, the system MUST log the failure and continue with remaining providers. If ALL providers fail, the system MUST return empty data structures and let the LLM generate hypotheses from objective text alone.

(Previously: Only LLM call failure triggered fallback)

#### Scenario: All providers fail

- GIVEN YahooFinance, FRED, web search, RSS, and new providers all raise exceptions
- WHEN `fetch_data()` runs
- THEN fundamental, macro, and news are empty dicts/lists
- AND the LLM prompt is built with only the objective text
