# Proposal: Research Agent Improvements

## Intent

The ResearchAgent generates low-quality, unvalidated hypotheses using hardcoded keyword matching and 5 indicators. Technical analysis is broken. No parameter validation exists. Knowledge Lake is underutilized. This change introduces validation, calibration, SQX documentation, semantic search, and a feedback loop to fix these gaps.

## Scope

### In Scope
- Parameter validation against SQX KB ranges and types
- Tag-based Sharpe calibration (TagCalibrator)
- SQX documentation provider (SQXDocProvider)
- Semantic similarity queries in Knowledge Lake
- Knowledge Lake feedback writer for campaign results
- Economic sense validation before hypothesis generation

### Out of Scope
- Scraping academic papers (SSRN/arXiv)
- Quantitative blog ingestion (Quantocracy, QuantStart)
- Stock screeners (Finviz, AlphaVantage)
- Multi-source data expansion beyond SQX docs

## Capabilities

> This section is the CONTRACT between proposal and specs phases.
> The sdd-spec agent reads this to know exactly which spec files to create or update.

### New Capabilities
- `economic-sense-validator`: Validates hypotheses against known SQX indicator semantics and market regime constraints before generation.
- `tag-calibrator`: Computes Sharpe distributions by tag and adjusts confidence scores using percentile calibration.
- `sqx-doc-provider`: Reads SQX built-in documentation from `structured/sqx-kb/` for indicator/parameter descriptions.
- `parameter-validator`: Validates hypothesis parameters against SQX KB ranges and types before strategy building.
- `semantic-similarity-query`: Adds embedding-based semantic search to Knowledge Lake QueryBuilder.
- `knowledge-lake-feedback-writer`: Writes campaign results back to agent memory and hypothesis confidence scores.

### Modified Capabilities
- `research-agent`: Integrates EconomicSenseValidator and TagCalibrator into hypothesis generation pipeline.
- `llm-research`: Integrates SQXDocProvider and ParameterValidator into prompt building and output validation.
- `knowledge-query`: Extends QueryBuilder with semantic similarity search methods.
- `sqx-parameter-kb`: Adds doc-provider consumption interface and validation hooks.

## Approach

Three-phase implementation prioritizing quick wins first:
1. Phase 1 adds validation and calibration to the existing ResearchAgent pipeline (~400 LOC).
2. Phase 2 enriches LLMResearchAgent with SQX documentation and validates parameters before strategy building.
3. Phase 3 adds semantic search to Knowledge Lake and closes the feedback loop.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/research_agent.py` | Modified | Integrates EconomicSenseValidator and TagCalibrator |
| `sdk/quantlab/agents/llm_research_agent.py` | Modified | Integrates SQXDocProvider and ParameterValidator |
| `sdk/quantlab/agents/hypothesis_builder/` | Modified | Uses validated parameters and calibrated confidence |
| `sdk/quantlab/knowledge/query.py` | Modified | Adds SemanticSimilarityQuery methods |
| `sdk/quantlab/knowledge/store.py` | Modified | Adds feedback writer path |
| `sdk/quantlab/data/fundamental/` | New | SQXDocProvider implementation |
| `structured/sqx-kb/` | Used | Source of SQX documentation and parameter ranges |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Calibration accuracy with sparse tag data | Medium | Bayesian smoothing + minimum sample thresholds |
| Embedding model dependency | Medium | Start with lightweight model; text-based fallback |
| LLM hallucination of indicators | High | Strict JSON schema + SQX KB post-parse validation |
| Feedback loop instability | Medium | Read-only recommendations first; human gate before auto-adjust |

## Rollback Plan

Each phase is independently deployable. Phase 1 validators are additive (no breaking changes to existing hypothesis flow). Phase 2 providers are optional with transparent fallback. Phase 3 semantic search falls back to text-based similarity. Disable any new component via config flags; remove without data loss.

## Dependencies

- Existing SQX installation and `structured/sqx-kb/` content (already present)
- Knowledge Lake `QueryBuilder` and `KnowledgeStore` (already present)
- Optional: embedding model library (add if Phase 3 proceeds)

## Success Criteria

- [ ] ResearchAgent hypotheses pass EconomicSenseValidator before output
- [ ] Confidence scores reflect tag-based historical Sharpe percentiles
- [ ] SQXDocProvider supplies indicator descriptions to LLM prompts
- [ ] ParameterValidator blocks invalid SQX parameters before strategy build
- [ ] SemanticSimilarityQuery returns relevant campaigns for natural-language queries
- [ ] KnowledgeLakeFeedbackWriter persists campaign outcomes to agent memory
