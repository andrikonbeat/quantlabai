# Proposal: Web Research for LLM Agent

## Intent

LLMResearchAgent today returns hypotheses with hardcoded source_urls — it fetches fundamentals and macro data but never populates the `news` field. The `PROMPT_TEMPLATES["news"]` template and both `WebSearchProvider` / `RSSNewsProvider` exist but are never called. This closes the gap: hypotheses become data-driven with real citations.

## Scope

### In Scope
- Wire `WebSearchProvider.search_web()` into `LLMResearchAgent.fetch_data()`
- Wire `RSSNewsProvider.fetch_news()` into `fetch_data()`
- Populate `news` data dict with real results, triggering the news prompt section
- Add `source_urls` from web results to the prompt context so the LLM can cite them
- ~40 lines of new code in `llm_research_agent.py` only

### Out of Scope
- Classic `ResearchAgent` — unchanged, stays as fallback
- `HypothesisBuilder` — no changes
- Pipeline orchestration — no stage or DAG changes
- New provider creation — both providers already exist
- Sentiment analysis on news — `NewsItem.sentiment` stays `None`

## Capabilities

### New Capabilities
None — both `llm-research` and `news-analysis` specs already cover this behavior. Implementation gap only.

### Modified Capabilities
None — no spec-level requirement changes. `llm-research` spec already expects populated `source_urls`, `data_sources`, and news data in `fetch_data()` return.

## Approach

1. Add `_get_web_search()` / `_get_rss_news()` lazy-init methods to `LLMResearchAgent` (mirror existing pattern for yahoo/fred).
2. In `fetch_data()`, call `search_web(market_context)` and `fetch_news(ticker)` before the return statement. Merge results into `news_data` list.
3. Extract URLs from `WebResult` / `NewsItem` objects and attach them as `source_urls` context in the prompt.
4. The existing `if news:` guard in `build_prompt()` activates automatically once `news_data` is non-empty.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/llm_research_agent.py` | Modified | Add provider inits + news/web fetching in `fetch_data()` |
| `sdk/quantlab/agents/prompts.py` | None | Template already ready |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| DuckDuckGo rate limits (3 req/s) | Medium | `WebSearchProvider` has built-in `TokenBucket` + retry; errors are logged and non-fatal |
| LLM prompt exceeds token limits | Low | News is capped at 10 articles in existing code; web results also limited |
| RSS feed downtime | Medium | `RSSNewsProvider` skips failed feeds gracefully; empty news still allows fundamental-only hypotheses |
| `feedparser` not installed | Low | Provider returns `[]` with warning; no crash |

## Rollback Plan

Revert `llm_research_agent.py` to remove the two provider init methods and the `fetch_data()` additions. The agent continues working with fundamental/macro data only, as before.

## Dependencies

- `duckduckgo-search` package — already optional in `WebSearchProvider`
- `feedparser` package — already optional in `RSSNewsProvider`
- No new dependencies

## Success Criteria

- [ ] `LLMResearchAgent.execute()` returns hypotheses with non-empty `source_urls`
- [ ] `fetch_data()` returns `news` field with actual `WebResult` / `NewsItem` entries
- [ ] `build_prompt()` includes the news section in the LLM prompt
- [ ] All existing tests pass unchanged
- [ ] Fallback to classic `ResearchAgent` still works on provider failure
