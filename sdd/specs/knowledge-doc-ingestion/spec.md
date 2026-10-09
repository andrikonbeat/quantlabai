# Knowledge Doc Ingestion Specification

## Purpose

Ingests official SQX/JForex documentation from licensed installs and public wikis into version-pinned Markdown under the Knowledge Lake, with provenance metadata and legal-boundary enforcement.

## Requirements

### Requirement: REQ-KDI-01 Raw Corpus Isolation (ADDED)

The raw corpus under `knowledge/raw/` MUST remain gitignored (`knowledge/raw/*`). Only derived facts and provenance MAY be committed; licensed artifacts MUST NOT enter git.

#### Scenario: gitignore enforcement

- GIVEN raw docs extracted to `knowledge/raw/sqx/144.2953/`
- WHEN `git status` runs
- THEN no raw file appears as tracked or staged

#### Scenario: Redistribution blocked

- GIVEN a docs.json-derived file placed under `knowledge/raw/`
- WHEN a commit is prepared
- THEN the file is not staged unless the ignore rule is explicitly bypassed
- AND no licensed content exists under `knowledge/structured/`

### Requirement: REQ-KDI-02 Version-Pinned Ingestion (ADDED)

The system MUST provide a `DocIndexer` that ingests the licensed SQX install corpus (`internal/autocomplete/docs.json`, `Snippets/SQ/Blocks/`, `Code/JForex/`) and public wikis into version-pinned Markdown at `knowledge/structured/sqx-kb/{ver}/docs/` and `knowledge/structured/jforex-kb/{ver}/`. Pinned dirs MUST NOT be overwritten in place; a new version creates a new directory.

#### Scenario: docs.json ingestion

- GIVEN the licensed install at `assets/SQX_144_2953_linux_20260601/`
- WHEN `DocIndexer.ingest("144.2953")` runs
- THEN Markdown docs are written under `structured/sqx-kb/144.2953/docs/` and `structured/jforex-kb/144.2953/`

#### Scenario: New version creates new directory

- GIVEN docs already exist under `144.2953/`
- WHEN `DocIndexer.ingest("144.4000")` runs
- THEN `structured/sqx-kb/144.4000/` is created
- AND `144.2953/` is untouched

#### Scenario: Idempotent re-ingest skips unchanged docs

- GIVEN docs already written for `144.2953`
- WHEN `DocIndexer.ingest("144.2953")` runs again
- THEN unchanged docs are skipped (sha256 match)
- AND only new/changed docs are written

### Requirement: REQ-KDI-03 Provenance per Document (ADDED)

Every ingested doc MUST carry front-matter provenance with `source`, `license`, `fetched_at`, and `sha256`. The `sha256` MUST be deterministic (stable across re-ingest) so idempotency is not broken by timestamp changes.

#### Scenario: front-matter contains required keys

- GIVEN a doc written by the ingestor
- WHEN the Markdown is inspected
- THEN `source:`, `license:`, `fetched_at:`, and `sha256:` are present in the front-matter

#### Scenario: Deterministic sha256 survives re-ingest

- GIVEN a doc was ingested at time T1
- WHEN the same source is re-ingested at time T2
- THEN the stored `sha256` matches the newly computed one
- AND the doc is skipped as unchanged

### Requirement: REQ-KDI-04 No Gated Scraping (ADDED)

The ingestor MUST skip URLs/paths that indicate gated or account-only content (e.g., `/login`, `/manual`, `/account`, `/members`, `/premium`, `/paid`). Skipped sources MUST emit a warning and MUST NOT be written to the Knowledge Lake.

#### Scenario: Gated URL skipped

- GIVEN a wiki URL containing `/manual`
- WHEN `WikiAdapter.iter_records()` processes it
- THEN a warning is logged
- AND no doc is yielded for that URL

#### Scenario: Public URL ingested

- GIVEN a public wiki URL without gated patterns
- WHEN `WikiAdapter.iter_records()` processes it
- THEN a normalized Markdown doc is yielded with `public-wiki` license
