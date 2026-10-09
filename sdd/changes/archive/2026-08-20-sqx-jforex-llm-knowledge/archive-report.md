# Archive Report: SQX + JForex 4 Knowledge for LLM Agents

**Change**: sqx-jforex-llm-knowledge
**Archived**: 2026-08-20
**Artifact store**: hybrid
**Mode**: Strict TDD

## Final State

- **Tasks**: 12/12 complete (4+2+2+2+2) across U1-U6.
- **PR plan**: 6 stacked PR slices (U1-U6), all merged to main.
- **Tests**: 88 focused tests passed, 0 new failures.
- **Transport deviation**: sdd-apply/general workers returned `sdd_task_result_empty` for this change; user authorized direct inline implementation for U1-U6 under the sdd-apply skill contract. All slices were implemented inline, tested, and commited as work units.

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| sqX-doc-provider | Created | General doc lookup (`get_doc`), KB-driven indicator ranges (`get_indicator_range`) |
| llm-research | Updated | Tool-knowledge templates (`TOOL_KNOWLEDGE_TEMPLATES`), KB-driven F2 ranges (`_render_f2_ranges`) |
| knowledge-storage | Updated | Directory init adds `docs/_template` and `jforex-kb/_template`; index `docs` section with legacy default |
| knowledge-doc-ingestion | Created | Raw corpus isolation (KDI-01), version-pinned ingestion (KDI-02), provenance (KDI-03), no gated scraping (KDI-04) |
| knowledge-doc-query | Created | Doc retrieval surface (`query_docs`), optional embeddings fallback (KDQ-01/02) |

## Source of Truth Updated

The following main specs now reflect the new behavior:
- `openspec/specs/sqX-doc-provider/spec.md`
- `openspec/specs/llm-research/spec.md`
- `openspec/specs/knowledge-storage/spec.md`
- `openspec/specs/knowledge-doc-ingestion/spec.md`
- `openspec/specs/knowledge-doc-query/spec.md`

## Deviations from Design

All deviations documented in `apply-progress.md` are recorded here as final state:

- sqX_doc_provider.py was untracked in HEAD (existed only in working tree from prior sessions); U1 extended it without breaking imports.
- F2 hardcoded ranges replaced by `_render_f2_ranges` with layered fallback: KB-driven → `_F2_DEFAULT_RANGES` → warning + omit.
- `QueryResult` extended with optional `docs` field to carry doc retrieval results alongside campaign results.
- `DocIndexer` sha256 computed deterministically (source + body only, no timestamp) to preserve idempotency across re-ingest.
- WikiAdapter uses minimal HTML→Markdown regex normalizer; complex wiki pages may lose formatting (acceptable for v1).
- `sentence-transformers` is not a project dependency; embeddings path is guarded and falls back to token/3-gram cosine.
