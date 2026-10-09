# Tasks: SQX + JForex 4 Knowledge for LLM Agents

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,700 total; ≤400 per slice |
| 400-line budget risk | Low |
| Chained PRs recommended | Yes |
| Suggested split | PR1 → PR2 → PR3 → PR4 → PR5 → PR6 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

## Suggested Work Units

| Unit | Goal (scope) | PR | Focused test command | Runtime harness | Rollback boundary |
|------|--------------|----|----------------------|-----------------|-------------------|
| U1 | Cheat-sheets + tool templates + `get_doc` (LMR-01, SDP-01) | PR1 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/test_doc_provider_docs.py tests/agents/test_tool_knowledge_templates.py` | N/A — pure functions; no daemon/network | Revert templates + `get_doc`; parameter YAML API untouched |
| U2 | KB-driven F2 ranges (LMR-02) | PR2 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents/test_llm_research_agent_f2.py` | N/A — prompt render is pure | Revert `_render_f2_ranges`; old defaults restored |
| U3 | Sub-layouts + docs index + gitignore (REQ-403, KDI-01) | PR3 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/test_knowledge_store_v5.py` | `git status --porcelain` on tmp raw fixture | Remove new sub-layout dirs + `.gitignore` line |
| U4 | DocIndexer core: docs.json/snippets/templates (KDI-02/03) | PR4 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/test_ingest.py` | `python3 -m quantlab.knowledge.ingest ingest --source sqx-install --version 144.2953 --install-path <fixture>` | Remove `ingest/` package + structured dirs; raw gitignored |
| U5 | Wiki adapter + gated skip (KDI-03/04) | PR5 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/test_wiki_adapter.py` | CLI wiki ingest on fixture URL (mocked httpx) | Remove `wiki.py`; `jforex-kb` dirs deletable |
| U6 | `query_docs` + embeddings hook (KDQ-01/02) | PR6 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/knowledge/test_query_docs.py` | `query_docs("ATR stop placement")` on fixture KB | Revert query surface; agents fall back to no-doc behavior |

## PR Mapping (stacked-to-main)

| PR | Branch | Unit | Base → Target |
|----|--------|------|---------------|
| PR1 | `feat/knowledge-docs/p1a-cheatsheets` | U1 | main → main |
| PR2 | `feat/knowledge-docs/p1b-f2-ranges` | U2 | main → main |
| PR3 | `feat/knowledge-docs/p2a-layout-index` | U3 | main → main |
| PR4 | `feat/knowledge-docs/p2b-ingest-core` | U4 | main → main |
| PR5 | `feat/knowledge-docs/p2c-wiki` | U5 | main → main |
| PR6 | `feat/knowledge-docs/p3-query` | U6 | main → main |

## Unit Tasks (Strict TDD: RED → GREEN in-commit; threat matrix all 5 rows N/A → no threat RED tasks)

### U1 — Phase 1: P1a cheat-sheets + templates + get_doc
- [x] T-01 (LMR-01) RED: `tests/agents/test_tool_knowledge_templates.py` asserts `TOOL_KNOWLEDGE_TEMPLATES` in `sdk/quantlab/agents/prompts.py` has `sqx_block_snippet|jforex_lifecycle|sqx_http_api` | GREEN: add templates; populate via retrieval/curated cheat-sheets only | AC: prompt shows IStrategy lifecycle + @Configurable; no full corpus injected
- [x] T-02 (SDP-01) RED: `tests/knowledge/test_doc_provider_docs.py` — `get_doc("block","RSI","144.2953")` returns DocRef referencing snippet; `None`+warning for missing | GREEN: add `get_doc(kind,name,ver)` to `sdk/quantlab/knowledge/sqX_doc_provider.py` reading `structured/sqx-kb/{ver}/docs/{kind}s/{slug}.md`; version isolation (REQ-F2-02) | AC: snippet lookup + missing→None
- [x] T-03 (SDP-01) GREEN: cheat-sheet kind reads `structured/sqx-kb/{ver}/cheat-sheets/` (mirrors `sdk/quantlab/knowledge/kb/educational.py`); commit 3 cheat-sheets (block→snippet, lifecycle, HTTP API) | AC: cheat-sheet lookup returns file

### U2 — Phase 1: P1b KB-driven F2 ranges
- [x] T-04 (LMR-02) RED: extend `tests/agents/test_llm_research_agent_f2.py`: F2 block renders KB-defined RSI range; missing doc → range omitted + warning | GREEN: add `get_indicator_range(indicator,ver)` to `SQXDocProvider`; replace hardcoded block `llm_research_agent.py:484-500` with `_render_f2_ranges(provider,ver)` | AC: no hardcoded range remains in `llm_research_agent.py`

### U3 — Phase 2: P2a layout + docs index + gitignore
- [x] T-05 (REQ-403) RED: extend `tests/knowledge/test_knowledge_store_v5.py`: `initialize()` creates `structured/sqx-kb/_template/docs/_template` + `structured/jforex-kb/_template`, idempotent re-init; `rebuild_index()` yields v5 `docs` section (relpath→{size,sha256,kind,version}); v1 index readable | GREEN: extend `STRUCTURED_SUB_LAYOUTS` (store.py:80), add `_build_docs_index()` (rebuild_index, store.py:463), legacy defaults in `read_index()` (store.py:536) | AC: fresh + re-init + docs indexed
- [x] T-06 (KDI-01) RED: `tests/knowledge/test_knowledge_docs.py` — file under `knowledge/raw/sqx/144.2953/` never tracked/staged (git status --porcelain) | GREEN: add `knowledge/raw/*` to `.gitignore` | AC: raw never staged; no licensed content under `knowledge/structured/`

### U4 — Phase 2: P2b ingest core
- [x] T-07 (KDI-02) RED: `tests/knowledge/test_ingest.py` + fixture docs.json — `DocIndexer.ingest("144.2953")` writes ≥2,000 md under `structured/sqx-kb/144.2953/docs/`; new version → new dir, old untouched; idempotent (same sha256 skipped) | GREEN: `sdk/quantlab/knowledge/ingest/` package — `__main__.py` CLI (`python -m quantlab.knowledge.ingest ingest --source sqx-install --version 144.2953 [--install-path]`), `adapters.py` (`DocsJsonAdapter`, `SnippetsAdapter` 10 dirs, `TemplatesAdapter` Code/JForex), slug=sanitized FQN, kind from FQN | AC: ≥2,000 docs + version pinning
- [x] T-08 (KDI-03) RED: provenance test — every doc front-matter has `source|license|fetched_at|sha256`; golden markdown | GREEN: write front-matter + `provenance.yaml` per doc (D5) | AC: provenance recorded per doc

### U5 — Phase 2: P2c wiki adapter
- [x] T-09 (KDI-04) RED: `tests/knowledge/test_wiki_adapter.py` (mocked httpx) — login/license-gated URL skipped with logged reason; ingest completes without gated content | GREEN: `wiki.py` — httpx `WikiAdapter`, snapshot-at-ingest (D4), gated-URL guard | AC: gated source skipped
- [x] T-10 (KDI-03) GREEN: wiki crawl writes raw + normalized `structured/jforex-kb/{ver}/docs/*.md` with `public-wiki` license + provenance front-matter | AC: jforex docs carry source URL/license/fetch date/sha256

### U6 — Phase 3: P3 query_docs + embeddings hook
- [x] T-11 (KDQ-01) RED: `tests/knowledge/test_query_docs.py` — `query_docs("ATR stop placement",top_k=5,version)` returns ranked excerpts with doc IDs + provenance; no match → empty result, not error | GREEN: `DocQuery` in `sdk/quantlab/knowledge/query.py` reusing `_tokenize`/`_add_text`/`_text_cosine`; `KnowledgeStore.query_docs` in `store.py` reading index `docs` section | AC: ranked excerpts + empty-not-error
- [x] T-12 (KDQ-02) RED: without `sentence-transformers`, `query_docs` returns token/3-gram results, no ImportError | GREEN: guarded `EmbeddingProvider` hook (D3), token/3-gram fallback default | AC: fallback works offline

## Verification Plan

- Per-slice gates: focused commands above, run inside each PR with in-commit tests.
- Full-suite gate (root pytest.ini, tests + sdk/tests): `SQX_FORCE_MOCK=1 python3 -m pytest -q`
- Never bind the real SQX daemon (port 5050) — mock only.