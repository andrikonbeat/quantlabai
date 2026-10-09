# Design: research-agent-improvements

## Architecture Overview

Current pipeline: `ResearchAgent.formulate_hypotheses()` → `HypothesisBuilder` (RuleMode | LLMMode) → `BuildingBlock` → `BuilderAgent`.

New components insert validation, calibration, documentation, and feedback at three layers:

```
ResearchAgent
    ├── formulate_hypotheses()
    │       ├── [F1] EconomicSenseValidator  (non-blocking warnings)
    │       ├── query_knowledge_lake()
    │       │       ├── [F2] SemanticSimilarityQuery  (extends QueryBuilder)
    │       │       └── [F1] TagCalibrator  (confidence adjustment)
    │       └── returns calibrated HypothesisConfig list
    │
HypothesisBuilder
    ├── RuleMode._build_with_rule()
    │       └── [F2] ParameterValidator  (blocking, before defaults)
    │
    └── LLMMode._build_with_llm()
            ├── [F2] SQXDocProvider  (prompt injection)
            └── [F2] ParameterValidator  (blocking, after parse)

BuilderAgent.run()
    └── [F3] KnowledgeLakeFeedbackWriter  (async, non-blocking)
```

## Component Designs

### EconomicSenseValidator

**Choice**: Standalone module `sdk/quantlab/agents/economic_sense/validator.py` with static range tables and cross-parameter rules.

**Integration**: Called from `ResearchAgent.formulate_hypotheses()` after each `HypothesisConfig` is created, and from `RuleMode`/`LLMMode` after parameters are resolved.

**Warning format**: Appended to `HypothesisConfig.validation_warnings: list[str]` (new field on the model). Non-blocking — never raises.

**Alternatives**: Inline checks in `ResearchAgent`. Rejected because validation logic is reusable and testable in isolation.

### TagCalibrator

**Choice**: Module `sdk/quantlab/agents/tag_calibrator.py` with in-memory LRU cache keyed by frozenset(tags).

**Formula**: `confidence = base_confidence × percentile(mean_tag_sharpe, global_sharpe_distribution)`. Percentile ∈ [0.1, 1.0]. Sparse tags (<5 samples) use Bayesian smoothing: `blended = (n × tag_mean + prior × global_mean) / (n + prior)`.

**Integration**: Called in `ResearchAgent.formulate_hypotheses()` after `query_knowledge_lake()` returns, before returning hypotheses.

### SQXDocProvider

**Choice**: Facade `sdk/quantlab/knowledge/sqX_doc_provider.py` over existing `KbStore`, adding transparent fallback to `_BUILD_CONFIG_MAP`.

**Interface**: `get_valid_range(tab, param, sqx_version)`, `get_enum_values(...)`, `get_description(...)`. Returns `None` for range/enums when unavailable.

**Fallback**: When YAML missing, probe `_BUILD_CONFIG_MAP` for type/range hints; log warning. Never invent semantics.

### ParameterValidator

**Choice**: Module `sdk/quantlab/agents/parameter_validator.py` that delegates constraint lookups to `SQXDocProvider`.

**Blocking behavior**: Returns `ValidationResult(valid, errors)`. Caller drops the hypothesis on invalid. In `LLMMode._parse_response()`, invalid JSON hypotheses are skipped. In `RuleMode`, invalid overrides fall back to defaults.

### SemanticSimilarityQuery

**Choice**: Extend `QueryBuilder` in `sdk/quantlab/knowledge/query.py` with `search_similar_campaigns(text, top_k=10)`.

**Embedding strategy**: Use `sentence-transformers` all-MiniLM-L6-v2 when installed. Cache embeddings in `index["embeddings"][campaign_id]`. Fallback: token + char 3-gram cosine similarity (no external deps).

**Integration**: Called from `ResearchAgent.formulate_hypotheses()` after keyword queries; merge results and adjust confidence by semantic match quality.

### KnowledgeLakeFeedbackWriter

**Choice**: Module `sdk/quantlab/agents/feedback_writer.py` with async `write_feedback()` using `asyncio.create_task()`.

**Metadata format**: Append to `structured/{campaign_id}/metadata.yaml` under `feedback: list[HypothesisFeedbackRecord]`.

**Human gate**: `auto_adjust` flag in writer config (default `False`). When `False`, feedback is queryable via `QueryBuilder` but confidence is not auto-modified.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/economic_sense/validator.py` | Create | Range + coherence validator |
| `sdk/quantlab/agents/tag_calibrator.py` | Create | Tag-based confidence calibration |
| `sdk/quantlab/knowledge/sqX_doc_provider.py` | Create | YAML + fallback doc provider |
| `sdk/quantlab/agents/parameter_validator.py` | Create | Blocking parameter validation |
| `sdk/quantlab/knowledge/query.py` | Modify | Add `search_similar_campaigns()` |
| `sdk/quantlab/knowledge/models.py` | Modify | Add `HypothesisFeedbackRecord` |
| `sdk/quantlab/agents/feedback_writer.py` | Create | Async feedback persistence |
| `sdk/quantlab/agents/research_agent.py` | Modify | Wire F1 validators/calibrator |
| `sdk/quantlab/agents/hypothesis_builder/rule.py` | Modify | Wire ParameterValidator |
| `sdk/quantlab/agents/hypothesis_builder/llm.py` | Modify | Wire SQXDocProvider + ParameterValidator |
| `sdk/quantlab/agents/llm_research_agent.py` | Modify | Wire SQXDocProvider into prompts |

## Interfaces / Contracts

```python
# HypothesisConfig extension
class HypothesisConfig(BaseModel):
    ...
    validation_warnings: list[str] = Field(default_factory=list)

# EconomicSenseValidator
class EconomicSenseValidator:
    def validate(self, hypothesis: HypothesisConfig) -> list[str]: ...

# TagCalibrator
class TagCalibrator:
    def calibrate(self, hypotheses: list[HypothesisConfig], query_results: list[dict]) -> list[HypothesisConfig]: ...

# SQXDocProvider
class SQXDocProvider:
    def get_valid_range(self, tab: str, param: str, sqx_version: str) -> tuple[float, float] | None: ...
    def get_enum_values(self, tab: str, param: str, sqx_version: str) -> list[str] | None: ...
    def get_description(self, tab: str, param: str, sqx_version: str) -> str: ...

# ParameterValidator
class ParameterValidator:
    def validate_hypothesis(self, hypothesis: HypothesisConfig, sqx_version: str = None) -> ValidationResult: ...

# SemanticSimilarityQuery (QueryBuilder extension)
class QueryBuilder:
    def search_similar_campaigns(self, text: str, top_k: int = 10) -> list[dict]: ...

# KnowledgeLakeFeedbackWriter
class KnowledgeLakeFeedbackWriter:
    async def write_feedback(self, record: HypothesisFeedbackRecord) -> None: ...
```

## Migration Plan

No breaking changes. All new components are additive:
- F1 components are non-blocking or additive (warnings, confidence adjustment).
- F2 components use transparent fallbacks (missing YAML → `_BUILD_CONFIG_MAP`; missing embedding → text similarity).
- F3 feedback writer defaults to read-only (`auto_adjust=False`).
- Feature flags via config dicts allow disabling any component at runtime.

## Test Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | EconomicSenseValidator ranges/coherence | Parametrized pytest with boundary values |
| Unit | TagCalibrator percentile + Bayesian smoothing | Mock KnowledgeStore with known tag distributions |
| Unit | SQXDocProvider YAML + fallback | Temp YAML files + monkeypatch `_BUILD_CONFIG_MAP` |
| Unit | ParameterValidator blocking | Valid/invalid parameter sets against mock provider |
| Unit | SemanticSimilarityQuery fallback | Test embedding path + text-only path |
| Unit | FeedbackWriter async write | `asyncio` test with temporary Knowledge Lake |
| Integration | ResearchAgent end-to-end F1 | Mock query results, assert warnings + confidence |
| Integration | LLMMode parameter validation | Mock LLM response with invalid params, assert drop |

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Calibration with sparse tags | Medium | Bayesian smoothing + min_samples=5 threshold |
| Embedding model dependency | Medium | Optional install; text fallback always works |
| LLM hallucination | High | Strict JSON schema + SQX KB post-parse validation |
| Feedback loop instability | Medium | Read-only by default; human gate before auto-adjust |
| Performance (embedding generation) | Low | Cache at ingestion; batch generation |

## Open Questions

- [ ] Confirm embedding model choice (all-MiniLM-L6-v2 vs. smaller ONNX runtime variant).
- [ ] Confirm `HypothesisConfig.validation_warnings` field name with DSL owner.
- [ ] Confirm `HypothesisFeedbackRecord` schema with Knowledge Lake owner.

## Ready for Tasks

Yes — no blockers. All specs are defined and codebase entry points are mapped.
