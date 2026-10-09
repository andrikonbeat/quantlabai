# Tasks: LLM Research Agent

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~800 (350 + 300 + 150) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|---------------------|-----------------|-------------------|
| 1 | Models + news providers | PR 1 | `pytest -k "llm_config or news_provider"` | N/A — no agent deps | Revert `dsl/models.py` + `data/news/` |
| 2 | LLM Research Agent | PR 2 | `pytest -k "llm_agent or prompts"` | `pytest -k "llm_fallback"` with respx mocks | Revert `llm_research_agent.py` + `prompts.py` |
| 3 | Pipeline wiring | PR 3 | `pytest -k "research_llm or routing"` | `pytest tests/integration -k "research_llm"` | Remove `"research_llm"` from registry |

## PR 1: LLMConfig + News Providers

- [x] 1.1 RED: LLMConfig validation — provider enum, defaults, temperature range
- [x] 1.2 RED: HypothesisConfig extended — null vs populated llm_rationale/source_urls
- [x] 1.3 Add `LLMConfig` + extend `HypothesisConfig` in `dsl/models.py`
- [x] 1.4 RED: NewsItem/WebResult — creation, sentiment optional, empty query ValueError
- [x] 1.5 Create `data/news/models.py` — NewsItem, WebResult dataclasses
- [x] 1.6 Create `data/news/base.py` — NewsProvider(AbstractDataProvider) ABC
- [x] 1.7 RED: RSSNewsProvider — dedup by URL, skip 500 feed, parse articles
- [x] 1.8 Create `data/news/rss.py` — RSSNewsProvider with httpx + feedparser
- [x] 1.9 RED: WebSearchProvider — results parse, rate-limit retry, ProviderError
- [x] 1.10 Create `data/news/web_search.py` — WebSearchProvider (duckduckgo-search)
- [x] 1.11 Create `data/news/__init__.py` — public exports
- [x] 1.12 Add deps: feedparser, beautifulsoup4, duckduckgo-search to `pyproject.toml`

## PR 2: LLM Research Agent

- [x] 2.1 RED: prompt template — fundamental includes financials, technical excludes macro
- [x] 2.2 Create `agents/prompts.py` — PROMPT_TEMPLATES per analysis type
- [x] 2.3 RED: parse_response() — valid/invalid JSON → ResearchConfig / fallback
- [x] 2.4 RED: LLM timeout/API error → classic ResearchAgent fallback + warning log
- [x] 2.5 Create `agents/llm_research_agent.py` — fetch → build_prompt → call_llm → parse → validate → generate_config
- [x] 2.6 RED: output validation — source_urls required, invalid ticker rejected
- [x] 2.7 Add output validation (source_urls, ticker correctness)
- [x] 2.8 Add `openai` dep to `pyproject.toml`

## PR 3: Pipeline Wiring (COMPLETE)

- [x] 3.1 RED: StageRegistry returns LLMResearchStage for "research_llm", RegistryError for unknown
- [x] 3.2 Create `LLMResearchStage` in `pipeline/stages/agent_stages.py` — same requires/provides as ResearchStage
- [x] 3.3 Register `"research_llm"` → LLMResearchStage wrapper in `registry._register_agent_stages()`
- [x] 3.4 RED: ResearchDirector routing — model="" → classic, model="gpt-4" → LLM, LLM fail → classic fallback
- [x] 3.5 Modify `ResearchDirector.build_pipeline()` for AgentConfig.model-based routing
- [x] 3.6 Integration: registry lookup + routing + fallback with mocked providers
