# Proposal: Official SQX + JForex 4 knowledge for LLM agents

## Intent

LLM agents ground decisions only in 82 parameter YAMLs plus hardcoded ranges, with no knowledge of blocks, the StrategyQuant API, or block-to-JForex mappings. The licensed SQX install already holds the official corpus locally (2,533-entry `docs.json`, 931 snippets, 605 JForex templates, `Extending_SQX.pdf`); JForex 4 docs are public (wiki, Javadoc, SDK). Goal: ground agents in official version-pinned knowledge, never redistributing licensed material.

## Scope

### In Scope
- P1: cheat-sheets (block→snippet, IStrategy lifecycle, @Configurable, HTTP API) + prompt templates; KB-driven F2 ranges
- P2: extract install corpus + crawl wikis → version-pinned Markdown; `DocIndexer`
- P3: docs query in `query.py`/`store.py` (token/3-gram, embeddings optional)
- P4 (future): continuous sync on new versions

### Out of Scope
- Licensed/gated material in git (CRITICAL); gated manuals
- Non-English docs; Dukascopy MCP runtime

## Capabilities

### New Capabilities
- `knowledge-doc-ingestion`: corpus → version-pinned Markdown + provenance, raw gitignored
- `knowledge-doc-query`: doc retrieval; token/3-gram default, optional embeddings

### Modified Capabilities
- `sqx-doc-provider`: doc lookup beyond parameter YAML (blocks, API, cheat-sheets)
- `llm-research`: tool-knowledge templates; KB-driven F2 ranges
- `knowledge-storage`: layout gains `sqx-kb/{ver}/docs/`, `jforex-kb/`; index covers docs

## Approach

Phased hybrid (exploration D): P1 injection → P2 ingestion → P3 retrieval → P4 sync; independently shippable, P3 needs P2.

## Affected Areas

- `knowledge/raw/` (New): gitignored corpus snapshots
- `knowledge/structured/` (Modified): `sqx-kb/{ver}/docs/`, `jforex-kb/`
- `sdk/quantlab/knowledge/query.py`, `store.py` (Modified): doc retrieval + docs index
- `sdk/quantlab/knowledge/sqX_doc_provider.py` (Modified): general doc lookup
- `sdk/quantlab/agents/prompts.py`, `llm_research_agent.py` (Modified): tool templates, KB-driven ranges
- `sdk/quantlab/knowledge/kb/seeder.py` (Modified): seed from `docs.json` + snippets
- `.gitignore` (Modified): keep raw ignored

## Risks

- CRITICAL: licensed/gated redistribution in git — gitignore raw; commit facts + provenance only
- CRITICAL: gated manuals block "full" knowledge — use public wiki + Javadoc + SDK + personal extraction
- WARNING: wiki crawl breaks / rate limits — version-pinned snapshots
- WARNING: embeddings size/offline — token/3-gram default
- WARNING: prompt bloat — retrieval + cheat-sheets only
- WARNING: version drift — pinned dirs; sync P4

## Rollback Plan

Per-phase revert: P1 — remove cheat-sheet injection, restore hardcoded ranges. P2 — delete docs dirs + `DocIndexer`; raw is gitignored. P3 — drop docs query; agents fall back to today's behavior.

## Dependencies

- Licensed SQX install at `assets/` (symlink); public wikis (strategyquant.com/doc, dukascopy.com/wiki, javadoc3)
- No new runtime deps (sentence-transformers optional)

## Success Criteria

- [ ] P1: cheat-sheets answer block/API questions; no hardcoded ranges in `llm_research_agent`
- [ ] P2: ≥2,000 `docs.json` entries + ≥500 snippets normalized with provenance; no licensed content in git
- [ ] P3: docs query returns relevant excerpts; token/3-gram fallback works without embeddings
- [ ] P4: version bump triggers re-ingestion runbook