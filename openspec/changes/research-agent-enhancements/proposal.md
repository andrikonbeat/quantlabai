# Proposal: Research Agent Enhancements

## Intent

The current Research sub-agent generates hypotheses by combining a small set of hardcoded technical indicators (RSI, BB, Donchian, EMA, ATR) and calibrates confidence using a single global historical Sharpe average. LLM mode only consumes YahooFinance, FRED, web search, and RSS. This limits the system to rediscovering known indicator combinations and leaves it blind to quantitative literature, advanced SQX built-ins, and strategy-type-specific performance patterns. We need to upgrade Research into a true multi-source research engine that reads external knowledge, diversifies hypotheses, validates them against known SQX capabilities, and learns from its own campaign history.

## Scope

### In Scope
- New data providers: academic papers (arXiv/SSRN), quantitative blogs, SQX documentation/DSL scanner, stock screeners (Finviz/AlphaVantage)
- LLMResearchAgent prompt engineering: few-shot examples, chain-of-thought, richer context
- Hypothesis diversification: parametric variants per hypothesis (multiple indicator periods/deviation combinations)
- Pre-hypothesis validation: SQX indicator existence check, parameter range sanity, semantic coherence
- Tag-based Sharpe calibration: per-strategy-type confidence instead of single global average
- Knowledge Lake semantic search: embedding generation, similarity retrieval, strategy-type metrics aggregation
- Automatic feedback loop: campaign results feed back into hypothesis calibration and Knowledge Lake indexing

### Out of Scope
- Real-time streaming data feeds
- Alternative data (satellite, credit card, etc.)
- LLM fine-tuning on proprietary trading data
- Full automated strategy discovery without human review gates

## Capabilities

### New Capabilities
- `research-multi-source`: provider abstraction for academic papers, quant blogs, SQX docs, and stock screeners
- `hypothesis-diversification`: parametric variant generation and pre-validation pipeline
- `knowledge-semantic-search`: embedding generation, similarity ranking, and strategy-type metrics

### Modified Capabilities
- `llm-research`: prompt templates, provider orchestration, confidence calibration by strategy type
- `hypothesis-builder`: LLM mode context injection, validation rules, deduplication
- `knowledge-store`: embeddings directory, similarity index, feedback ingestion hooks
- `knowledge-memory`: injected-context retrieval from semantic search, feedback loop integration

## Approach

Implement in 4 sequential phases: (1) Knowledge Lake semantic foundation (embeddings + strategy-type metrics), (2) Multi-source data providers (quick wins first: blogs + SQX docs; then papers + screeners), (3) LLM intelligence upgrades (prompt engineering, diversification, calibration), (4) Closed-loop feedback. Each phase is independently testable and gated. LLM failures always fall back to existing rule-based ResearchAgent.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/llm_research_agent.py` | Modified | New providers, prompt templates, diversification, calibration |
| `sdk/quantlab/agents/research_agent.py` | Modified | Tag-based Sharpe, parametric variants, pre-validation |
| `sdk/quantlab/agents/hypothesis_builder/` | Modified | LLM context injection, validation, deduplication |
| `sdk/quantlab/knowledge/` | Modified | Embeddings, semantic search, metrics aggregation |
| `sdk/quantlab/data/` | New | Provider implementations for papers, blogs, screeners |
| `sdk/quantlab/dsl/models.py` | Modified | HypothesisConfig extensions for embeddings/feedback |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM hallucination of non-existent indicators | Med | Validate against known SQX indicator registry; fallback to rule mode |
| External API rate limits / downtime | Med | Circuit breakers, caching, graceful degradation to existing providers |
| Embedding model dependency | Low | Text-based fallback; lightweight local model option |
| Feedback loop overfitting | Med | Human-in-the-loop gates; read-only recommendations in MVP |
| Insufficient historical data for tag calibration | Med | Bayesian smoothing; minimum sample thresholds; global fallback |

## Rollback Plan

Each provider and feature is opt-in via config flags. Removing a provider registration or feature flag restores previous behavior. No schema migrations are required for existing Knowledge Lake data; new directories (embeddings/) are additive. LLM mode already has a tested fallback to rule mode.

## Dependencies

- Existing `LLMConfig`, `LLMCircuitBreaker`, `QueryBuilder`, `KnowledgeStore`
- Optional: `sentence-transformers` or similar for embeddings (graceful import fallback)
- Optional: `arxiv`, `feedparser`, `beautifulsoup4` for new providers

## Success Criteria

- [ ] ResearchAgent generates 3-5 parametric variants per hypothesis instead of 1
- [ ] LLMResearchAgent consumes at least 2 new provider types (papers OR blogs OR screeners)
- [ ] Hypothesis pre-validation rejects invalid SQX indicators before pipeline proceeds
- [ ] Knowledge Lake supports semantic similarity search with text fallback
- [ ] Confidence calibration uses tag-specific Sharpe distributions when available
- [ ] All existing 530+ tests pass; new tests cover new providers and validation logic
- [ ] End-to-end campaign with enhanced research produces ≥1 accepted strategy in mock mode
