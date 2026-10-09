# T9 Research Agent Enhancements (reconciliado)

**Branch**: feature/t9-research-agent-enhancements
**Base**: feature/installer-onboarding-consent-flow (actual)
**Objetivo**: Implementar 26 tasks reconciliados (22 verdes + 4 consolidaciones) en 4 PRs encadenados.

## PR 1: Foundation (EmbeddingService + similarity + metrics)

| Task | Descripción | Estado | Commit | Evidencia |
|------|-------------|--------|--------|-----------|
| 1.1 | EmbeddingService (embed, similarity, fallback TF-IDF) | ✅ HECHO | | 12 tests pass |
| 1.2 | embeddings/ dir existe (store.py:55) → version bump a 6 | ✅ HECHO | | v6 + migración + _build_embeddings_index; 31+23 tests |
| 1.3 | QueryBuilder.filter_by_similarity() (usa EmbeddingService) | ✅ HECHO | | 10 tests pass; KNOWLEDGE_DIRS += campaigns/results/tags |
| 1.4 | Indexer.compute_tag_sharpe_stats() + best_params_by_market (desde TagCalibrator) | ✅ HECHO | | 9 tests (incl. equivalencia con TagCalibrator) |
| 1.5 | Tests unitarios: EmbeddingService, filter_by_similarity, Indexer metrics | ✅ HECHO | | 12 + 11 + 9 tests |
| 1.6 | Test integración: write embeddings → query similarity → verify ranking | ✅ HECHO | | e2e real-path + ranking con mocks |

## PR 2: Providers (Literature + Screener) — ✅ HECHO

| Task | Descripción | Estado | Commit | Evidencia |
|------|-------------|--------|--------|-----------|
| 2.1 | data/literature/ (LiteratureProvider + PaperItem) | ✅ | daa5bb2 | 6 tests |
| 2.2 | AcademicPapersProvider (arXiv Atom, sin dep nueva; SSRN diferido) | ✅ | 0799d88 | 7 tests |
| 2.3 | QuantBlogProvider (RSS, dedup) | ✅ | ef643f8 | 5 tests |
| 2.4 | SQXDocProvider — ✅ HECHO T7 | ✅ | 99109d5 | sqx_doc_provider.py |
| 2.5 | StockScreenerProvider (AlphaVantage; Finviz diferido) | ✅ | 10f8297 | 8 tests |
| 2.6 | LLMResearchAgent.fetch_data() paralelo + graceful degradation | ✅ | e0f0052 | 4 tests + 19 news sin regresión |
| 2.7 | Prompt templates research-literature + sqx-catalog | ✅ | | 7 tests + fix g3 v6 |
| 2.8 | Tests providers | ✅ | | 37 tests totales PR2 |

## PR 3: LLM Intelligence

| Task | Descripción | Estado | Commit | Evidencia |
|------|-------------|--------|--------|-----------|
| 3.1 | DiversityEngine (variantes paramétricas, dedup, factor configurable) | ⏳ Pendiente | | |
| 3.2 | PreValidator (indicador existe, rango, coherencia, dirección) | ⏳ Pendiente | | |
| 3.3 | Integración DiversityEngine en formulate_hypotheses/parse_response | ⏳ Pendiente | | |
| 3.4 | Integración PreValidator en generate_config (policy strict/lenient/off) | ⏳ Pendiente | | |
| 3.5 | Exponer TagCalibrator per-tag stats en LLMResearchAgent.build_prompt() | ⏳ Pendiente | | |
| 3.6 | HypothesisBuilder LLM mode: inyectar contexto semántico | ⏳ Pendiente | | |
| 3.7 | HypothesisConfig: embedding + feedback fields (validation_warnings ya existe) | ⏳ Pendiente | | |
| 3.8 | Tests: DiversityEngine, PreValidator, prompt injection | ⏳ Pendiente | | |

## PR 4: Integration + Feedback Loop

| Task | Descripción | Estado | Commit | Evidencia |
|------|-------------|--------|--------|-----------|
| 4.1 | FeedbackWriter — ✅ HECHO T7 | ✅ | cc51e7c | feedback_writer.py |
| 4.2 | Hook feedback en boundary review→archive | ⏳ Pendiente | | |
| 4.3 | AgentMemoryManager.query_cross_agent() + semantic + calibración | ⏳ Pendiente | | |
| 4.4 | Feedback ingestion en Knowledge Store indexing | ⏳ Pendiente | | |
| 4.5 | Test e2e feedback loop | ⏳ Pendiente | | |

## PR 5: Verification & Regression

| Task | Descripción | Estado | Commit | Evidencia |
|------|-------------|--------|--------|-----------|
| 5.1 | Full suite + fix regresiones | ⏳ Pendiente | | |
| 5.2 | Test e2e: pipeline produce ≥1 accepted strategy | ⏳ Pendiente | | |
| 5.3 | Tests privacidad/deny-list providers + feedback | ⏳ Pendiente | | |
| 5.4 | Actualizar specs/llm-research/spec.md | ⏳ Pendiente | | |
| 5.5 | Actualizar specs/hypothesis-builder/spec.md | ⏳ Pendiente | | |
| 5.6 | Actualizar specs/knowledge-store/spec.md | ⏳ Pendiente | | |
| 5.7 | Actualizar specs/knowledge-memory/spec.md | ⏳ Pendiente | | |

---

**Regla**: un task = un commit work-unit (≤400 líneas). Tests + docs en mismo commit. Branch feature primero, chained PRs.

**Reviews**: 6d9a518 → medium/slice_budget_reached, granted por usuario, lens review-reliability indisponible (transport binding, 2 intentos) → commit sostenido por verificación funcional. 030361e → medium/under_budget (acumula en slice).

**Próximo**: PR 2 — Task 2.1 data/literature/ (LiteratureProvider + PaperItem)
