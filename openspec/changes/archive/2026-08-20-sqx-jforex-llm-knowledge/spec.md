# Delta: SQX + JForex 4 Knowledge for LLM Agents

Grounds LLM agents in official, version-pinned SQX/JForex knowledge: doc ingestion from the licensed install + public wikis, docs retrieval, and tool-knowledge injection. Legal boundary: never redistribute licensed/gated material in git — commit derived facts + provenance only.

## Capability: knowledge-doc-ingestion (NEW)

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

The system MUST provide a `DocIndexer` that ingests the licensed SQX install corpus (`internal/autocomplete/docs.json` — 2,533 entries, `Snippets/SQ/Blocks/` — 931, `Code/JForex/` — 605 templates) and public wikis into version-pinned Markdown at `knowledge/structured/sqx-kb/{ver}/docs/` and `knowledge/structured/jforex-kb/{ver}/`. Pinned dirs MUST NOT be overwritten in place; a new version creates a new directory.

#### Scenario: docs.json ingestion

- GIVEN the licensed install at `assets/SQX_144_2953_linux_20260601/`
- WHEN `DocIndexer.ingest("144.2953")` runs
- THEN ≥2,000 of the 2,533 entries become Markdown under `sqx-kb/144.2953/docs/`
- AND each doc carries provenance

#### Scenario: Version pinning

- GIVEN `sqx-kb/144.2953/docs/` exists
- WHEN a 145.0 corpus is ingested
- THEN docs land under `sqx-kb/145.0/docs/`
- AND `144.2953` files are untouched

### Requirement: REQ-KDI-03 Provenance per Document (ADDED)

Every generated doc MUST record provenance: source path or URL, license note, fetched date, and sha256 of the source artifact.

#### Scenario: Provenance recorded

- GIVEN a public wiki page crawled into `jforex-kb/2.13.99/`
- WHEN ingestion finishes
- THEN the doc's front-matter contains source URL, license note, fetch date, and sha256

### Requirement: REQ-KDI-04 No Gated Scraping (ADDED)

The system MUST NOT scrape or download license-gated (SQX User Manual) or account-gated (JForex User Manual) material.

#### Scenario: Gated source skipped

- GIVEN a source URL behind a login or license wall
- WHEN the crawler encounters it
- THEN it is skipped with a logged reason
- AND ingestion completes without the gated content

## Capability: knowledge-doc-query (NEW)

### Requirement: REQ-KDQ-01 Doc Retrieval Surface (ADDED)

The system MUST provide doc retrieval over indexed docs (token + char-3-gram cosine by default), returning ranked excerpts with doc IDs and provenance.

#### Scenario: Query returns excerpts

- GIVEN docs indexed for `sqx-kb/144.2953/docs/`
- WHEN `query_docs("ATR stop placement")` runs
- THEN ranked excerpts are returned with doc IDs and provenance
- AND an empty result (not an error) is returned when nothing matches

### Requirement: REQ-KDQ-02 Optional Embeddings (ADDED)

Embeddings MAY be used when `sentence-transformers` is available; token/3-gram MUST remain the fallback when it is not.

#### Scenario: Fallback without embeddings

- GIVEN `sentence-transformers` not installed
- WHEN `query_docs()` runs
- THEN token/3-gram cosine results are returned and no import error is raised

## Capability: sqx-doc-provider (MODIFIED)

### Requirement: REQ-SDP-01 General Doc Lookup (ADDED)

The provider MUST expose doc lookup beyond parameter YAML — `get_doc(kind, name, sqx_version)` for `block`, `api`, and `cheat-sheet` kinds backed by ingested docs. Parameter YAML behavior (REQ-F2-01..03) is unchanged.

#### Scenario: Snippet lookup for a block

- GIVEN `sqx-kb/144.2953/docs/` contains the RSI block doc
- WHEN `get_doc("block", "RSI", "144.2953")` runs
- THEN the doc references the Java snippet from the 931-snippet corpus
- AND version isolation applies as in REQ-F2-02

#### Scenario: Missing doc returns None

- GIVEN no doc for an unknown block
- WHEN `get_doc("block", "NoSuchBlock", "144.2953")` runs
- THEN None is returned and a warning is logged

## Capability: llm-research (MODIFIED)

### Requirement: REQ-LMR-01 Tool-Knowledge Templates (ADDED)

The system MUST add tool-knowledge prompt templates in `prompts.py` (block→snippet mapping, IStrategy lifecycle, @Configurable, SQX HTTP API). Templates SHALL be populated via retrieval or curated cheat-sheets only; full corpora MUST NOT be injected.

#### Scenario: Cheat-sheet injection

- GIVEN an agent prompt about a JForex strategy
- WHEN the tool-knowledge template is selected
- THEN the prompt contains the IStrategy lifecycle and @Configurable reference
- AND no full corpus text is included

### Requirement: REQ-LMR-02 KB-Driven F2 Ranges (ADDED)

`LLMResearchAgent.build_prompt` MUST derive F2 indicator ranges from `SQXDocProvider`/KB docs instead of hardcoded values.
(Previously: F2 ranges hardcoded — RSI [2,200], BB [2,200]/[0.1,5.0], EMA/SMA [2,500], ATR [2,200], MACD [2,200])

#### Scenario: Ranges from KB

- GIVEN KB docs define an RSI range
- WHEN the F2 block renders
- THEN the KB range is shown
- AND no hardcoded range remains in `llm_research_agent.py`

#### Scenario: Missing range falls back

- GIVEN no KB doc for an indicator
- WHEN the F2 block renders
- THEN the range is omitted and a warning is logged (no invented range)

## Capability: knowledge-storage (MODIFIED)

### Requirement: Directory Initialization (MODIFIED)

The system MUST create the Knowledge Lake skeleton: `raw/`, `structured/`, `graph/`, `embeddings/`, `datasets/`, `pipeline-runs/`, `agent-memory/`. `structured/` SHALL host the reconciled sub-layouts `structured/{campaign_id}/` (configs, metrics, results), `structured/sqx-kb/{sqx_version}/parameters/{tab}/`, `structured/sqx-kb/{sqx_version}/docs/`, `structured/jforex-kb/{jforex_version}/`, and `structured/sqx-version/{old}→{new}/`. Each directory SHALL contain a `.gitkeep` or metadata file.
(Previously: 7-dir skeleton without `sqx-kb/{ver}/docs/` or `jforex-kb/`)

#### Scenario: Fresh initialization creates all directories

- GIVEN a `knowledge/` path that does not exist
- WHEN the system initializes the Knowledge Lake
- THEN the 7 top-level dirs and all structured sub-layouts (incl. `sqx-kb/{ver}/docs/` and `jforex-kb/`) exist, each with a `.gitkeep`

#### Scenario: Re-initialization on existing structure is idempotent

- GIVEN an already-initialized Knowledge Lake with files present
- WHEN the system initializes again
- THEN no existing files are modified or deleted, and no error is raised

### Requirement: REQ-403 Index v4 Compatibility (MODIFIED)

The system MUST bump `knowledge/index.yaml` to version 4, covering the reconciled layout: campaign metrics/tags/links, agent-memory decisions, KB parameter files, version-pinned doc directories, and version events. The index MUST read legacy v1–v3 indexes with defaults (backward compatible).
(Previously: covered campaign/agent-memory/parameters/version-events but not doc directories)

#### Scenario: Rebuild covers docs

- GIVEN entries in `sqx-kb/144.2953/docs/` and `jforex-kb/2.13.99/`
- WHEN `rebuild_index()` runs
- THEN index.yaml is version 4 and indexes each doc file with path, size, and sha256

#### Scenario: Legacy index readable

- GIVEN an index.yaml of version 1
- WHEN `read_index()` runs
- THEN entries parse with defaults and no error

## Out of Scope

- Gated manuals: SQX User Manual (license-gated), JForex User Manual (account-gated)
- Non-English docs
- Redistribution of licensed artifacts in git (prohibited — REQ-KDI-01)
- P4 continuous version sync (future change)
- Dukascopy MCP runtime integration