# Delta for knowledge-store

## ADDED Requirements

### Requirement: Embedding Storage

The Knowledge Store MUST create and maintain an `embeddings/` directory. The system MUST store hypothesis embeddings as `.npy` files keyed by hypothesis ID. Each embedding file MUST be accompanied by a metadata JSON file with `{hypothesis_id, campaign_id, created_at, model_name, dimension}`. If the embedding model is unavailable, the system MUST fall back to text-based token similarity without raising errors.

#### Scenario: Embedding written with metadata

- GIVEN a hypothesis with id `hyp_001` and embedding vector of dimension 384
- WHEN the embedding is persisted
- THEN `embeddings/hyp_001.npy` and `embeddings/hyp_001.meta.json` exist

#### Scenario: Missing embedding model falls back to text

- GIVEN `sentence-transformers` is not installed
- WHEN semantic search is requested
- THEN the system uses token-based similarity and logs a warning

## MODIFIED Requirements

### Requirement: Metadata Indexing

The system MUST maintain a metadata index (`knowledge/index.yaml`) tracking top-level files per directory. The index MUST include entries for `embeddings/{hypothesis_id}.npy` and `embeddings/{hypothesis_id}.meta.json`. The version MUST be incremented to 6 when embeddings are present.

(Previously: version 5 with campaign-phases, parameter-matrix, guardian-feedback, maintenance)

#### Scenario: Index tracks embeddings

- GIVEN an initialized Knowledge Lake with 2 embeddings
- WHEN `read_index()` runs
- THEN the index includes embedding entries under `directories.embeddings`
- AND version is 6

### Requirement: Directory Initialization

The system MUST create the Knowledge Lake skeleton including `embeddings/`. Re-initialization on an existing structure MUST be idempotent.

(Previously: 11 top-level subdirectories without embeddings)

#### Scenario: Fresh initialization creates embeddings directory

- GIVEN a `knowledge/` path that does not exist
- WHEN the system initializes
- THEN `embeddings/` is created with a `.gitkeep` marker

## ADDED Requirements

### Requirement: Semantic Similarity Query

`QueryBuilder` MUST expose `filter_by_similarity(hypothesis_text, top_k=5)` which returns campaigns ranked by embedding similarity when embeddings are available, or by token overlap when they are not. Results MUST include a `similarity_score` float in `[0, 1]`.

#### Scenario: Semantic search returns ranked campaigns

- GIVEN 3 historical campaigns with embeddings
- WHEN `filter_by_similarity("mean reversion equities")` runs
- THEN campaigns are returned sorted by descending similarity_score

#### Scenario: Text fallback when no embeddings

- GIVEN no `.npy` files in embeddings/
- WHEN `filter_by_similarity()` runs
- THEN results are ranked by token overlap Jaccard similarity
