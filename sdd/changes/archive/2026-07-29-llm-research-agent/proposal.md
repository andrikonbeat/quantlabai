# Proposal: LLM Research Agent

## Intent

Current `ResearchAgent` is 100% deterministic — keyword-parses objectives, generates hypotheses without consulting real data. No LLM, no market context, no news/sentiment. This limits hypothesis quality to hardcoded rules. An LLM-powered agent that consumes real fundamental data, news, and macroeconomic indicators will produce grounded, adaptive trading hypotheses.

## Scope

### In Scope
- `LLMResearchAgent` — new agent coexisting alongside `ResearchAgent`, selected at runtime via `AgentConfig.model`
- `data/news/` — `NewsProvider` ABC + RSS/web search implementations (feedparser, duckduckgo-search)
- `LLMConfig` model + extended `HypothesisConfig` (source_urls, data_signals fields)
- `LLMResearchStage` registered as `"research_llm"` in `StageRegistry`
- `ResearchDirector` routing: if `AgentConfig.model != ""` → use LLM agent, else classic
- New deps: `openai`, `beautifulsoup4`, `feedparser`, `duckduckgo-search`
- TokenBucket + SqliteCache reuse for LLM API calls

### Out of Scope
- Replacing the existing `ResearchAgent`
- UI for LLM agent interaction
- Local models (API-based only: OpenAI / Anthropic)
- Social media scraping (Twitter, Reddit)
- SEC filings / earnings call transcripts

## Capabilities

### New Capabilities
- `llm-research`: LLM-powered hypothesis generation from fundamental data, news, and macro indicators
- `news-analysis`: RSS feed and web search data provider with caching and rate limiting

### Modified Capabilities
- `research-dsl`: Add `LLMConfig` model (provider, model, temperature, max_tokens) + `source_urls`/`data_signals` to `HypothesisConfig`
- `pipeline-core`: Add `research_llm` stage type to registry + runtime routing in `ResearchDirector`

## Approach

`LLMResearchAgent` consumes `YahooFinanceProvider` + `FredProvider` + new `NewsProvider` → builds a structured prompt → calls OpenAI/Anthropic API → parses response into `ResearchConfig` with `HypothesisConfig[]` each carrying `source_urls` for auditability. Falls back to classic `ResearchAgent` on timeout/error. Reuses existing `TokenBucket` + `SqliteCache` for API cost control.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/llm_research_agent.py` | New | LLM-powered agent |
| `sdk/quantlab/data/news/` | New | NewsProvider + RSS + web impls |
| `sdk/quantlab/dsl/models.py` | Modified | Add LLMConfig, extend HypothesisConfig |
| `sdk/quantlab/pipeline/registry.py` | Modified | Register "research_llm" stage |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modified | (optional) LLMResearchStage ABC |
| `sdk/quantlab/agents/research_director.py` | Modified | Runtime routing classic vs LLM |
| `pyproject.toml` | Modified | New dependencies |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| API costs | Med | TokenBucket + SqliteCache for LLM; cheap model for web analysis |
| Hallucinations | High | Require `source_urls` + ticker validation in output |
| Timeouts/failures | Low | httpx.AsyncClient timeout + fallback to classic ResearchAgent |
| Rate limits (news) | Low | TokenBucket pattern already in place |

## Rollback Plan

Remove `"research_llm"` from `StageRegistry`, delete `llm_research_agent.py` and `data/news/`. Set `AgentConfig.model = ""` in all configs — pipeline falls back to classic `ResearchAgent` with zero code changes elsewhere.

## Dependencies

- `openai` / `anthropic` SDK
- `beautifulsoup4`, `feedparser`, `duckduckgo-search`
- Existing: `httpx`, `YahooFinanceProvider`, `FredProvider`, `TokenBucket`, `SqliteCache`

## Success Criteria

- [ ] `LLMResearchAgent` generates `ResearchConfig` with hypotheses grounded in real data sources
- [ ] Tests pass with mocked HTTP (respx) — no real API calls needed
- [ ] Existing pipeline runs unchanged with `AgentConfig.model = ""`
- [ ] `NewsProvider` follows same ABC + caching + rate-limit pattern as fundamental providers
- [ ] duckduckgo-search works without API key
