# Delta for knowledge-memory

## ADDED Requirements

### Requirement: Semantic Context Injection

`AgentMemoryManager` MUST include semantic similarity results from `QueryBuilder.filter_by_similarity()` in the injected context block. The injected context MUST contain:
- Matched prior decisions, risks, and lessons
- Similar campaigns ranked by embedding similarity score
- Strategy-type calibration data (`avg_sharpe_by_tag`, `best_parameters_by_market`)

If semantic search is unavailable, the system MUST fall back to tag-based text search without raising.

#### Scenario: Semantic context injected with similarity scores

- GIVEN 3 similar prior campaigns with embeddings
- WHEN phase N+1 context is composed
- THEN the envelope includes matched decisions with similarity scores > 0.6

## MODIFIED Requirements

### Requirement: REQ-104 Injected-Context Retrieval

The system MUST compose prior-campaign context — QueryBuilder results plus `find_similar_campaigns` embeddings — into a markdown block injected into the next phase's Result Contract envelope. The system MUST ALSO include strategy-type calibration metrics and parametric best-practices when available.

(Previously: Only QueryBuilder results + find_similar_campaigns embeddings)

#### Scenario: Calibration data included in injected context

- GIVEN Knowledge Lake has computed `avg_sharpe_by_tag`
- WHEN context is composed for a mean-reversion objective
- THEN the injected block includes the tag-specific Sharpe baseline
