# Design: LLM Research Agent

## Technical Approach

Three independent subsystems (LLM agent, news provider, stage wiring) that plug into the existing 8-agent pipeline without modifying classic `ResearchAgent`. The `ResearchDirector` selects runtime routing based on `AgentConfig.model`: empty → classic, non-empty → LLM-powered. On LLM failure, falls back transparently to the classic agent. All new providers follow the `AbstractDataProvider` ABC + `SqliteCache` + `TokenBucket` pattern from `quantlab/data/fundamental/`.

## Architecture Decisions

| Decision | Options | Tradeoffs | Choice |
|---|---|---|---|
| LLM agent vs. classic agent extension | Subclass `ResearchAgent` vs. standalone class | Inheritance couples to internal keyword logic; standalone is easier to test, swap, and fallback | **Standalone `LLMResearchAgent`** — same `generate_config()` signature, no shared state |
| Prompt template strategy | Templates as files vs. Python dicts/functions | File templates are harder to version with code; dicts are self-contained, testable | **Python module `prompts.py`** — one dict per analysis type (fundamental, technical, macro, news) |
| News provider namespace | Inside `data/fundamental/` vs. new `data/news/` | Fundamental is for financial ratios, not news | **New `data/news/` module** — follows same ABC pattern but separate concern |
| LLM stage registration | Inline in `StageRegistry._register_agent_stages()` vs. external registration API | External is cleaner but StageRegistry already has `register()` method | **Use existing `StageRegistry.register("research_llm", LLMResearchStage)`** — called at import time |
| API client library | Direct `httpx` to OpenAI vs. `openai` SDK | SDK handles retries, streaming, auth; `httpx` is lower-level | **`openai` SDK** with `anthropic` fallback — both supported via `LLMConfig.provider` |

## Data Flow

```
User objective ──→ LLMResearchAgent.execute()
                       │
            ┌──────────┼──────────┐
            ↓          ↓          ↓
     YahooFinance   FRED      NewsProvider
     Provider     Provider   (RSS + WebSearch)
            │          │          │
            └──────────┼──────────┘
                       ↓
               PromptBuilder.build(
                 objective,
                 fundamental_data,
                 news_articles,
                 macro_indicators
               )
                       ↓
               LLMClient.call(prompt)
                       ↓
              ResponseParser.parse(json)
                       ↓
              ResearchConfig (with HypothesisConfig[])
                       ↓
             Artifacts → PipelineContext
                       │
                  (on error)
                       ↓
              Fallback: classic ResearchAgent
```

## Module Structure

```
sdk/quantlab/
├── agents/
│   ├── research_agent.py         (unchanged)
│   ├── llm_research_agent.py     [NEW] — LLMResearchAgent class
│   ├── research_director.py      [MODIFY] — routing logic
│   └── prompts.py                [NEW] — prompt templates
├── data/
│   └── news/
│       ├── __init__.py           [NEW]
│       ├── base.py               [NEW] — NewsProvider ABC
│       ├── models.py             [NEW] — NewsItem, WebResult
│       ├── rss.py                [NEW] — RSSNewsProvider
│       └── web.py                [NEW] — WebSearchProvider
├── dsl/
│   └── models.py                 [MODIFY] — add LLMConfig, extend HypothesisConfig
└── pipeline/
    ├── registry.py               [MODIFY] — register "research_llm"
    └── stages/
        └── agent_stages.py       [MODIFY] — add LLMResearchStage ABC
```

## Interfaces / Contracts

```python
# data/news/base.py
class NewsProvider(AbstractDataProvider):
    async def fetch_news(self, query: str) -> list[NewsItem]: ...
    async def search_web(self, query: str) -> list[WebResult]: ...

# agents/prompts.py
PROMPT_TEMPLATES: dict[str, str] = {
    "fundamental": "Analyze {ticker} fundamentals: PE={pe}, PB={pb}, ROE={roe}...",
    "technical": "Price action for {ticker}: recent close={close}, volume={vol}...",
    "macro": "Macro context: GDP={gdp}, CPI={cpi}, rates={rate}...",
    "news": "News sentiment for {query}: {articles}...",
}

# dsl/models.py extensions
class LLMConfig(BaseModel):
    provider: str = "openai"       # "openai" | "anthropic"
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2048
    web_sources: list[str] = []

class HypothesisConfig(BaseModel):
    # … existing fields …
    llm_rationale: str | None = None    # NEW
    source_urls: list[str] = []          # NEW
    data_sources: list[str] = []         # NEW
```

## File Changes

| File | Action | Description |
|---|---|---|
| `sdk/quantlab/agents/llm_research_agent.py` | Create | LLMResearchAgent — fetch data, build prompt, call LLM, parse, validate |
| `sdk/quantlab/agents/prompts.py` | Create | Template dicts per analysis type |
| `sdk/quantlab/data/news/__init__.py` | Create | Package export |
| `sdk/quantlab/data/news/base.py` | Create | NewsProvider(AbstractDataProvider) ABC |
| `sdk/quantlab/data/news/models.py` | Create | NewsItem, WebResult dataclasses |
| `sdk/quantlab/data/news/rss.py` | Create | RSSNewsProvider with feedparser + httpx |
| `sdk/quantlab/data/news/web.py` | Create | WebSearchProvider wrapping duckduckgo-search |
| `sdk/quantlab/dsl/models.py` | Modify | Add LLMConfig, extend HypothesisConfig with audit fields + validators |
| `sdk/quantlab/pipeline/registry.py` | Modify | Register `research_llm` → LLMResearchStage + agent wrapper |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modify | Add LLMResearchStage (same requires/provides as ResearchStage) |
| `sdk/quantlab/agents/research_director.py` | Modify | Routing: if AgentConfig.model → research_llm, else research |
| `pyproject.toml` | Modify | Add openai, anthropic, feedparser, beautifulsoup4, duckduckgo-search |

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | LLMResearchAgent.parse_response() | Inject mock LLM JSON, verify ResearchConfig fields |
| Unit | PromptBuilder.format() | Verify correct template selected per analysis type |
| Unit | NewsProvider models | Test NewsItem/WebResult creation with/without sentiment |
| Unit | LLMConfig validation | Test provider enum, temperature range, defaults |
| Integration | RSSNewsProvider.fetch_news() | respx mock for httpx, feedparser; verify dedup + error skip |
| Integration | WebSearchProvider.search_web() | Mock duckduckgo-search, verify fallback on rate limit |
| Integration | SQLiteCache + TokenBucket with news | Verify cache hits skip network, rate limit queues |
| Pipeline | StageRegistry lookup `research_llm` | Verify returns LLMResearchStage class |
| Pipeline | ResearchDirector routing | Test model="" → classic, model="gpt-4" → LLM |
| E2E | LLM → classic fallback | Mock LLM timeout → verify classic agent produces config |
| E2E | Full pipeline with LLM agent | Mock all providers + LLM → verify artifacts populated |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## PR Breakdown

| PR # | Scope | Files | Lines (est.) |
|---|---|---|---|
| **PR 1** | DSL models + NewsProvider subsystem | models.py, news/*, pyproject.toml | ~350 |
| **PR 2** | LLMResearchAgent + prompts + fallback | llm_research_agent.py, prompts.py | ~300 |
| **PR 3** | Stage wiring: registry + routing | registry.py, agent_stages.py, research_director.py | ~150 |
| **Total** | | | **~800** |

Each PR is independently testable: PR 1 adds models + data providers (no agent runtime change), PR 2 adds the agent (usable standalone), PR 3 wires into pipeline.

## Migration / Rollout

No migration required. `AgentConfig.model` defaults to `""`, preserving classic behavior. Enable LLM research by setting `model` in config — rollback is reverting that field.

## Open Questions

- [ ] LLM response schema: define exact JSON structure the agent expects from the LLM (schema versioning for prompt compatibility)
- [ ] News provider default source list: which RSS feeds ship as defaults vs. user-configured?
- [ ] Rate limit burst size for news providers (RSS fetches are cheap but duckduckgo limits aggressively)
