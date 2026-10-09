# Tasks: Research Agent Enhancements (RECONCILIADO 2026-10-07)

> **Scope reconciliado contra HEAD**: 8 de 34 tasks originales ya están total/parcialmente implementadas por T7/T8. Quedan **22 tasks verdes + 4 consolidaciones** = ~26 tasks reales. Forecast reestimado: ~800-1200 líneas.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~800-1200 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation (EmbeddingService + similarity) → PR 2: Providers (literature + screener) → PR 3: LLM Intelligence (DiversityEngine + PreValidator + prompt injection) → PR 4: Integration + Feedback loop |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |
| Decision needed before apply | **AUTORIZADO** (usuario: "Corrige todo esto y haz el R9 como es debido") |

---

## Phase 1: Foundation — Knowledge Lake Semantic Layer (PR 1)

### 1.1 EmbeddingService (GREENFIELD)
- [x] 1.1 Create `sdk/quantlab/knowledge/embedding_service.py` with `EmbeddingService` class: async `embed()`, `similarity()`, graceful fallback to token similarity (TF-IDF/char 3-gram). Configurable model via env/Config. Stores `.npy` + `.meta.json` per hypothesis in `knowledge/embeddings/`. Index version bump to 6 in `store.py`.

### 1.2 KnowledgeStore embeddings dir + version bump (CONSOLIDACIÓN)
- [x] 1.2 `embeddings/` directory **ya existe** en `store.py:55` (creado por `initialize()`). **Solo queda**: bump `KnowledgeStore._version` de 5 a 6 en `store.py` y asegurar que `read_index()` maneje v6. Tests: `tests/knowledge/test_store_version.py`.

### 1.3 QueryBuilder.filter_by_similarity (CONSOLIDACIÓN)
- [x] 1.3 Implement `QueryBuilder.filter_by_similarity(query_text: str, top_k: int = 10, threshold: float = 0.7) -> QueryBuilder` en `query.py`. Usa `EmbeddingService.similarity()` con fallback a `_text_cosine()` (ya existe scaffolding: `_tokenize`, `_add_text`, `_text_cosine`, `search_text` en `query.py`). **Nota**: `search_similar_campaigns()` ya existe en `query.py:201` — este método es el *builder* equivalente para filtrar hipótesis.

### 1.4 Métricas por estrategia (CONSOLIDACIÓN)
- [x] 1.4 Mover/expone `avg_sharpe_by_tag` y `best_parameters_by_market` desde `TagCalibrator._build_tag_stats()` → `indexer.py` como métodos públicos `Indexer.compute_tag_sharpe_stats()` e `Indexer.compute_best_params_by_market()`. Tests en `tests/knowledge/test_indexer_metrics.py`.

### 1.5 Tests unitarios Foundation
- [x] 1.5 Tests: `EmbeddingService` (embed + similarity + fallback), `QueryBuilder.filter_by_similarity()`, `Indexer` métricas nuevas.

### 1.6 Test integración Foundation
- [x] 1.6 Test integración: write embeddings → query similarity → verify ranking (tmp Knowledge Lake, mock embeddings).

---

## Phase 2: Data Providers (PR 2)

### 2.1 Literature provider base package (RE-SCOPEADO)
- [ ] 2.1 Crear `sdk/quantlab/data/literature/` con:
  - `LiteratureProvider(AbstractDataProvider)` en `base.py` (hereda de `data/fundamental/base.py:AbstractDataProvider`, auto-registro via `__init_subclass__`).
  - `PaperItem` model en `models.py`: `title`, `authors: list[str]`, `abstract`, `url`, `arxiv_id`, `categories: list[str]`, `published_at`, `source`.
  - `__init__.py` exportando ambos.
  - **NO** crear `data/providers/` ni `BaseProvider` nuevo ni `ProviderRegistry` — reusar `AbstractDataProvider`.

### 2.2 AcademicPapersProvider
- [ ] 2.2 Implementar `AcademicPapersProvider` en `papers.py`: consulta arXiv/SSRN, filtro por categorías, rate-limit polito (reusar `data/news/rate_limit.py`). Requiere dep `arxiv` en `sdk/pyproject.toml`. Tests mock HTTP.

### 2.3 QuantBlogProvider
- [ ] 2.3 Implementar `QuantBlogProvider` en `blogs.py`: RSS feeds (feedparser ya en deps), dedup por URL, rate-limit. Tests mock feeds.

### 2.4 SQXDocProvider (✅ YA EXISTE — MARCAR HECHO)
- [x] 2.4 **COMPLETADO EN T7**: `sdk/quantlab/knowledge/sqx_doc_provider.py` existe y funciona (lee YAML de `knowledge/structured/sqx-kb/` con fallback a `_BUILD_CONFIG_MAP`). **No hay nada que hacer aquí**.

### 2.5 StockScreenerProvider
- [ ] 2.5 Implementar `StockScreenerProvider` en `screening.py` (nuevo `data/screening/`): Finviz/AlphaVantage con API keys via env vars (`data/data_manager.py` precedent). Tests mock HTTP.

### 2.6 Integración providers en LLMResearchAgent
- [ ] 2.6 Actualizar `LLMResearchAgent.fetch_data()` en `llm_research_agent.py`: ejecución paralela de providers, graceful degradation (un provider falla → log + continúa), resultados fusionados en contexto.

### 2.7 Prompt templates
- [ ] 2.7 Añadir templates `research-literature` y `sqx-catalog` a `sdk/quantlab/agents/prompts.py` (o archivos en `prompts/` si hay carpeta).

### 2.8 Tests providers
- [ ] 2.8 Tests unitarios c/providers (mock HTTP/feeds), test ejecución paralela + aislamiento de fallos.

---

## Phase 3: LLM Intelligence (PR 3)

### 3.1 DiversityEngine (GREENFIELD)
- [ ] 3.1 Crear `sdk/quantlab/agents/diversity_engine.py`: `DiversityEngine` con generación de variantes paramétricas, deduplicación por fingerprint, factor de diversidad configurable. Tests unitarios.

### 3.2 PreValidator (GREENFIELD)
- [ ] 3.2 Crear `sdk/quantlab/agents/pre_validator.py`: `PreValidator` — existencia de indicador (via `SQXDocProvider`), rango de parámetros, coherencia semántica, consistencia direccional. `validation_policy`: `strict`/`lenient`/`off`. Tests unitarios.

### 3.3 Integración DiversityEngine
- [ ] 3.3 Integrar `DiversityEngine` en `ResearchAgent.formulate_hypotheses()` y `LLMResearchAgent.parse_response()` (variantes diversificadas antes de validar).

### 3.4 Integración PreValidator
- [ ] 3.4 Integrar `PreValidator` en `ResearchAgent.generate_config()` con soporte de `validation_policy`. Tests: strict bloquea, lenient advierte, off pasa.

### 3.5 Exponer TagCalibrator al prompt LLM (CONSOLIDACIÓN — TRABAJO REAL)
- [ ] 3.5 **TRABAJO REAL**: Actualizar `LLMResearchAgent.build_prompt()` en `llm_research_agent.py` para inyectar las estadísticas per-tag del `TagCalibrator` (ya computado en `formulate_hypotheses()` path rule-based). El path LLM **no lo usa hoy**. Añadir sección `TAG_CALIBRATION` al prompt con percentiles Sharpe por tag. Tests: LLM prompt incluye calibración cuando `query_results` existe.

### 3.6 Semantic context en HypothesisBuilder LLM mode
- [ ] 3.6 Actualizar `HypothesisBuilder` LLM mode (`llm.py`) para inyectar contexto semántico (similar hypotheses de `QueryBuilder.filter_by_similarity()`); actualizar `HypothesisBuilderStage` (si existe) para pasar `market_context`.

### 3.7 HypothesisConfig fields (CONSOLIDACIÓN)
- [ ] 3.7 Extender `HypothesisConfig` en `sdk/quantlab/dsl/models.py` con campo opcional `embedding: list[float] | None` y `feedback: HypothesisFeedbackRecord | None`. `validation_warnings` ya existe (T7). `HypothesisFeedbackRecord` ya existe en `knowledge/models.py` (T7 F3).

### 3.8 Tests LLM Intelligence
- [ ] 3.8 Tests: `DiversityEngine`, `PreValidator`, inyección de prompt (3.5), inyección semántica (3.6).

---

## Phase 4: Feedback Loop & Integration (PR 4)

### 4.1 FeedbackWriter (✅ YA EXISTE — MARCAR HECHO)
- [x] 4.1 **COMPLETADO EN T7**: `sdk/quantlab/agents/feedback_writer.py` con `KnowledgeLakeFeedbackWriter` y `HypothesisFeedbackRecord` en `knowledge/models.py`. **No hay nada que hacer** (ubicación: `agents/` vs `knowledge/` per task original — la implementación T7 la puso en `agents/` y es correcta por cohesión).

### 4.2 Hook feedback en boundary review→archive
- [ ] 4.2 Hookear escritura de feedback al completar fase de review (campaign phase completion). En `gate_interceptor.py` o `research_director.py` al recibir `HUMAN_APPROVE_ARCHIVE`.

### 4.3 AgentMemoryManager retrieval semántico
- [ ] 4.3 Extender `AgentMemoryManager.query_cross_agent()` en `memory.py` para incluir búsqueda semántica (usa `EmbeddingService.similarity()`) y métricas de calibración per-tag.

### 4.4 Feedback ingestion en Knowledge Store indexing
- [ ] 4.4 Al escribir feedback, actualizar índices de Knowledge Lake (embeddings, tag stats) para que búsquedas futuras vean el feedback. En `store.py` o `indexer.py`.

### 4.5 Test integración feedback loop
- [ ] 4.5 Test e2e: campaña mock completa → feedback escrito → búsqueda semántica encuentra hipótesis similares previas con su feedback.

---

## Phase 5: Verification & Regression

- [ ] 5.1 Full test suite: `SQX_FORCE_MOCK=1 python3 -m pytest -q`; fix regresiones.
- [ ] 5.2 Test e2e: pipeline research mejorado produce ≥1 estrategia aceptada en mock mode.
- [ ] 5.3 Tests privacidad/deny-list para URLs de providers nuevos y datos de feedback.
- [ ] 5.4 Actualizar `openspec/specs/llm-research/spec.md` con providers + templates.
- [ ] 5.5 Actualizar `openspec/specs/hypothesis-builder/spec.md` con diversificación + validación.
- [ ] 5.6 Actualizar `openspec/specs/knowledge-store/spec.md` con embedding + similarity.
- [ ] 5.7 Actualizar `openspec/specs/knowledge-memory/spec.md` con semantic injection + feedback.

---

## Notas de implementación

**Solapamientos ya resueltos (no tocar):**
- `sdk/quantlab/knowledge/sqx_doc_provider.py` (T7 F2) → task 2.4 ✅
- `sdk/quantlab/agents/feedback_writer.py` + `knowledge/models.py:HypothesisFeedbackRecord` (T7 F3) → tasks 4.1, 3.7 parcial ✅
- `TagCalibrator` completo con LRU cache (T7 F1-05) → task 3.5 (solo exponer) / 1.4 (consolidar métricas)
- `search_similar_campaigns()` en `query.py:201` + `search_agent_memory()` en `query.py:138` (T7 F2 / T8) → task 1.3 scaffolding
- `embeddings/` dir en `store.py:55` (T8) → task 1.2 (solo bump)
- `AgentMemoryManager` completo (T8) → task 4.3 (solo extender retrieval)

**Archivos verdes a crear:**
- `sdk/quantlab/knowledge/embedding_service.py`
- `sdk/quantlab/data/literature/{base.py,models.py,papers.py,blogs.py,screening.py}`
- `sdk/quantlab/agents/diversity_engine.py`
- `sdk/quantlab/agents/pre_validator.py`
- Tests correspondientes

**Convención**: un task = un commit work-unit (≤400 líneas). Tests y docs junto al código. Branch feature primero, chained PRs.