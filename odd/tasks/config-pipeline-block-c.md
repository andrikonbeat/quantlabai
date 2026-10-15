# ODD Task Document: config-pipeline-block-c

## Objective

Implement the complete configuration pipeline (Bloque C) that takes the ExplorationDecision artifact from Bloque B and drives the full SQX CustomProject lifecycle: template selection → parameter configuration → SQX execution → monitoring → results analysis → JForex deployment → backtest comparison → live-ops pool.

## Problem

Bloque A (instalador) y Bloque B (exploración) ya están implementados. Falta el pipeline de configuración y ejecución completo que conecta la decisión de exploración con la ejecución real en SQX, el monitoreo, la compilación en JForex, el backtest comparativo, y el pool de live-ops.

El usuario describe 10 pasos en el spec original (C1–C10) con dudas específicas en:
- C2: Mapeo determinista de parámetros por task (no existe schema por task)
- C6: Estado del custom project en ejecución + monitoreo móvil + clasificación de veredictos
- C9: Comparación backtest JForex vs SQX (no existe)

## Why

Para cerrar el loop completo: Exploración → Configuración → Ejecución → Monitoreo → Resultados → JForex → Live-ops, sin intervención manual en pasos intermedios.

## Scope

### In Scope
1. **C1**: CustomProject template selection + default task sequence (ya existe `TemplateSelector`)
2. **C2**: Schema de parámetros por task (NUEVO: `exploration/params_schema.py` + `ParamMapper`)
3. **C3**: Configuración del CustomProject via `ParamMapper` + sub-agente `config_builder`
4. **C4**: Revisión con evidencias + `ConfigReviewer` (ya existe) + gate humano
5. **C5**: Arranque + verificación running (extender `CampaignMonitor`)
5. **C6**: Monitoreo estado + alertas móviles + clasificación veredictos (extender `CampaignMonitor` + `LLMGenerationMonitor` + NUEVO `MobileNotifier`)
6. **C7**: Análisis resultados + recomendaciones JForex demo (extender `AnalysisAgent` + `JForexDeployer`)
7. **C8**: Selección usuario → carpeta JForex → compilación + fix loop + KB (extender `JForexDeployer` + `CompilerFixLoop`)
7. **C9**: Backtest comparativo JForex vs SQX (NUEVO `BacktestComparator`)
8. **C9b**: Discrepancias → sub-agente análisis + notificación usuario
9. **C10**: Pool live-ops + monitoreo continuo (extender `LiveOpsStage` + `Guardian`)

### Out of Scope
- Descarga/instalación SQX/JForex (manual)
- Login JForex (I/O externo frágil)
- UI móvil nativa (solo notificaciones push/webhook)
- Cambios en SQX/JForex binarios

## Authorized Scope

- `sdk/quantlab/exploration/` (nuevos: `params_schema.py`, `param_mapper.py`, `backtest_comparator.py`)
- `sdk/quantlab/customproject/` (`param_mapper.py`, `template_selector.py` extendido)
- `sdk/quantlab/campaign/` (`monitor.py`, `llm_generation_monitor.py` extendidos)
- `sdk/quantlab/sqx/` (`campaign_monitor.py`, `llm_generation_monitor.py` extendidos)
- `sdk/quantlab/jforex/` (`strategy_bridge.py`, `exporter.py`, `live_feed.py` extendidos)
- `sdk/quantlab/pipeline/stages/` (`config_builder_stage.py`, `backtest_comparator_stage.py` nuevos)
- `sdk/quantlab/pipeline/stages/` (`mobile_notifier.py` nuevo)
- `sdk/quantlab/guardian/` (extendido para pool live-ops)
- `ai/opencode/agents/` (nuevos: `config_builder.md`, `backtest_comparator.md`)

## Acceptance Criteria

- [ ] C1: `TemplateSelector.select_project(state, params)` genera CustomProject válido
- [ ] C2: `ParamMapper.map(exploration_decision, template)` → dict[task_name, dict[param, value]] completo
- [ ] C3: `ConfigBuilderStage` ejecuta `ParamMapper` y genera CFX válido
- [ ] C4: `ConfigReviewer` valida + gate humano `HUMAN_APPROVE_CONFIG`
- [ ] C5: `CampaignMonitor` arranca + verifica running en <30s
- [ ] C6: `CampaignMonitor` + `LLMGenerationMonitor` + `MobileNotifier` (webhook/ntfy/telegram)
- [ ] C6b: Clasificación veredictos (dedup + quiet hours) evita spam móvil
- [ ] C7: `AnalysisAgent` + `JForexDeployer` recomiendan estrategias demo con evidencia
- [ ] C8: `JForexDeployer` + `CompilerFixLoop` + KB write
- [ ] C9: `BacktestComparator` compara SQX vs JForex + threshold de similitud
- [ ] C9b: Discrepancias → sub-agente `BacktestAnalyzer` + notificación usuario
- [ ] C10: `LiveOpsStage` + `Guardian` pool live-ops + monitoreo continuo

## Tasks

- [ ] T1: Crear `exploration/params_schema.py` (schema por task type)
- [ ] T2: Crear `exploration/param_mapper.py` (ExplorationDecision → dict[task, params])
- [ ] T3: Crear `customproject/param_mapper.py` (template-aware parameter mapping)
- [ ] T4: Crear `pipeline/stages/config_builder_stage.py` (ejecuta ParamMapper → CFX)
- [ ] T5: Extender `CampaignMonitor` + `LLMGenerationMonitor` para C6
- [ ] T6: Crear `mobile_notifier.py` (webhook/ntfy/telegram) + clasificación veredictos
- [ ] T7: Crear `pipeline/stages/backtest_comparator_stage.py` (SQX vs JForex)
- [ ] T8: Crear `agents/backtest_analyzer.md` (sub-agente discrepancias)
- [ ] T9: Crear `pipeline/stages/backtest_comparator_stage.py` + `BacktestAnalyzer` agent
- [ ] T10: Extender `JForexDeployer` + `CompilerFixLoop` + KB write
- [ ] T11: Extender `LiveOpsStage` + `Guardian` para pool live-ops
- [ ] T12: Tests unitarios + integración
- [ ] T13: SDD docs (proposal/design/tasks/specs)

## Progress

- Created: 2026-01-15
- Status: planning
- Active Task: T1

## Rationale For Accepted Changes

Nueva arquitectura de configuración determinista que conecta ExplorationDecision → CustomProject params → SQX execution → JForex deploy → live-ops.

## Next Step

Begin T1: Create `exploration/params_schema.py` with per-task-type parameter schemas.