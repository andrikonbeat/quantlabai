# Design: SQX + JForex 4 Knowledge for LLM Agents

## Technical Approach

Phased hybrid (spec D). P1: curated cheat-sheets + tool-knowledge templates + KB-driven F2 ranges. P2: `DocIndexer` extracts the licensed SQX install (docs.json 2,533 entries, 931 snippets, 605 JForex templates) and public wikis into version-pinned Markdown; raw gitignored, structured holds docs + provenance. P3: token/3-gram retrieval reusing `query.py` cosine plumbing. Backward compat: parameter API unchanged; index stays v5 (spec "v4" is historical; ladder reads v1–v4).

```
SQX install ─┐
public wikis ├→ DocIndexer (adapters) → knowledge/raw/{sqx,jforex}/{ver}/   (gitignored)
             └     │ normalize + provenance
                   ▼
      structured/{sqx-kb,jforex-kb}/{ver}/docs/*.md
                   │ rebuild_index → docs section (index v5)
                   ▼
  query_docs / get_doc → agent context (prompts.py, F2 block)
```

## Architecture Decisions

| # | Decision | Tradeoff | Choice |
|---|----------|----------|--------|
| D1 | Spec shape | cohesive delta vs finer diffs | Single spec.md; archive may split later |
| D2 | DocIndexer form | runnable vs testable | Package + `__main__` CLI |
| D3 | Embeddings | size/offline vs weaker semantics | Token/3-gram default; guarded `EmbeddingProvider` hook; no dep (KDQ-02) |
| D4 | Wiki crawl | freshness vs stability | Snapshot at ingest; never runtime (KDI-02/03) |
| D5 | Provenance | self-contained vs single file | Front-matter per doc + `provenance.yaml` (KDI-03) |
| D6 | Index version | spec literal vs code reality | Keep v5; add `docs` section |
| D7 | Cheat-sheet location | — | `structured/sqx-kb/{ver}/cheat-sheets/` mirrors `educational/` |
| D8 | F2 fallback | spec scenario vs no-KB degradation | KB wins; KB missing → defaults; doc missing → omit + warn (LMR-02) |

## Component Design

### DocIndexer (new)

`python -m quantlab.knowledge.ingest ingest --source {sqx-install|wiki} --version 144.2953 [--install-path assets/SQX_144_2953_linux_20260601]`

Adapters implement `extract()`/`normalize()`: `DocsJsonAdapter` (FQN→description dict), `SnippetsAdapter` (10 category dirs), `TemplatesAdapter` (`Code/JForex/`), `WikiAdapter` (httpx; gated URLs skipped — KDI-04). Writes raw → `knowledge/raw/{sqx|jforex}/{ver}/`, normalized → `structured/{sqx-kb|jforex-kb}/{ver}/docs/{kind}s/{slug}.md`. Idempotent: skip when same sha256 exists; never delete; new version → new dir (KDI-02). Provenance front-matter: `source`, `license` (`licensed-sqx-install|public-wiki`), `fetched_at`, `sha256` (KDI-03).

### SQXDocProvider (extend)

Parameter API untouched (REQ-F2-01..03). Add `get_doc(kind, name, sqx_version) -> DocRef | None` for `block|api|cheat-sheet` and `get_indicator_range(indicator, sqx_version) -> tuple[float,float] | None`. Missing doc → `None` + warning (SDP-01).

### knowledge-storage

`STRUCTURED_SUB_LAYOUTS` += `structured/sqx-kb/_template/docs/_template`, `structured/jforex-kb/_template` (idempotent `initialize()`). `rebuild_index()` gains `_build_docs_index()` → `docs` section: relpath → {size, sha256, kind, version}.

### llm-research

Replace hardcoded F2 block (`llm_research_agent.py:484-500`; dead `SQXDocProvider()` instantiation) with `_render_f2_ranges(provider, version)` per D8. `prompts.py` gains `TOOL_KNOWLEDGE_TEMPLATES`: `sqx_block_snippet`, `jforex_lifecycle`, `sqx_http_api` — populated via retrieval/cheat-sheets only (LMR-01).

### Query surface

`KnowledgeStore.query_docs(query, top_k=5, version=None)` → `DocQuery` in query.py reusing `_tokenize`/`_add_text`/`_text_cosine`; optional embeddings hook via guarded import (KDQ-01/02). Empty result, not an error.

## Chained PR Plan (stacked to main; ≤400 lines, tests in-commit)

| PR | Branch | Phase | Scope (REQs) |
|----|--------|-------|--------------|
| 1 | `feat/knowledge-docs/p1a-cheatsheets` | P1 | templates + cheat-sheets + `get_doc` (LMR-01, SDP-01) |
| 2 | `feat/knowledge-docs/p1b-f2-ranges` | P1 | F2 KB-driven ranges (LMR-02) |
| 3 | `feat/knowledge-docs/p2a-layout-index` | P2 | sub-layouts + docs index + gitignore test (403, KDI-01) |
| 4 | `feat/knowledge-docs/p2b-ingest-core` | P2 | ingest package + CLI + provenance + fixtures (KDI-02/03) |
| 5 | `feat/knowledge-docs/p2c-wiki` | P2 | wiki adapter + gated skip (KDI-03/04) |
| 6 | `feat/knowledge-docs/p3-query` | P3 | query_docs + embeddings hook (KDQ-01/02) |

Each slice: standalone, verified in-slice, rollback = revert (PR1–3 independent; PR4–5 need PR3; PR6 needs PR4).

## Testing Strategy

Strict TDD, runner `SQX_FORCE_MOCK=1 python3 -m pytest -q <path>` — never binds the real SQX daemon.

| Layer | What | How |
|-------|------|-----|
| Unit | `get_doc`/`get_indicator_range`; F2 render; adapters; `query_docs` | per-component tests; docs.json fixture; golden Markdown |
| Integration | `initialize()` idempotency; docs index; provenance; gitignore enforcement | `test_knowledge_store_v5.py` + `test_knowledge_docs.py` |
| E2E | CLI ingest on fixture; ranked excerpts | subprocess test on tmp root |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. CLI is a Python module entry; wiki fetch is httpx. All 5 rows N/A.

## Migration / Rollout

No data migration. Stacked rollout per PR plan. P1 reversible (remove injection, restore defaults). P2 dirs deletable. P3 falls back when docs absent.

## Risks

| Severity | Risk | Mitigation |
|----------|------|------------|
| CRITICAL | Licensed content enters git (KDI-01) | raw gitignored; commit facts + provenance; enforcement test in PR3 |
| WARNING | Wiki crawl breaks / rate limits | version-pinned snapshots; crawl is maintenance, not runtime (D4) |
| WARNING | Docs bloat prompts | retrieval + curated cheat-sheets only (LMR-01) |
| WARNING | F2 ranges lost without KB | curated default fallback (D8) |
| LOW | docs.json FQN→slug ambiguity | slug = sanitized FQN; kind from FQN segment |

## Open Questions

- [ ] Embeddings model if enabled later (deferred, non-blocking)