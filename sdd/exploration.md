# Exploration: QuantLab Research Agent Enhancements

## 1. Current Architecture Map

### 1.1 ResearchAgent (`sdk/quantlab/agents/research_agent.py`)

**Role**: Deterministic hypothesis generation from objectives + Knowledge Lake queries.

**Key methods**:
- `generate_config()` — Parses objectives to extract market/timeframe, generates hardcoded building blocks (RSI, Bollinger, Donchian, EMA, ATR), strategies, and acceptance criteria.
- `formulate_hypotheses()` — Produces 3-5 hypotheses based on keyword matching (mean-reversion, breakout, momentum, volatility). Confidence scores are simple heuristics: `min(0.7, 0.4 + avg_historical_sharpe * 0.2)`.
- `query_knowledge_lake()` — Uses `QueryBuilder` to filter campaigns by Sharpe, date, tags.
- `_extended_knowledge_query()` — Adds max-drawdown filtering for capital constraints.
- `run()` — Pipeline integration: reads config, generates ResearchConfig, queries lake, formulates hypotheses, writes to context artifacts.

**Pain points**:
- Hardcoded keyword matching — only detects "mean-reversion", "breakout", "momentum", "trend", "volatility", "atr", "squeeze".
- Building blocks are limited to 5 indicators (RSI, BB, Donchian, EMA, ATR).
- Hypothesis generation is combinatorial but bounded by hardcoded templates.
- No parametric diversification — repeats similar indicator combinations.
- Confidence calibration is a simple linear function of historical Sharpe.

### 1.2 LLMResearchAgent (`sdk/quantlab/agents/llm_research_agent.py`)

**Role**: LLM-powered research with multi-source data fetching.

**Data providers**:
- `YahooFinanceProvider` — fundamental data (P/E, P/B, ROE, revenue, debt, market cap, sector).
- `FredProvider` — macro data (GDP, CPI, Fed funds, unemployment).
- `WebSearchProvider` — web search results.
- `RSSNewsProvider` — RSS news feeds.

**Key methods**:
- `fetch_data()` — Orchestrates provider calls with lazy initialization and error isolation.
- `build_prompt()` — Combines fundamental, technical, macro, and news templates.
- `call_llm()` — Supports `opencode` (local CLI) and `openai` providers. Anthropic raises `ValueError`.
- `parse_response()` — Parses JSON response into ResearchConfig with validation.
- `validate_output()` — Ensures hypotheses have `source_urls` and valid ticker symbols.
- `generate_config()` — Full pipeline: fetch → prompt → LLM → parse → validate → fallback.

**Fallback**: Transparent fallback to `ResearchAgent` on any failure (ImportError, API error, parse error).

### 1.3 HypothesisBuilder (`sdk/quantlab/agents/hypothesis_builder/__init__.py`)

**Role**: Transforms hypotheses into validated building blocks and strategies.

**Modes**:
- `RuleMode` — Keyword-based deterministic building block generation.
- `LLMMode` — LLM-based generation via `LLMResearchAgent.call_llm()`.

**Flow**:
1. `build()` accepts list of `HypothesisConfig`.
2. Routes to `_build_with_llm()` or `_build_with_rule()`.
3. LLM mode has fallback to rule mode on any exception.
4. `_merge_and_validate()` deduplicates blocks by name, merges strategies, runs `BuildingBlockValidator`.

### 1.4 Knowledge Lake (`sdk/quantlab/knowledge/`)

**Components**:

| Component | File | Role |
|-----------|------|------|
| `KnowledgeStore` | `store.py` | Central persistence layer with circuit breaker, write buffering, pipeline run history, tagging, linking, agent memory, phase envelopes. |
| `QueryBuilder` | `query.py` | Fluent API for campaign queries (Sharpe, profit factor, win rate, max drawdown, tags, date, text search, agent memory search, similar campaigns). |
| `Indexer` | `indexer.py` | Enhanced indexer that reads campaign stats YAML, extracts metrics, manages tags and links. Supports v1→v2 migration. |
| `MemoryCaptureService` | `memory_capture.py` | Write side of phase-boundary memory loop. |
| `context.py` | `context.py` | Read side: `compose_prior_context()` loads prior decisions and similar campaigns for injection into phase envelopes. |
| `models.py` | `models.py` | Dataclasses: `CampaignMetrics`, `CampaignSummary`, `QueryFilter`, `QueryResult`, `AgentMemoryEntry`, `PhaseEnvelope`, `ParameterMatrixEntry`, `FeedbackRecord`, `MaintenancePlan`. |

**Embeddings**: `find_similar_campaigns()` loads `.npy` vectors from `embeddings/` and computes cosine similarity. Falls back to `_find_similar_text()` which builds sparse token+char n-gram vectors from agent memory and campaign.md.

**Current state**: The Knowledge Lake is a structured directory with YAML/JSON artifacts. It has the *scaffolding* for embeddings (directory exists, method exists) but no actual embedding generation pipeline. Text-based similarity is the active fallback.

---

## 2. Pain Points and Limitations

### 2.1 ResearchAgent
1. **Brittle keyword matching**: Only 6 keyword categories. "statistical arbitrage" or "pairs trading" produce no blocks.
2. **Indicator poverty**: Hardcoded to 5 indicators. No volume indicators, no custom indicators, no SQX-specific indicators.
3. **No parametric diversification**: Always uses default parameters (RSI 14, BB 20/2, etc.). Generates near-identical hypotheses for similar objectives.
4. **Shallow confidence calibration**: Single linear formula based on average historical Sharpe. Ignores sample size, regime, market conditions.
5. **No pre-hypothesis validation**: Generates hypotheses first, validates later. Wastes cycles on obviously bad ideas.

### 2.2 LLMResearchAgent
1. **Limited providers**: Only YahooFinance, FRED, WebSearch, RSS. No academic papers, no quantitative blogs, no stock screeners.
2. **No source validation**: `validate_output()` only checks that `source_urls` is non-empty. Doesn't verify URL reachability, relevance, or authority.
3. **Prompt engineering is basic**: Static templates with no few-shot examples, no chain-of-thought, no structured reasoning steps.
4. **LLM output is unconstrained**: JSON parsing is fragile. LLM can produce invalid JSON, missing fields, or hallucinated indicators.
5. **No parametric diversification enforcement**: LLM can produce similar parameter sets across hypotheses.
6. **No Sharpe calibration**: LLM confidence scores are uncalibrated — LLMs are overconfident.

### 2.3 HypothesisBuilder
1. **Rule mode is extremely limited**: Only 3 hardcoded building blocks (RSI_MeanReversion, BollingerBands, DonchianBreakout, EMATrend, ATRFilter).
2. **LLM mode has no context**: `_build_prompt()` only includes hypothesis rationale, no Knowledge Lake context, no historical performance data.
3. **No strategy type awareness**: Doesn't differentiate between mean-reversion, momentum, breakout, or volatility strategy requirements.

### 2.4 Knowledge Lake
1. **No real semantic search**: `find_similar_campaigns()` falls back to text-based similarity (token overlap). No embedding generation pipeline.
2. **No metrics by strategy type**: `QueryFilter` filters by global metrics but not by strategy category (e.g., "show me all mean-reversion strategies with Sharpe > 1.5").
3. **No automatic feedback loop**: Campaign results are stored but not automatically fed back into hypothesis generation or confidence calibration.
4. **Static index**: `rebuild_index()` is manual or triggered by code. No incremental updates.
5. **No content-based retrieval**: Can't search for "strategies using RSI with oversold < 25" — only tag/text matching.

---

## 3. Feasibility Analysis for Proposed Enhancements

### Front 1: Multi-Source Research

#### 3.1.1 SSRN/arXiv Papers
**Feasibility**: Medium
- **Pros**: Academic papers contain validated factor models, regime detection methods, and novel indicators. RSS feeds from arXiv (quant-ph, q-fin.ST, q-fin.PM) are freely available.
- **Cons**: Papers are dense, need summarization. SSRN requires web scraping (may have rate limits). arXiv has an API but returns XML/JSON that needs parsing.
- **Integration**: Add `AcademicPapersProvider` to `sdk/quantlab/data/news/` or a new `sdk/quantlab/data/academic/`. Follow the `DatasourceHandler` pattern. Fetch abstract + key findings, inject into `LLMResearchAgent.build_prompt()`.
- **Complexity**: Medium. Need parsing, summarization, and relevance filtering.

#### 3.1.2 Quantitative Blogs (Quantocracy, QuantStart)
**Feasibility**: High
- **Pros**: These sites have RSS feeds. `RSSNewsProvider` already exists and can be extended.
- **Cons**: Content quality varies. Need deduplication and relevance scoring.
- **Integration**: Add blog-specific RSS feeds to `RSSNewsProvider` or create `QuantBlogProvider`. Simple extension.
- **Complexity**: Low.

#### 3.1.3 SQX Built-in Documentation
**Feasibility**: High
- **Pros**: SQX has built-in indicators and parameters. Documentation can be extracted from the SQX installation or configuration files.
- **Cons**: Requires SQX installation. Documentation format may vary by version.
- **Integration**: Create `SQXDocProvider` that reads SQX's parameter files (`structured/sqx-kb/` already exists). Inject indicator descriptions into prompts.
- **Complexity**: Low-Medium.

#### 3.1.4 Stock Screeners (Finviz, AlphaVantage)
**Feasibility**: Medium
- **Pros**: Finviz has a free API for screeners. AlphaVantage has fundamental and technical indicators.
- **Cons**: Finviz free tier is rate-limited. AlphaVantage requires API key. Both need parsing HTML/JSON responses.
- **Integration**: Add `FinvizProvider` and `AlphaVantageProvider` to `sdk/quantlab/data/fundamental/`. Extend `fetch_data()` in `LLMResearchAgent`.
- **Complexity**: Medium. HTML parsing for Finviz is brittle.

### Front 2: Improved LLM Hypothesis Generation

#### 3.2.1 Better Prompt Engineering
**Feasibility**: High
- **Pros**: The prompt templates in `sdk/quantlab/agents/prompts.py` are static. Adding few-shot examples, chain-of-thought, and structured reasoning is purely a prompt engineering task.
- **Cons**: Prompt length increases. Need to manage token limits.
- **Integration**: Modify `build_prompt()` in `LLMResearchAgent` and `_build_prompt()` in `LLMMode`. Add template versioning.
- **Complexity**: Low.

#### 3.2.2 Forced Parametric Diversification
**Feasibility**: High
- **Pros**: Can enforce parameter diversity in `HypothesisConfig` before LLM call, or post-process LLM output to ensure parameter ranges differ.
- **Cons**: May conflict with LLM's "best" parameters. Need to balance diversity with quality.
- **Integration**: Add `DiversificationEnforcer` class. Run after `formulate_hypotheses()` in `ResearchAgent` or after `parse_response()` in `LLMResearchAgent`.
- **Complexity**: Low-Medium.

#### 3.2.3 Pre-Hypothesis Validation
**Feasibility**: Medium
- **Pros**: Validate against Knowledge Lake before committing. If similar hypothesis failed recently, skip or adjust.
- **Cons**: Requires fast similarity search. Current text-based similarity may be too noisy.
- **Integration**: Add `PreValidationLayer` that queries `QueryBuilder` for similar historical hypotheses, checks failure rates.
- **Complexity**: Medium. Depends on Front 3 (semantic search).

#### 3.2.4 Tag-Based Sharpe Calibration
**Feasibility**: Medium-High
- **Pros**: `KnowledgeStore` already supports tagging and metrics extraction. Can compute Sharpe distributions by tag.
- **Cons**: Requires sufficient historical data per tag. Cold-start problem for new tags.
- **Integration**: Add `SharpeCalibrator` class that queries `QueryBuilder` grouped by tags, computes percentiles, adjusts confidence scores.
- **Complexity**: Medium.

### Front 3: Knowledge Lake as Real Knowledge Base

#### 3.3.1 Semantic Query with Embeddings
**Feasibility**: Medium
- **Pros**: The infrastructure exists (`embeddings/` directory, `find_similar_campaigns()`, `_text_corpus()`). Need to add actual embedding generation.
- **Cons**: Requires an embedding model (e.g., `sentence-transformers`, OpenAI embeddings). Adds a new dependency. Embedding generation is compute-intensive.
- **Integration**: Add `EmbeddingService` class. Generate embeddings for campaign summaries and agent memories. Store in `embeddings/` as `.npy` or `.parquet`.
- **Complexity**: Medium. Model selection, caching, incremental updates.

#### 3.3.2 Metrics by Strategy Type
**Feasibility**: Medium
- **Pros**: `CampaignMetrics` already exists. Need to add `strategy_type` field and aggregate logic.
- **Cons**: Requires tagging campaigns with strategy types. Current tagging is free-form.
- **Integration**: Extend `QueryFilter` with `strategy_type`. Add aggregation methods to `QueryBuilder` or `Indexer`.
- **Complexity**: Low-Medium.

#### 3.3.3 Automatic Feedback Loop
**Feasibility**: Medium
- **Pros**: `MemoryCaptureService` and `compose_prior_context()` already exist. Need to close the loop: campaign results → hypothesis adjustment.
- **Cons**: Feedback loop design is non-trivial. Need to avoid overfitting to historical data.
- **Integration**: Add `FeedbackLoop` service that reads campaign results, updates hypothesis confidence, stores in `agent-memory/`.
- **Complexity**: Medium-High.

---

## 4. Integration Points and Dependencies

### 4.1 Current Integration Points

| Integration Point | Current State | Enhancement Impact |
|-------------------|---------------|-------------------|
| `ResearchAgent.generate_config()` | Produces ResearchConfig with hardcoded hypotheses | Front 2: Add diversification, pre-validation, calibration |
| `LLMResearchAgent.fetch_data()` | YahooFinance, FRED, WebSearch, RSS | Front 1: Add new providers |
| `LLMResearchAgent.build_prompt()` | Static templates | Front 2: Better prompt engineering |
| `HypothesisBuilder.build()` | Rule mode / LLM mode | Front 2: LLM mode with context |
| `KnowledgeStore.find_similar_campaigns()` | Text-based fallback | Front 3: Embeddings replace text similarity |
| `QueryBuilder` | Filter by metrics, tags, date | Front 3: Strategy type filters, semantic search |

### 4.2 Dependency Graph

```
Front 1 (Multi-source)
├── FinvizProvider ──┐
├── AlphaVantageProvider ──┤
├── AcademicPapersProvider ──┤
└── SQXDocProvider ──┘
         │
         ▼
LLMResearchAgent.fetch_data() ──► build_prompt() ──► call_llm()
         │
         ▼
Front 2 (LLM hypothesis generation)
├── Prompt templates ──┐
├── DiversificationEnforcer ──┤
├── PreValidationLayer ──┤
└── SharpeCalibrator ──┘
         │
         ▼
HypothesisBuilder ──► BuildingBlockValidator
         │
         ▼
Front 3 (Knowledge Lake)
├── EmbeddingService ──► find_similar_campaigns()
├── StrategyTypeAggregator ──► QueryBuilder
└── FeedbackLoop ──► agent-memory/
```

### 4.3 Key Dependencies
1. **Front 3 (embeddings) enables Front 2 (pre-validation)**: Pre-validation needs semantic similarity to find related historical hypotheses.
2. **Front 1 (providers) enables Front 2 (better prompts)**: More data sources → richer prompts → better LLM output.
3. **Front 2 (calibration) depends on Front 3 (metrics by type)**: Tag-based Sharpe calibration needs strategy type aggregation.

---

## 5. Recommended Implementation Order

### Phase 1: Foundation (Front 3 — Knowledge Lake)
**Rationale**: The Knowledge Lake is the force multiplier. Better knowledge retrieval makes everything else more effective.

1. **Semantic embeddings** (3.3.1)
   - Add `EmbeddingService` class.
   - Generate embeddings for existing campaign summaries.
   - Replace text-based similarity with cosine similarity on dense vectors.
   - **Effort**: Medium. **Risk**: Low.

2. **Metrics by strategy type** (3.3.2)
   - Extend `CampaignMetrics` with `strategy_type`.
   - Add aggregation methods to `Indexer`.
   - **Effort**: Low-Medium. **Risk**: Low.

### Phase 2: Data Expansion (Front 1 — Multi-source)
**Rationale**: More data sources improve LLM prompt quality immediately.

3. **Quantitative blog RSS feeds** (3.1.2)
   - Extend `RSSNewsProvider` with blog feeds.
   - **Effort**: Low. **Risk**: Low.

4. **SQX built-in documentation** (3.1.3)
   - Create `SQXDocProvider`.
   - Read from `structured/sqx-kb/`.
   - **Effort**: Low-Medium. **Risk**: Low.

5. **Academic papers** (3.1.1) — optional
   - Create `AcademicPapersProvider`.
   - **Effort**: Medium. **Risk**: Medium (parsing complexity).

6. **Stock screeners** (3.1.4) — optional
   - Create `FinvizProvider`, `AlphaVantageProvider`.
   - **Effort**: Medium. **Risk**: Medium-High (API stability).

### Phase 3: LLM Intelligence (Front 2 — Better Hypothesis Generation)
**Rationale**: With rich data and semantic search, LLM prompts become much more powerful.

7. **Better prompt engineering** (3.2.1)
   - Add few-shot examples, chain-of-thought.
   - Version templates.
   - **Effort**: Low. **Risk**: Low.

8. **Forced parametric diversification** (3.2.2)
   - Add `DiversificationEnforcer`.
   - **Effort**: Low-Medium. **Risk**: Low.

9. **Tag-based Sharpe calibration** (3.2.4)
   - Depends on Phase 1 (strategy type aggregation).
   - Add `SharpeCalibrator`.
   - **Effort**: Medium. **Risk**: Medium (calibration accuracy).

10. **Pre-hypothesis validation** (3.2.3)
    - Depends on Phase 1 (semantic search).
    - Add `PreValidationLayer`.
    - **Effort**: Medium. **Risk**: Medium (false positives).

### Phase 4: Closed Loop (Front 3 — Feedback)
**Rationale**: After the system can generate good hypotheses, close the loop.

11. **Automatic feedback loop** (3.3.3)
    - Add `FeedbackLoop` service.
    - Connect campaign results to hypothesis adjustment.
    - **Effort**: Medium-High. **Risk**: High (overfitting, feedback stability).

---

## 6. Risks and Mitigation Strategies

### 6.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|-------|-----------|--------|------------|
| **Embedding model dependency** | Medium | High | Start with lightweight model (`all-MiniLM-L6-v2`). Make embedding generation optional with text-based fallback. |
| **LLM hallucination of indicators** | High | Medium | Strict JSON schema validation. Post-parse validation against known SQX indicator registry. |
| **Rate limiting on external APIs** | High | Medium | Circuit breaker pattern (already exists for LLM). Cache responses. Exponential backoff. |
| **Knowledge Lake bloat** | Medium | Medium | Implement retention policies. Archive old campaigns. Compress embeddings. |
| **Feedback loop instability** | Medium | High | Start with read-only recommendations. Add human-in-the-loop gate before auto-adjusting hypotheses. |

### 6.2 Architectural Risks

| Risk | Likelihood | Impact | Mitigation |
|-------|-----------|--------|------------|
| **Tight coupling between agents and Knowledge Lake** | Medium | High | Define clear interfaces (`QueryBuilder`, `KnowledgeStore`). Use dependency injection. |
| **Prompt engineering drift** | Medium | Medium | Version prompts in `knowledge/structured/prompts/`. A/B test new prompts. |
| **Provider availability** | High | Low | Graceful degradation. Each provider is optional (already follows this pattern). |

### 6.3 Data Risks

| Risk | Likelihood | Impact | Mitigation |
|-------|-----------|--------|------------|
| **Insufficient historical data for calibration** | High | Medium | Bayesian smoothing for Sharpe estimates. Minimum sample size thresholds. |
| **Noisy text-based similarity** | High | Medium | Prioritize dense embeddings. Use tag-based filtering as pre-filter. |
| **Strategy type misclassification** | Medium | Medium | Multi-label classification. Human review for ambiguous cases. |

### 6.4 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|-------|-----------|--------|------------|
| **Increased latency from multi-source fetching** | High | Medium | Parallelize provider calls (already async). Set per-provider timeouts. Cache aggressively. |
| **LLM cost increase** | Medium | Medium | Use cheaper models for routine research. Reserve expensive models for complex hypotheses. Circuit breaker already exists. |
| **Knowledge Lake index rebuild overhead** | Low | Low | Incremental indexing. Only rebuild on write failures. |

---

## 7. Ready for Proposal

**Yes** — The codebase has clear extension points for all 3 fronts.

### What the orchestrator should tell the user:

> The QuantLab Research sub-agent system is well-architected for extension. The current `ResearchAgent` uses hardcoded keyword matching with 5 indicators. `LLMResearchAgent` already has a multi-provider data fetching layer with transparent fallback. `HypothesisBuilder` supports both rule and LLM modes. The Knowledge Lake has the directory structure, indexing, and even embedding scaffolding — but no actual embedding generation yet.
>
> **Recommended path**: Start with Knowledge Lake semantic search (Front 3) because it enables the other fronts. Then add data providers (Front 1) to enrich LLM prompts. Finally, upgrade LLM hypothesis generation (Front 2) with better prompts, diversification, and calibration.
>
> **Estimated effort**:
> - Front 3 (Knowledge Lake): 2-3 weeks
> - Front 1 (Providers): 1-2 weeks
> - Front 2 (LLM improvements): 2-3 weeks
> - Front 3 feedback loop: 1-2 weeks
>
> **Total**: 6-10 weeks for full implementation.

### Key Files for Implementation

| File | Role in Enhancements |
|------|---------------------|
| `sdk/quantlab/agents/research_agent.py` | Hypothesis generation, diversification, calibration |
| `sdk/quantlab/agents/llm_research_agent.py` | Provider orchestration, prompt building, LLM calling |
| `sdk/quantlab/agents/hypothesis_builder/__init__.py` | Mode routing, merge/validate |
| `sdk/quantlab/agents/hypothesis_builder/llm.py` | LLM prompt building, response parsing |
| `sdk/quantlab/knowledge/store.py` | Embeddings, similarity search, agent memory |
| `sdk/quantlab/knowledge/query.py` | QueryBuilder extensions (strategy type, semantic) |
| `sdk/quantlab/knowledge/indexer.py` | Strategy type aggregation, metric extraction |
| `sdk/quantlab/data/fundamental/` | New provider implementations |
| `sdk/quantlab/data/news/` | Blog and academic paper providers |
| `sdk/quantlab/agents/prompts.py` | Template versioning, few-shot examples |
