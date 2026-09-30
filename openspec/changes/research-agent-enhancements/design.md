# Design: Research Agent Enhancements

## Technical Approach

Extend the existing `LLMResearchAgent`, `ResearchAgent`, `HypothesisBuilder`, and `KnowledgeStore` with multi-source providers, parametric diversification, semantic search, and feedback hooks. Each front is additive: new classes extend existing provider/fetch patterns; existing stages consume enriched artifacts through the same `PipelineContext` contract. No breaking changes to public APIs.

## Architecture Decisions

### Decision: Provider registry pattern for new data sources

**Choice**: Add a `ProviderRegistry` to `LLMResearchAgent` with async `fetch()` methods per provider type.
**Alternatives considered**: Hardcode providers in `fetch_data`; use external plugin package.
**Rationale**: Keeps providers colocated with existing Yahoo/FRED/RSS pattern; lazy init + graceful ImportError already proven by NWS-01. Registry enables parallel execution and circuit breaking.

### Decision: Diversity as post-process on ResearchConfig

**Choice**: Generate parametric variants in `ResearchAgent.formulate_hypotheses()` and `LLMResearchAgent.parse_response()`, not in `HypothesisBuilder`.
**Alternatives considered**: Put diversification in HypothesisBuilder; generate variants at LLM prompt time.
**Rationale**: Hypotheses are the right abstraction level — they carry parameters and confidence. Builder consumes validated hypotheses; putting variants upstream keeps builder logic unchanged.

### Decision: Embedding fallback to token similarity

**Choice**: Use Jaccard token similarity when `sentence-transformers` is unavailable.
**Alternatives considered**: Require embedding model as hard dependency; skip similarity entirely.
**Rationale**: QuantLab already runs in mock/offline modes. Hard dependency breaks air-gapped execution. Token fallback preserves functionality.

### Decision: Feedback loop writes to Knowledge Lake, not Engram

**Choice**: Persist feedback JSON in `knowledge/structured/feedback/` and index via `KnowledgeStore`.
**Alternatives considered**: Write feedback to Engram only; inject feedback directly into LLM prompts.
**Rationale**: Knowledge Lake is the durable Git-versioned training-ready store (REQ-103). Feedback must be versioned, queryable, and exportable. Engram is session/working memory only.

## Data Flow

    Objective ──▶ LLMResearchAgent.fetch_data()
                     │
                     ├─ YahooFinance ──┐
                     ├─ FRED ─────────┤
                     ├─ WebSearch ────┤
                     ├─ RSS ──────────┤
                     ├─ Papers ───────┤
                     ├─ Blogs ────────┤
                     ├─ SQX Docs ─────┤
                     └─ Screeners ────┘
                     │
                     ▼
               build_prompt() ──▶ LLM
                     │
                     ▼
             parse_response() ──▶ ResearchConfig
                     │
                     ▼
           formulate_hypotheses() ──▶ diversity engine
                     │
                     ▼
             pre-validation ──▶ filter incoherent
                     │
                     ▼
             HypothesisBuilder ──▶ BuildingBlocks + Strategies
                     │
                     ▼
             KnowledgeStore.index() ──▶ embeddings + metrics
                     │
                     ▼
             feedback loop ──▶ calibration for next run

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/llm_research_agent.py` | Modify | Add provider registry, parallel fetch, literature/SQX templates |
| `sdk/quantlab/agents/research_agent.py` | Modify | Add diversity engine, pre-validation, tag-based calibration |
| `sdk/quantlab/agents/hypothesis_builder/__init__.py` | Modify | Inject semantic context into LLM mode |
| `sdk/quantlab/agents/hypothesis_builder/llm.py` | Modify | Richer prompt with similar hypotheses and calibration data |
| `sdk/quantlab/knowledge/store.py` | Modify | Embedding write/read, similarity index, feedback directory |
| `sdk/quantlab/knowledge/query.py` | Modify | `filter_by_similarity()` method |
| `sdk/quantlab/knowledge/indexer.py` | Modify | Strategy-type metrics aggregation |
| `sdk/quantlab/data/providers/` | New | `papers.py`, `blogs.py`, `sqx_docs.py`, `screeners.py` |
| `sdk/quantlab/dsl/models.py` | Modify | `HypothesisConfig` embedding/feedback fields |
| `sdk/quantlab/agents/prompts.py` | New | Few-shot templates, chain-of-thought prompts |

## Interfaces / Contracts

```python
class ProviderRegistry:
    async def register(self, name: str, provider: BaseProvider) -> None
    async def fetch_all(self, query: str, context: dict | None = None) -> dict[str, list[dict]]

class BaseProvider(ABC):
    @abstractmethod
    async def fetch(self, query: str, context: dict | None = None) -> list[dict[str, Any]]: ...

class DiversityEngine:
    def generate_variants(self, hypothesis: HypothesisConfig, factor: int = 2) -> list[HypothesisConfig]

class PreValidator:
    def validate(self, hypothesis: HypothesisConfig, policy: str = "strict") -> ValidationResult

class EmbeddingService:
    async def embed(self, text: str) -> np.ndarray | None
    async def similarity(self, query: str, top_k: int = 5) -> list[SimilarCampaign]

class FeedbackWriter:
    def write(self, campaign_id: str, feedback: dict) -> Path
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Provider registry, diversity engine, pre-validator, embedding service | Mock HTTP/imports; parametrize indicator ranges |
| Integration | LLMResearchAgent with new providers; HypothesisBuilder with semantic context | Mock providers + LLM; verify prompt composition |
| Integration | KnowledgeStore embedding read/write; QueryBuilder similarity | Temp dirs; compare vector vs token rankings |
| E2E | Full research → hypothesis → builder pipeline with enhancements | Mock SQX + mock LLM; assert enriched artifacts |
| Regression | All existing 530+ tests | Run full suite with SQX_FORCE_MOCK=1 |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. All new code runs in-process async Python with existing circuit-breaker and caching patterns.

## Migration / Rollout

No migration required. New directories (`embeddings/`, `feedback/`) are additive. New providers are opt-in via config. Existing `ResearchConfig` gains optional fields with defaults. LLM mode fallback to rule mode remains unchanged.

## Open Questions

- [ ] Which embedding model to use? `all-MiniLM-L6-v2` (lightweight) vs domain-specific quant model?
- [ ] Should SQXDocProvider parse local SQX install or bundled DSL reference?
- [ ] Finviz scraping vs API — Finviz HTML structure changes frequently; AlphaVantage requires API key.
