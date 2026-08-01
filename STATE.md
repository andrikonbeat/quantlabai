# QuantLab AI — Estado Completo del Proyecto

> **Actualizado**: 2026-08-01
> Proyecto: `/home/ogzuz/Proyectos/QuantLab AI`
> Rama: `main` (limpia)
> Test suite (ambos árboles): **2572 passed, 3 skipped, 49 failed** en 181s — 2622 tests recogidos
> Los 49 fallos son S2 (news lazy-init, dashboard) o pre-existentes fuera de alcance (ver §Tests)

---

## 📋 Resumen General

QuantLab AI es un SDK cuantitativo para trading algorítmico con StrategyQuant X.
**Stack**: Python 3.14, Pydantic, PyYAML, Plotly, Pandas, Jinja2, Matplotlib (opcional).

### Estructura

```
sdk/
├── quantlab/
│   ├── agents/         # 6 agent stages + ResearchDirector + AgentMemoryManager + refutation/
│   ├── cfx/            # CFX reader/writer/patcher/dom/models
│   ├── cli/            # pipeline, agent_memory, campaign, api commands + main
│   ├── dsl/            # ResearchConfig models + parser
│   ├── gates/          # HumanGateOrchestrator, notifiers, models
│   ├── knowledge/      # KnowledgeStore, Indexer, QueryBuilder, Models
│   ├── phase4/         # JForex, Portfolio, Optimizer, Retester, CampaignOrchestrator, Checkpoint
│   ├── pipeline/       # Pipeline runner, stages, registry, config, license, progress
│   ├── readers/        # CSV/XLSX databank readers
│   ├── reporting/      # Report generator, templates, CLI
│   ├── stats/          # StatisticsEngine, aggregation
│   ├── tools/          # Exception hierarchy
│   └── translate/      # DSL-to-CFX translator
├── tests/              # árbol canónico de tests (testpaths incluye ambos árboles)
├── docs/               # Architecture, configuration, multi-agent docs
└── examples/           # pipeline.yaml, research-config.yaml
```

Además: `tests/` en la raíz (árbol heredado; testpaths recoge ambos: `tests sdk/tests`).

---

## 🏁 Fases Completadas

| Fase | Estado |
|------|--------|
| Fase 1 — SDK Core | ✅ Mergeado |
| Fase 3 — CFX Engineering | ✅ Mergeado |
| Fase 4 — JForex/Port/Opt | ✅ Mergeado |
| Fase 5 — Pipeline Core | ✅ Mergeado |
| Fase 5b-e — Extensions | ✅ Mergeado |
| Fase 5f-i — Reporting/Config/Docs | ✅ Mergeado |
| **Sistema Multi-Agent** (6 PRs) | **✅ Mergeado** |
| └ PR 1: Foundation & Pipeline Extensions | ✅ |
| └ PR 2: Core Agents (ResearchDirector, Research, Builder) | ✅ |
| └ PR 3: Analysis Agents (Statistics, Reviewer, Portfolio) | ✅ |
| └ PR 4: Gates (incluido en PR 5) | ✅ |
| └ PR 5: Monitoring/Persistence/Reporting | ✅ |
| └ PR 6: CLI/Integration/Docs (review fixes aplicados) | ✅ |
| **Production Readiness — Slice 1 (Foundation)** | **✅ Aplicado (PR pendiente)** |
| └ Packaging setuptools + CLI `quantlab` | ✅ |
| └ pytest unificado (ambos árboles) + dedup DSL | ✅ |
| └ Guardian imports + stats test + openai sys.modules fix | ✅ |
| └ Docker/compose sin poetry, CI pip, junk y dups eliminados | ✅ |
| └ SQX zip untracked + gitignore | ✅ |
| **Production Readiness — Slice 2 (Behavior)** | 🔲 Pendiente (S2) |

---

## 🧠 Sistema Multi-Agent (completo en main)

**8 agentes + 5 gates humanos** orquestados via PipelineRunner:

| Componente | Archivo |
|------------|---------|
| Research Director | `agents/research_director.py` |
| Research Agent | `agents/research_agent.py` |
| Builder Agent | `agents/builder_agent.py` |
| Statistics Agent | `agents/statistics_agent.py` |
| Reviewer Agent | `agents/reviewer_agent.py` |
| Portfolio Agent | `agents/portfolio_agent.py` |
| Deployment Agent | `agents/deployment_agent.py` |
| Monitoring Agent | `agents/monitoring_agent.py` |
| Human Gate Orchestrator (5 gates) | `gates/orchestrator.py` |
| Agent Memory Manager | `agents/memory.py` |
| Refutation layer | `agents/refutation/` |
| CLI commands | `cli/pipeline_commands.py`, `cli/agent_commands.py`, `cli/campaign_commands.py` |

**Cambios totales: ~16.560 líneas, 82 archivos.**

---

## 🧩 Módulos Recientemente Agregados

| Módulo | Propósito |
|--------|-----------|
| `phase4/checkpoint.py` | Checkpoint save/resume para campañas sqcli (moved from pipeline/) |
| `phase4/models.py` | Tipos compartidos: CampaignPhase, PhaseStatus, PhaseResult |
| `pipeline/license.py` | LicenseManager para licencias SQX |
| `pipeline/progress.py` | ProgressCallback protocol |
| `pipeline/runner.py` | Retry logic con exponential backoff + ProgressCallback integration |
| `agents/refutation/` | Capa de refutación (committed as-is, sin features nuevos) |

(Cherry-picked desde `feature/phase2-local-execution` — adaptados a main.)
Checkpoint movido a `phase4/` para evitar circulares y cableado en `CampaignOrchestrator`.

---

## 🔧 Design Gaps Resueltos

| Gap | Fix |
|-----|-----|
| `HOLD` faltante en `FallbackPolicy` | Agregado a `gate_interceptor.py` + `GateAction.HOLD` + `gates/models.py` |
| `escalate_to` ausente en `GateConfig` | ✅ Ya existía en `pipeline/config/models.py` |
| `notifications` vs `notifiers` | ✅ El campo correcto es `notifications` |

---

## 🧪 Tests

**Workflow actual** (unificado, sin poetry):

```bash
# Desde la raíz del repo
pytest -q                # testpaths = tests sdk/tests (ambos árboles)
pytest sdk/tests/test_guardian -q   # 48 passed
```

- `pytest.ini` raíz: `testpaths = tests sdk/tests`; `norecursedirs` incluye `assets`, `sdk/.venv`, etc.
- `conftest.py` raíz añade `sdk/` a `sys.path` para imports `quantlab.*`.
- Entorno: `sdk/.venv` (Python 3.14.4, pytest 9.1.1). Sin `uv.lock` (uv no disponible; deps vía pip).

| Suite | Recogidos | Pasados | Fallos | Saltados |
|-------|-----------|---------|--------|----------|
| Ambos árboles (2026-08-01) | **2622** | **2572** | **49** | **3** |

Nota: la suite requiere `SQX_FORCE_MOCK=1` en el entorno para completar
(`test_run_writes_context_artifacts` usa el daemon real de sqcli si existe y
bloquea el puerto 5050; con mock pasa en ~13s). Sin la variable, ese test cuelga.

Los 49 fallos se descomponen:
- **S2 (en alcance de Slice 2)**: `sdk/tests/agents/test_llm_agent_news.py` (lazy-init/`_get_web_search` — T25), `tests/dashboard/*` (static/API/integration — T20–T24), `tests/news/*` + `sdk/tests/news/*` (T25).
- **Pre-existentes fuera de alcance**: `tests/robustness/*` (circuit breaker, buffering, monitor health), `tests/phase5/test_pipeline_registry.py`, `sdk/tests/test_knowledge.py`, `sdk/tests/phase4/test_llm_generation_monitor.py`, `tests/cfx/test_reader.py`, `tests/phase4/test_retester.py` (flake dependiente de orden; pasa solo).

---

## 🗺️ Pendientes y Deuda Técnica

- [ ] **Slice 2 (Behavior)**: guards PID/mock/licencia, dashboard API, news lazy-init — tasks T14–T25 en `openspec/changes/production-readiness/`
- [ ] `test_full_17_stage_pipeline_dry_run` — fixture setup roto, marcado @skip deliberadamente
- [ ] `LicenseManager` — exportado pero sin uso. Integrar en CLI como subcomando `license`
- [ ] PipelineRunner.run_with_gates() — tiene retry logic pero no maneja GateTimeoutError como el run() simple
- [ ] `sqx` zip grande (1.2 GB) — untracked (`git rm --cached` + `.gitignore assets/SQX_*.zip`); no LFS
- [ ] nginx service — eliminado (TLS fuera de alcance); `docker compose` sin validar (docker no disponible)
- [ ] `stash@{0}` `sdd-slice1-bisect` — pendiente de verificación/drop

---

## 🔧 Comandos Útiles

```bash
# Tests completos (ambos árboles, con mock)
SQX_FORCE_MOCK=1 python -m pytest -q

# CLI
sdk/.venv/bin/python -m quantlab.cli api --help

# Ver estado
git status
git log --oneline -10
```
