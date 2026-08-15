# QuantLab AI — Estado Completo del Proyecto

> **Actualizado**: 2026-08-14
> Proyecto: `/home/ogzuz/Proyectos/QuantLab AI`
> Rama: `feat/per-phase-subagent-delegation-pr5` (**42 commits** por delante de `main` — no es `main` limpia; `main` quedó congelado en el flujo 14-fases pre-delegación)
> Test suite (ambos árboles, `SQX_FORCE_MOCK=1`): **3449 passed, 44 failed, 12 skipped, 11 errors** en ~390s
> Los 44 fallos y los 11 errores son pre-existentes y fuera del alcance de la reorganización actual (ver §Tests)

---

## 📋 Resumen General

QuantLab AI es un SDK cuantitativo para trading algorítmico con StrategyQuant X.
**Stack**: Python 3.14, Pydantic, PyYAML, Plotly, Pandas, Jinja2, Matplotlib (opcional).
El trabajo se gobierna por **SDD** (spec-driven development): cada cambio tiene
proposal/spec/design/tasks y se archiva en `openspec/changes/archive/` al completarse.

### Estructura

```
sdk/
├── quantlab/
│   ├── agents/         # agent stages + ResearchDirector + refutation/ + adaptive_retest_agent
│   ├── campaign/       # delegación por fase (PhaseResult, delegation)
│   ├── cfx/            # CFX reader/writer/patcher/dom/models
│   ├── cli/            # pipeline, agent_memory, campaign, api, sq commands + main
│   ├── data/           # DataManager (Dukascopy) + market/ (providers, registry)
│   ├── dsl/            # ResearchConfig models + parser
│   ├── gates/          # HumanGateOrchestrator, notifiers, models
│   ├── knowledge/      # KnowledgeStore, Indexer, KB (models/store/seeder/seeding_flow)
│   ├── phase4/         # JForex, Portfolio, Optimizer, Retester, template_registry, models
│   ├── pipeline/       # Pipeline runner, stages, registry, config, license, progress
│   ├── substrate/      # executor (PhaseResult), soporte de ejecución
│   ├── customproject/  # templates (metadata + renderer de AutomaticRetest)
│   └── ...             # readers/, reporting/, stats/, tools/, translate/
├── tests/              # árbol canónico (testpaths incluye ambos árboles)
└── examples/           # pipeline.yaml, research-config.yaml
docs/                   # docs raíz reorganizadas + docs/sqx-builder-config/ (fuente KB seeder)
infra/                  # init-schema.sql (DB init, referenciado por docker-compose)
app_movil/              # app Android demo (standalone, 112 archivos trackeados)
knowledge/              # knowledge lake (agent-memory/, structured/, timeseries/)
AI/opencode/            # prompts canónicos (campaign.md + phase-*.md + guardian.md), skills
```

Además: `tests/` en la raíz y `sdk/tests/` (**dos árboles de test** — deuda
conocida; `testpaths = tests sdk/tests` recoge ambos).

---

## 🏁 Fases y Cambios SDD Completados (archivados)

| Cambio | Fecha | Estado |
|--------|-------|--------|
| Fase 1 — SDK Core → Fase 5f-i + Reporting/Config/Docs | 2026-07 | ✅ Archivado |
| Sistema Multi-Agent (6 PRs) | 2026-07 | ✅ Archivado |
| Production Readiness (Slice 1 — Foundation) | 2026-08-02 | ✅ Archivado |
| Orchestrated Campaign Flow (REQ-01..21) | 2026-08-06/09 | ✅ Archivado |
| Knowledge Memory System + Consumption Wiring | 2026-08-08 | ✅ Archivado |
| Flow Integrity Gates + Monitoring | 2026-08-10 | ✅ Archivado |
| Knowledge Seeding + Education (KB seeder, REQ-203/209) | 2026-08-11 | ✅ Archivado |
| Research Real Analysis Frame | 2026-08-11 | ✅ Archivado |
| Project Template + Retest Strategy | 2026-08-12 | ✅ Archivado |
| Guardian Orchestrator Feedback | 2026-08-13 | ✅ Archivado |
| JForex4 Integration | 2026-08-13 | ✅ Archivado |
| **Per-Phase Subagent Delegation** | 2026-08-13 | ✅ Archivado (rama actual) |
| Repo Organization + GitHub Prep | 2026-08-14 | 🔄 PR 2/3 en curso |

---

## 🧠 Sistema Multi-Agent

8 agentes + 5 gates humanos orquestados via PipelineRunner (ver detalle en
secciones previas de este doc y en `openspec/changes/archive/`).

---

## 🧭 Orchestrated Campaign Flow (14 fases, delegación por fase)

El flujo de campaña es **LLM-driven con 14 fases**:

`research → hypothesis → config → review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops`

Cada fase se delega a un **subagente dedicado** vía los prompts canónicos en
`AI/opencode/agents/phase-*.md` (14 fases) + `campaign.md` (harness) +
`guardian.md` (observación/retroalimentación en live-ops). El repo
`AI/opencode/agents/` es la **única fuente de verdad**: `sync_prompts.py`
copia repo → `~/.config/opencode/prompts/quantlab/` (idempotente; los archivos
no gestionados — `guardian.md`, `orchestrator.md`, etc. — nunca se tocan).

Cada fase devuelve el envelope Result Contract (`status`,
`executive_summary`, `artifacts`, `next_recommended`, `risks`). Los gates
humanos son **fail-closed** (REQ-11): decisión por archivo en
`/tmp/sqx-gates/{campaign_id}/`, `question` como canal primario, stdin como
fallback. `DataManager` es **solo Dukascopy** (FX M1/M5/H1).

---

## 🧩 Módulos Recientemente Agregados

| Módulo | Propósito |
|--------|-----------|
| `sdk/quantlab/data/market/` | Proveedores de datos de mercado + registry (`providers.py`, `registry.py`) |
| `sdk/quantlab/agents/adaptive_retest_agent.py` | Agente de retest adaptativo |
| `sdk/quantlab/customproject/templates.py` | Plantillas de proyecto + metadata `template_name` + renderer AutomaticRetest |
| `sdk/quantlab/phase4/template_registry.py` | Registro de plantillas |
| `app_movil/` | App Android demo standalone (112 archivos trackeados; `.gradle`/`build/` pendientes de ignore) |
| `sdk/quantlab/campaign/delegation.py`, `substrate/executor.py` | Delegación por fase y ejecución (per-phase-subagent-delegation) |

---

## 🔍 Hallazgos de la Auditoría (2026-08-14, previos al PR de reorg)

- **Islas huérfanas** (código sin referencias activas): `sdk/quantlab/broker/`,
  `sdk/quantlab/evolution/`, `sdk/quantlab/health/`, `sdk/quantlab/mcp/` —
  pendientes de triaje/eliminación (fuera del alcance de PR 1-3).
- **Tipos `PhaseResult` duplicados (x3)**: definidos en
  `sdk/quantlab/phase4/models.py`, `sdk/quantlab/campaign/delegation.py` y
  `sdk/quantlab/substrate/executor.py` — consolidar en un único tipo.
- **Dos árboles de test** (`tests/` + `sdk/tests/`): deuda heredada; el
  `testpaths` unificado los recoge, pero la duplicación persiste.
- **Reorganización aplicada (PR 1-2)**: triaje de untracked (valiosos
  commiteados, rotos/duplicados eliminados), docs movidas a `docs/` y
  `docs/sqx-builder-config/`, refs de `DEFAULT_DOC_PATH` actualizadas,
  `infra/init-schema.sql` movido de `docker/`.

---

## 🧪 Tests

```bash
# Desde la raíz del repo (mock obligatorio: el daemon real bloquea puerto 5050)
SQX_FORCE_MOCK=1 python -m pytest -q
```

| Suite | Recogidos | Pasados | Fallos | Saltados | Errores |
|-------|-----------|---------|--------|----------|---------|
| Ambos árboles (2026-08-14) | **3516** | **3449** | **44** | **12** | **11** |

Desglose (pre-existente, NO causado por la reorg de docs):
- **11 errors**: `tests/phase4/test_campaign_orchestrator.py` — fallan por
  orden/estado en la suite completa; cada test pasa individualmente (flaky
  de fixtures, pre-existente).
- **44 fallos**: deuda heredada en `tests/robustness/*`, dashboard,
  news/llm lazy-init, `test_knowledge.py`, cfx reader, retester (flake de
  orden), etc. — mismo set pre-existente, sin relación con los cambios de
  docs/refs (PR 2 no toca código funcional).
- Suites KB (fuente movida): `test_kb.py` + `test_kb_seed_validation.py` →
  **62 passed** ✓ (valida `DEFAULT_DOC_PATH` → `docs/sqx-builder-config/SQX Builder Config.md`).

---

## 🗺️ Pendientes y Deuda Técnica

- [ ] **PR 3 (GitHub prep)**: `.gitignore`/`.gitattributes`, compose →
  `infra/init-schema.sql`, README/LICENSE/SECURITY, remote add + push
- [ ] Islas huérfanas (`broker/`, `evolution/`, `health/`, `mcp/`): triaje
- [ ] Consolidar los 3 tipos `PhaseResult`
- [ ] Unificar los dos árboles de test
- [ ] `test_full_17_stage_pipeline_dry_run` — fixture roto, `@skip` deliberado
- [ ] `LicenseManager` exportado sin uso; `PipelineRunner.run_with_gates()`
  sin manejo de `GateTimeoutError`
- [ ] `app_movil/**/build/`, `.gradle/` y `*.Zone.Identifier` pendientes de `.gitignore`
- [ ] Backup `backup/pre-cleanup` — no borrar hasta verificar el push a GitHub

---

## 🔧 Comandos Útiles

```bash
# Configuración de SQX (instalación real, fuera del repo)
export SQX_INSTALL_PATH="$HOME/Proyectos/SQX_144_2953_linux_20260601"
export SQX_PORT=5050

# Tests completos (ambos árboles, con mock)
SQX_FORCE_MOCK=1 python -m pytest -q

# Sync de prompts (repo → live; --check sale 1 si hay drift)
python3 AI/opencode/sync_prompts.py --check

# KB seeder: ruta por defecto resuelta
python -c "from quantlab.knowledge.kb.seeder import DEFAULT_DOC_PATH; print(DEFAULT_DOC_PATH)"

# CLI
sdk/.venv/bin/python -m quantlab.cli api --help

# Ver estado
git status
git log --oneline -10
```
