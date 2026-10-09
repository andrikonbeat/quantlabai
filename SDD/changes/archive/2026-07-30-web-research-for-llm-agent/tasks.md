# Tasks: Web Research for LLM Agent

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~40 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

## Phase 1: Foundation — Imports & Instance Vars

- [x] 1.1 **Add imports** — import `WebSearchProvider` and `RSSNewsProvider` from their module paths at the top of `llm_research_agent.py`
- [x] 1.2 **Add instance vars** — add `_web_search: WebSearchProvider | None = None` and `_rss_news: RSSNewsProvider | None = None` in `__init__()`
- [x] 1.3 **Add lazy-init methods** — add `_get_web_search()` and `_get_rss_news()` methods below `_get_fred()`, mirroring the `if self._x is None: self._x = X()` pattern

## Phase 2: Core — Wire Providers in `fetch_data()`

- [x] 2.1 **Wire web search** — before `return` in `fetch_data()`, call `_get_web_search().search_web(market_query)` where `market_query = context.get("market", objective)`. Wrap in try/except with `logger.warning()`. Append results to `news_data` as `{"title", "url", "summary", "source"}` dicts
- [x] 2.2 **Wire RSS news** — if `ticker` is non-empty, call `_get_rss_news().fetch_news(ticker)`. Wrap in try/except with `logger.warning()`. Append results to `news_data` as dicts

## Phase 3: Prompt — URL Visibility

- [x] 3.1 **Update format string** — in `build_prompt()`, change the articles_text f-string to include `url`: `f"- {a.get('title', '')} ({a.get('url', '')}): {a.get('summary', '')}"`

## Phase 4: Verification

- [x] 4.1 **Run tests** — `python3 -m pytest tests/ -q --tb=short -x` and confirm all pass
