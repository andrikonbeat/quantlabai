# Semantic Similarity Query Specification

## Purpose

Extends Knowledge Lake QueryBuilder with embedding-based semantic search, enabling natural-language queries to find semantically similar campaigns beyond keyword matching.

## Requirements

### Requirement: REQ-F2-06 QueryBuilder Extension

The system MUST extend QueryBuilder with:
- search_similar_campaigns(text: str, top_k: int = 10) -> QueryResult
- _generate_embedding(text: str) -> list[float]
- _cosine_similarity(a: list[float], b: list[float]) -> float

Embeddings SHALL use a lightweight model when available; text-based fallback SHALL use token + char 3-gram cosine similarity.

#### Scenario: Semantic search returns similar campaigns

- GIVEN Knowledge Lake contains campaigns about "EURUSD trend following"
- WHEN search_similar_campaigns("European currency momentum") runs
- THEN campaigns with similar embeddings are returned
- AND keyword-only matches are not required

#### Scenario: Text fallback works

- GIVEN no embedding model is available
- WHEN search_similar_campaigns("breakout strategy") runs
- THEN token + char 3-gram cosine similarity is used
- AND results are ranked by similarity score

### Requirement: REQ-F2-07 Embedding Persistence

The system MUST generate and cache embeddings for new campaigns at ingestion time. Embeddings SHALL be stored alongside campaign metrics in the index.

#### Scenario: New campaign gets embedding

- GIVEN a new campaign is added to Knowledge Lake
- WHEN the indexer processes it
- THEN an embedding is generated from campaign description + tags
- AND stored in the index

### Requirement: REQ-F2-08 ResearchAgent Integration

The system MUST integrate semantic search into ResearchAgent.formulate_hypotheses():
- After keyword-based Knowledge Lake queries, run semantic search
- Merge results with tag-based calibration
- Use semantic matches to refine hypothesis confidence

#### Scenario: Hypotheses enriched by semantic search

- GIVEN ResearchAgent is formulating hypotheses for "USDJPY carry"
- WHEN formulate_hypotheses() runs
- THEN semantic search finds campaigns with "yen funding" descriptions
- AND hypothesis confidence is adjusted based on semantic match quality
