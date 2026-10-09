# Delta for Knowledge Query

## ADDED Requirements

### Requirement: SemanticSimilarityQuery Methods

QueryBuilder MUST expose search_similar_campaigns(text, top_k=10) using embedding-based similarity. When embeddings are unavailable, text-based fallback SHALL use token + char 3-gram cosine similarity.

#### Scenario: Semantic search added to QueryBuilder

- GIVEN QueryBuilder instance
- WHEN search_similar_campaigns("momentum strategy") is called
- THEN campaigns with high embedding similarity are returned
- AND results are merged with existing filter criteria

## MODIFIED Requirements

### Requirement: REQ-501 Injected-Context Retrieval Surface

The system MUST provide a context-composition API, e.g. compose_prior_context(campaign_id, phase) -> str, that combines QueryBuilder results, find_similar_campaigns embedding matches, and semantic similarity search results into a markdown context block for injection into the next phase's Result Contract envelope.

(Previously: only embedding matches were included)

#### Scenario: Composes prior memory block

- GIVEN prior campaigns with metrics and stored decisions
- WHEN compose_prior_context runs for phase N+1
- THEN the returned markdown includes matched prior decisions, risks, and lessons
- AND similar campaigns are ranked by embedding similarity

#### Scenario: Empty lake returns placeholder

- GIVEN an empty Knowledge Lake
- WHEN compose_prior_context runs
- THEN a "no prior memory" placeholder is returned and no error is raised
