# Knowledge Semantic Search Specification

## Purpose

Embedding-based similarity search and strategy-type metrics aggregation for the Knowledge Lake. Enables the Research agent to find historically similar campaigns and hypotheses, calibrate confidence by strategy type, and support the feedback loop.

## Requirements

### Requirement: Embedding Generation

The system MUST generate embeddings for each `HypothesisConfig` at campaign completion. Embeddings MUST capture the hypothesis `name`, `description`, `parameters`, and `expected_outcome`. The embedding model and dimension MUST be recorded in metadata. If the embedding service is unavailable, the system MUST fall back to token-based similarity and log a warning.

#### Scenario: Embedding generated on campaign completion

- GIVEN a campaign completes with 3 hypotheses
- WHEN the embedding service runs
- THEN 3 `.npy` files and 3 `.meta.json` files are written to `embeddings/`

### Requirement: Similarity Search

`QueryBuilder` MUST expose `filter_by_similarity(text: str, top_k: int = 5)` returning campaigns ranked by cosine similarity. When embeddings are available, the system MUST use vector similarity; otherwise, it MUST use token overlap (Jaccard). Results MUST include `similarity_score` in `[0, 1]`.

#### Scenario: Vector similarity ranking

- GIVEN 10 campaigns with embeddings
- WHEN `filter_by_similarity("mean reversion SP500 H1")` runs with `top_k=3`
- THEN the top 3 most similar campaigns are returned with scores > 0.7

#### Scenario: Token fallback ranking

- GIVEN no embeddings available
- WHEN `filter_by_similarity()` runs
- THEN results are ranked by Jaccard similarity of token sets

### Requirement: Strategy-Type Metrics Aggregation

The system MUST compute and expose per-strategy-type metrics:
- `avg_sharpe_by_tag`: average Sharpe ratio for each strategy tag
- `best_parameters_by_market`: most frequent parameter sets per market/timeframe/tag combination
- `confidence_baseline`: prior confidence calibration data per strategy type

These metrics MUST be recomputed when new campaign results are indexed. The system MUST use Bayesian smoothing when sample size < 5 to avoid overfitting to sparse data.

#### Scenario: Tag metrics computed from 3 campaigns

- GIVEN 3 campaigns tagged `mean_reversion` with Sharpe ratios [1.2, 1.5, 0.9]
- WHEN metrics are recomputed
- THEN `avg_sharpe_by_tag["mean_reversion"]` is 1.2 (smoothed if < 5 samples)

#### Scenario: Best parameters extracted for EURUSD H1 mean-reversion

- GIVEN 5 campaigns on EURUSD H1 tagged `mean_reversion`
- WHEN best-parameter extraction runs
- THEN the most common `{rsi_period, bb_period, bb_deviation}` tuple is returned

### Requirement: Feedback Loop Integration

After each campaign phase, the system MUST persist a feedback record containing:
- Which hypotheses were tested
- Which passed/failed acceptance criteria
- Parameter performance deltas
- Recommended adjustments for future hypotheses of the same type

Feedback records MUST be stored in `knowledge/structured/feedback/` and indexed for similarity search.

#### Scenario: Feedback record written after review

- GIVEN a campaign with 5 hypotheses, 2 passed, 3 failed
- WHEN the review phase completes
- THEN a feedback JSON is written with pass/fail flags and parameter notes
