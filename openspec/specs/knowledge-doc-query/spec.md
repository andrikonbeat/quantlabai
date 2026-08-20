# Knowledge Doc Query Specification

## Purpose

Provides a retrieval surface over ingested official SQX/JForex documentation, with token/char-3-gram cosine as the default path and an optional embedding-based path when `sentence-transformers` is available.

## Requirements

### Requirement: REQ-KDQ-01 Doc Retrieval Surface (ADDED)

`QueryBuilder` MUST expose `query_docs(text, version, kind, top_k)` that reads the `docs` section from the index, applies optional filters, and returns ranked docs by similarity score. The result MUST include `path`, `rel_path`, `kind`, `version`, and `score` per doc.

#### Scenario: query_docs returns ranked results

- GIVEN docs exist under `structured/sqx-kb/144.2953/docs/`
- WHEN `query_docs("RSI indicator parameters", top_k=2)` is called
- THEN up to 2 docs are returned, ranked by descending score

#### Scenario: Version filter limits results

- GIVEN docs exist for versions `144.2953` and `144.4000`
- WHEN `query_docs("RSI", version="144.2953")` is called
- THEN only docs with `version == "144.2953"` are returned

#### Scenario: Kind filter limits results

- GIVEN `block` and `api` docs exist
- WHEN `query_docs("interface", kind="api")` is called
- THEN only `api` docs are returned

#### Scenario: Empty query returns empty result

- GIVEN an empty string query
- WHEN `query_docs("")` is called
- THEN an empty result is returned without error

### Requirement: REQ-KDQ-02 Optional Embeddings (ADDED)

`query_docs` MUST attempt an embedding-based similarity path when `sentence-transformers` is installed. When the library is absent or the model fails to load, it MUST fall back to token/char-3-gram cosine without raising an ImportError.

#### Scenario: sentence-transformers available uses embeddings

- GIVEN `sentence-transformers` and `numpy` are installed
- WHEN `query_docs` is called
- THEN the embedding path is attempted and ranked results are returned

#### Scenario: sentence-transformers absent falls back gracefully

- GIVEN `sentence-transformers` is not installed
- WHEN `query_docs` is called
- THEN a warning is logged
- AND token/3-gram cosine results are returned

#### Scenario: Scores are descending

- GIVEN multiple docs match the query
- WHEN `query_docs` returns results
- THEN scores are sorted from highest to lowest
