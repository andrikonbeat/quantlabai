# Archive: Web Research for LLM Agent

**Status**: archived
**Date**: 2026-07-30
**Mode**: SDD (auto) — explore → propose → spec → design → tasks → apply → verify → archive

## Summary

Wired the existing `WebSearchProvider` and `RSSNewsProvider` into `LLMResearchAgent.fetch_data()` so the LLM gets real web research context (news, articles, source URLs) before generating hypotheses. Previously the agent fetched YahooFinance fundamentals and FRED macro data but `news_data` was always empty — the `PROMPT_TEMPLATES["news"]` template and both providers existed but were never called.

## What Was Built

- **Lazy-init providers**: `_get_web_search()` / `_get_rss_news()` mirroring the `_get_yahoo()` / `_get_fred()` pattern
- **Web search wiring**: `search_web(market_query)` where `market_query = context.get("market", objective)`
- **RSS news wiring**: `fetch_news(ticker)` when ticker is non-empty
- **URL visibility**: articles_text format string includes `(url)` so the LLM sees citation sources
- **Graceful degradation**: provider failures are non-fatal (logger.warning + continue); LLM still works on fundamental/macro data alone

## Files Changed

| File | Action |
|------|--------|
| `sdk/quantlab/agents/llm_research_agent.py` | Modified (+51 lines) |
| `sdk/tests/agents/test_llm_agent_news.py` | Created (19 tests) |

## Verification

- 19/19 news tests pass
- 170/170 agent tests pass
- 4/4 spec requirements compliant
- All acceptance criteria met
- Classic `ResearchAgent` fallback unchanged

## Key Decisions

1. Lazy-init pattern matches existing `_get_yahoo()` / `_get_fred()` — zero configuration plumbing
2. Search query = `context.get("market", objective)` — market more specific than objective
3. URLs included directly in articles_text — minimal change, LLM cites naturally
4. Both providers already have TokenBucket rate limiting + cache + retry — no new deps

## Next Steps

The research layer now has real web context. Next pipeline pieces to build (per full-flow gap analysis):
- Config refutation layer (review BuilderConfig before execution)
- LLM-capable monitor during SQX generation
- Post-result analysis (overfitting detection, strategy quality)
- Reconfiguration loop (reconfigure and relaunch based on results)
