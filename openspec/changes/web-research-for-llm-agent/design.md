# Design: Web Research for LLM Agent

## Technical Approach

Wire existing `WebSearchProvider` and `RSSNewsProvider` into `LLMResearchAgent.fetch_data()` using the established lazy-init pattern. Two new async provider calls before the return statement populate `news_data`, and the existing `if news:` guard in `build_prompt()` activates automatically. URLs from each result are included in the prompt's articles text so the LLM can cite them in `source_urls`.

## Architecture Decisions

### Decision: Provider Lazy-Init Pattern

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Constructor injection | Requires config plumbing, changes caller | Rejected — inconsistent with existing yahoo/fred pattern |
| Factory method | Over-engineered for 40-line change | Rejected |
| `_get_web_search()` / `_get_rss_news()` + `None` instance vars | Matches `_get_yahoo()` exactly, zero configuration | **Chosen** |

### Decision: Search Query Derivation

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Always use objective text | Generic, misses market context | Rejected |
| Hardcode query | No dynamism | Rejected |
| `context.get("market", objective)` for web; ticker for RSS | Market is more specific than objective; RSS works best with ticker symbols | **Chosen** |

### Decision: URL Visibility in Prompt

| Option | Tradeoff | Decision |
|--------|----------|----------|
| New `source_urls` key in data dict | Extra plumbing, no prompt integration | Rejected |
| Modify prompt template | Breaks template reuse | Rejected |
| Include `(url)` in articles_text format string | Minimal change, LLM sees URLs alongside content naturally | **Chosen** |

## Data Flow

```
fetch_data(objective, market_context)
  │
  ├── YahooFinance.fetch(ticker)       ──→ fundamental_data  (existing)
  ├── FRED.fetch(series_id)           ──→ macro_data         (existing)
  │
  ├── market_query = context.get("market", objective)
  ├── WebSearchProvider.search_web(market_query)  (NEW)
  │   └── success → news_data.append({"title", "url", "summary", "source"})
  │   └── failure → logger.warning(), continue
  │
  ├── RSSNewsProvider.fetch_news(ticker)           (NEW, guarded: if ticker)
  │   └── success → news_data.append({"title", "url", "summary", "source"})
  │   └── failure → logger.warning(), continue
  │
  └── return {ticker, fundamental, macro, news}  (unchanged shape)
```

When `build_prompt()` processes `data["news"]`, the `if news:` guard (existing line 238) activates. The articles_text format includes the URL so the LLM sees citation sources.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/llm_research_agent.py` | Modify | +2 imports, +2 instance vars in `__init__`, +2 lazy-init methods (~8 lines), ~18 lines of news fetching in `fetch_data()`, 1 line format change in `build_prompt()` |

Total: ~40 net lines added, ~50 with gaps.

## Interfaces / Contracts

No new interfaces. Consumes existing providers:

| Provider | Method | Returns |
|----------|--------|---------|
| `WebSearchProvider` | `search_web(query: str)` → `list[WebResult]` | `{title, url, snippet, source}` |
| `RSSNewsProvider` | `fetch_news(query: str)` → `list[NewsItem]` | `{title, url, source, published_date, summary, sentiment}` |

## Error Handling Chain

```
search_web() fails (ProviderError, ValueError, or any Exception)
  → logger.warning() → continue with empty web results

fetch_news() fails (ValueError, or any Exception)
  → logger.warning() → continue with empty RSS results

Both fail
  → news_data stays [] → if news: guard skips section
  → LLM still gets fundamental + macro data

Empty market_context (None or {})
  → market_query = "" → ValueError caught → empty web results
  → ticker = "" → RSS not attempted → empty news
  → fundamental/macro still fetched as before
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_get_web_search()` / `_get_rss_news()` lazy-init | Assert same instance on repeated calls |
| Unit | `fetch_data()` populates news | Mock providers to return data, assert `data["news"]` non-empty |
| Unit | Graceful degradation | Mock providers to raise, assert `data["news"]` is `[]`, no exception propagates |
| Unit | Empty market_context | Call with `None`, assert fundamental/macro still populated, news empty |
| Unit | `build_prompt()` includes URLs | Assert URL substring appears in formatted news articles text |
| Existing | All existing tests pass | `pytest tests/agents/test_llm_agent.py -q` |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. Revert commit to remove the two provider init methods and `fetch_data()` additions; agent continues with Yahoo/FRED data only.

## Open Questions

None.
