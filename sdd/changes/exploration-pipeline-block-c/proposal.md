# Propuesta: Config Pipeline Block C — Pipeline de Configuración y Ejecución Completa

## Intent

Completar el loop cerrado de QuantLab: desde la decisión de exploración (`ExplorationDecision`) hasta la operación en vivo (live-ops), automatizando la configuración determinista del CustomProject SQX, su ejecución, monitoreo con alertas móviles, análisis de resultados, despliegue en JForex, comparación de backtests, y pool de live-ops.

## Problem

El Bloque B (ExplorationDecision) genera un artefacto de 13 campos, pero no existe pipeline que:
1. Convierta esa decisión en parámetros concretos por task de SQX (C2)
4. Ejecute el CustomProject en SQX con monitoreo y alertas móviles (C6)
5. Analice resultados y recomiende estrategias para JForex demo (C7)
7. Despliegue en JForex, corrija errores de compilación y guarde en KB (C8)
8. Compare backtest SQX vs JForex y analice discrepancias (C9)
9. Gestione pool de live-ops con Guardian (C10)

## Scope

### In Scope
- **C2**: `ParamMapper` determinista: `ExplorationDecision` → `dict[task_name, params]` usando `params_schema.py`
- **C3**: `ConfigBuilderStage` genera CFX listo para SQX
- **C4**: `ConfigReviewer` + gate `HUMAN_APPROVE_CONFIG`
- **C5**: `CampaignMonitor` arranque + verificación running
- **C6**: `CampaignMonitor` + `LLMGenerationMonitor` + `MobileNotifier` (ntfy/Telegram/webhook) + `VerdictClassifier` (dedup + quiet hours)
- **C7**: `AnalysisAgent` + `JForexDeployer` recomiendan estrategias demo con evidencia
- **C8**: `JForexDeployer` + `CompilerFixLoop` → KB write en fallos
- **C9**: `BacktestComparatorStage` compara SQX vs JForex + `BacktestAnalyzer` agent para discrepancias
- **C10**: `LiveOpsStage` con `LiveOpsPool` + `Guardian` para pool live-ops

### Out of Scope
- Descarga/instalación SQX/JForex (manual)
- Login JForex (I/O externo frágil)
- UI móvil nativa (solo notificaciones push/webhook)
- Cambios en SQX/JForex binarios

## Authorized Scope

- `sdk/quantlab/exploration/` (nuevos: `params_schema.py`, `param_mapper.py`, `backtest_comparator.py`)
- `sdk/quantlab/customproject/` (`param_mapper.py`, `template_selector.py` extendido)
- `sdk/quantlab/campaign/` (`monitor.py`, `llm_generation_monitor.py` extendidos)
- `sdk/quantlab/sqx/` (`campaign_monitor.py`, `llm_generation_monitor.py`, `mobile_notifier.py` nuevos)
- `sdk/quantlab/jforex/` (`strategy_bridge.py`, `exporter.py`, `live_feed.py` extendidos)
- `sdk/quantlab/pipeline/stages/` (`config_builder_stage.py`, `backtest_comparator_stage.py`, `jforex_deploy_stage.py`, `live_ops_stage.py` nuevos/extendidos)
- `sdk/quantlab/guardian/` (extendido para pool live-ops)
- `sdk/quantlab/pipeline/stages/` (`config_builder_stage.py`, `backtest_comparator_stage.py` nuevos)
- `ai/opencode/agents/` (nuevos: `config_builder.md`, `backtest_comparator.md`, `backtest_analyzer.md`)
- Tests: `sdk/tests/exploration/`, `sdk/tests/pipeline/`

## Acceptance Criteria

- [ ] C1: `TemplateSelector.select_project(state, params)` genera CustomProject válido
- [ ] C2: `ParamMapper.map(exploration_decision, template)` → `dict[task_name, dict[param, value]]` completo
- [ ] C3: `ConfigBuilderStage` ejecuta `ParamMapper` y genera CFX válido
- [ ] C4: `ConfigReviewer` valida + gate `HUMAN_APPROVE_CONFIG`
- [ ] C5: `CampaignMonitor` arranca + verifica running en <30s
- [ ] C6: `CampaignMonitor` + `LLMGenerationMonitor` + `MobileNotifier` (ntfy/Telegram/webhook) + `VerdictClassifier` (dedup + quiet hours)
- [ ] C7: `AnalysisAgent` + `JForexDeployer` recomiendan estrategias demo con evidencia
- [ ] C8: `JForexDeployer` + `CompilerFixLoop` + KB write en fallos
- [ ] C9: `BacktestComparatorStage` compara SQX vs JForex + `BacktestAnalyzer` agent para discrepancias
- [ ] C10: `LiveOpsStage` con `LiveOpsPool` + `Guardian` para pool live-ops

## Tasks

- [ ] T1: Crear `exploration/params_schema.py` (schema por task type)
- [ ] T2: Crear `exploration/param_mapper.py` (ExplorationDecision → dict[task, params])
- [ ] T3: Crear `customproject/param_mapper.py` (template-aware parameter mapping)
- [ ] T4: Crear `pipeline/stages/config_builder_stage.py`
- [ ] T5: Extender `CampaignMonitor` + `LLMGenerationMonitor` para C6
- [ ] T6: Crear `sqx/mobile_notifier.py` (webhook/ntfy/telegram) + `VerdictClassifier`
- [ ] T7: Crear `pipeline/stages/backtest_comparator_stage.py`
- [ ] T8: Crear `agents/backtest_analyzer.md` (sub-agente discrepancias)
- [ ] T9: Extender `JForexDeployStage` + `CompilerFixLoop` + KB write
- [ ] T10: Extender `LiveOpsStage` + `Guardian` para pool live-ops
- [ ] T11: Tests unitarios + integración
- [ ] T12: SDD docs (proposal/design/tasks/specs)

## Progress

- Created: 2026-01-15
- Status: T1-T11 completed, T12 in progress
- Active Task: T12 — SDD docs

## Rationale For Accepted Changes

Completa el loop cerrado QuantLab: Exploración → Configuración → Ejecución → Monitoreo → Resultados → Despliegue → Live-ops. Cada paso es determinista, auditable y auditable por humanos en gates críticos.

## Next Step

Completar SDD docs (proposal/design/tasks/specs) y mergear PRs stacked.