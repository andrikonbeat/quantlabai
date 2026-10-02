# Tasks: Research Agent Enhancements

> **Read `apply-progress.md` → "Resume Handoff" before executing any task.** Two scope items here are
> already partly delivered by other changes (tag-based Sharpe calibration and Knowledge Lake token-level
> search), and the estimated line count below predates that. Scope needs re-approval before work starts.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1200-1800 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation (embeddings + metrics) → PR 2: Providers + LLM intelligence → PR 3: Integration + feedback loop |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |
| Decision needed before apply | Yes |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Knowledge Lake semantic foundation (embeddings, similarity, metrics) | PR 1 | `SQX_FORCE_MOCK=1 python3 -m pytest sdk/tests/knowledge/ -q` | Mock campaigns with embeddings | `sdk/quantlab/knowledge/` |
| 2 | New data providers (papers, blogs, SQX docs, screeners) | PR 2 | `SQX_FORCE_MOCK=1 python3 -m pytest sdk/tests/agents/test_llm_agent_news.py -q` | Mock HTTP + feedparser | `sdk/quantlab/data/literature/` + `llm_research_agent.py` |
| 3 | LLM intelligence (diversification, validation, calibration) | PR 2 | `SQX_FORCE_MOCK=1 python3 -m pytest sdk/tests/agents/ -q` | Mock LLM responses | `research_agent.py` + `hypothesis_builder/` |
| 4 | Integration + feedback loop | PR 3 | `SQX_FORCE_MOCK=1 python3 -m pytest -q` | Full pipeline dry-run | `knowledge-memory` + context injection |

## Phase 1: Foundation — Knowledge Lake Semantic Layer

- [ ] 1.1 Create `sdk/quantlab/knowledge/embedding_service.py` with `EmbeddingService` class: async `embed()`, `similarity()`, graceful fallback to token similarity
- [ ] 1.2 Add `embeddings/` directory to `KnowledgeStore.initialize()` and `read_index()` version bump to 6
- [ ] 1.3 Implement `QueryBuilder.filter_by_similarity()` in `sdk/quantlab/knowledge/query.py`
- [ ] 1.4 Add strategy-type metrics aggregation to `sdk/quantlab/knowledge/indexer.py`: `avg_sharpe_by_tag`, `best_parameters_by_market`
- [ ] 1.5 Write unit tests for `EmbeddingService`, `QueryBuilder.filter_by_similarity()`, and indexer metrics
- [ ] 1.6 Write integration test: write embeddings → query similarity → verify ranking

## Phase 2: Data Providers

- [ ] 2.1 ~~Create `sdk/quantlab/data/providers/base.py` with `BaseProvider` ABC and `ProviderRegistry`~~
      - **Re-scoped 2026-09-30 by maintainer decision — do NOT create `data/providers/`.**
        `AbstractDataProvider` (`sdk/quantlab/data/fundamental/base.py`) already provides the whole
        abstraction: one abstract method `async fetch(query, **params) -> dict`, `ProviderError` with
        structured code/details, and automatic registration via `__init_subclass__`. No registry class is
        needed — subclasses register themselves into `_registry`.
        New shape: create `sdk/quantlab/data/literature/` (matching the by-domain layout used by
        `fundamental/`, `news/`, `market/`, `technical/`) containing `LiteratureProvider(
        AbstractDataProvider)` and a `PaperItem` model with `authors`, `arxiv_id`, `categories`.
        `NewsItem` does not fit: its `sentiment` field is meaningless for a paper, and task 2.2 requires
        category filtering.
- [ ] 2.2 Implement `AcademicPapersProvider` in `sdk/quantlab/data/literature/papers.py`: arXiv/SSRN query, category filter, rate-limit polite
      - Extends `LiteratureProvider` from 2.1 and returns `PaperItem`. Needs `arxiv` added to
        `sdk/pyproject.toml` — it is not currently declared anywhere.
- [ ] 2.3 Implement `QuantBlogProvider` in `sdk/quantlab/data/literature/blogs.py`: RSS feeds, dedup by URL
      - `feedparser` is already a core dependency (`sdk/pyproject.toml:26`).
- [ ] 2.4 Implement `SQXDocProvider`: scan `knowledge/structured/sqx-kb/` for indicator definitions
      - **Placement undecided.** This scans local files, not a network source, so it may not belong to
        `data/literature/` or the `AbstractDataProvider` hierarchy at all. Decide when picking up this task.
- [ ] 2.5 Implement `StockScreenerProvider`: Finviz/AlphaVantage with env-var API keys
      - **Placement undecided.** A screener is not literature. Candidates: `data/market/` or a new
        `data/screening/`. Decide when picking up this task. Env-var key precedent:
        `data/data_manager.py` (`SQCLI_PATH`, `SQX_INSTALL_PATH`).
- [ ] 2.6 Integrate providers into `LLMResearchAgent.fetch_data()`: parallel execution, graceful degradation
- [ ] 2.7 Add `research-literature` and `sqx-catalog` prompt templates to `sdk/quantlab/agents/prompts.py`
- [ ] 2.8 Write unit tests for each provider (mock HTTP/feeds); test parallel execution and provider failure isolation

## Phase 3: LLM Intelligence

- [ ] 3.1 Implement `DiversityEngine` in `sdk/quantlab/agents/diversity_engine.py`: parametric variant generation, deduplication, configurable factor
- [ ] 3.2 Implement `PreValidator` in `sdk/quantlab/agents/pre_validator.py`: indicator existence, parameter range, semantic coherence, direction consistency
- [ ] 3.3 Integrate diversity engine into `ResearchAgent.formulate_hypotheses()` and `LLMResearchAgent.parse_response()`
- [ ] 3.4 Integrate pre-validator into `ResearchAgent.generate_config()` with `validation_policy` support (strict/lenient/off)
- [ ] 3.5 Update `LLMResearchAgent.build_prompt()` to inject similar hypotheses and tag-based Sharpe calibration from Knowledge Lake
      - **Reconciled 2026-09-30 — not greenfield.** `TagCalibrator` already computes per-tag Sharpe
        percentiles with Bayesian smoothing and is already called from
        `ResearchAgent.formulate_hypotheses()` (rule-based path, gated on `if query_results:`), with
        tests in `tests/agents/test_tag_calibrator.py` and `test_research_agent_f1.py`. This task is
        only about **exposing that existing output to the LLM prompt path**, which currently ignores it.
        Do not build a second calibrator.
- [ ] 3.6 Update `HypothesisBuilder` LLM mode to inject semantic context; update `HypothesisBuilderStage` to pass `market_context`
- [ ] 3.7 Extend `HypothesisConfig` in `sdk/quantlab/dsl/models.py` with optional embedding/feedback fields
- [ ] 3.8 Write unit tests for diversity engine, pre-validator, and prompt injection

## Phase 4: Feedback Loop & Integration

- [ ] 4.1 Implement `FeedbackWriter` in `sdk/quantlab/knowledge/feedback.py`: persist hypothesis test results, pass/fail flags, parameter notes
- [ ] 4.2 Hook feedback writing into campaign phase completion (review → archive boundary)
- [ ] 4.3 Update `AgentMemoryManager` injected-context retrieval to include semantic similarity and calibration metrics
- [ ] 4.4 Wire feedback ingestion into Knowledge Store indexing pipeline
- [ ] 4.5 Write integration test: full campaign mock → feedback written → semantic search finds similar prior hypotheses

## Phase 5: Verification & Regression

- [ ] 5.1 Run full existing test suite (`SQX_FORCE_MOCK=1 python3 -m pytest -q`); fix any regressions
- [ ] 5.2 Add e2e test: enhanced research pipeline produces ≥1 accepted strategy in mock mode
- [ ] 5.3 Add privacy/deny-list conformance tests for new provider URLs and feedback data
- [ ] 5.4 Update `openspec/specs/llm-research/spec.md` with new provider and template scenarios
- [ ] 5.5 Update `openspec/specs/hypothesis-builder/spec.md` with diversification and validation scenarios
- [ ] 5.6 Update `openspec/specs/knowledge-store/spec.md` with embedding and similarity scenarios
- [ ] 5.7 Update `openspec/specs/knowledge-memory/spec.md` with semantic injection and feedback scenarios
