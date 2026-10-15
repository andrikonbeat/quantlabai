# Tasks: Config Pipeline Block C

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 3500+ |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Unit A (params_schema + param_mapper) → Unit B (config_builder) → Unit C (mobile_notifier) → Unit D (backtest_comparator + backtest_analyzer) → Unit E (jforex_deploy + fixloop) → Unit F (live_ops + guardian) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes

## Tasks

### Phase 1: Core Schema & Mapping (Foundation)

- [x] T1: Create `exploration/params_schema.py` (schema por task type)
  - 14 task types, 54 params para Build
  - ParamSpec, ParamType, ParamConstraint, TaskType
  - Helper functions: get_task_schema, validate_task_params, coerce_params

- [x] T2: Create `exploration/param_mapper.py` (ExplorationDecision → task params)
  - 37 mapping rules
  - Transform registry (capital_to_risk_usd, capital_to_max_lot, etc.)
  - ParamMapper class with map() method

- [x] T3: Create `customproject/param_mapper.py` (template-aware)
  - CustomProjectParamMapper class
  - TemplateSelector integration
  - guardian_state persistence

- [x] T4: Create `pipeline/stages/config_builder_stage.py`
  - ConfigBuilderStage (Stage ABC)
  - ConfigBuilderConfig
  - TemplateParams building from ExplorationDecision
  - CFX generation via generate_cfx_archive()

### Phase 2: Mobile Notifications & Monitoring (C6)

- [x] T5: Extender CampaignMonitor + LLMGenerationMonitor para C6
  - _fanout_notify → NotificationManager
  - VerdictClassifier integration

- [x] T6: Crear `sqx/mobile_notifier.py`
  - BaseNotifier (ABC) + NtfyNotifier, TelegramNotifier, WebhookNotifier, PushoverNotifier
  - NotificationManager (dedup, quiet hours, severity filter)
  - VerdictClassifier (dedup window, quiet hours, severity threshold)
  - setup_mobile_notifications() convenience function

- [x] T5b: Extender CampaignMonitor._fanout_notify → NotificationManager
- [x] T5c: Extender LLMGenerationMonitor → VerdictClassifier integration

### Phase 3: Backtest Comparison & Analysis (C9)

- [x] T7: Crear `pipeline/stages/backtest_comparator_stage.py`
  - BacktestComparatorStage
  - BacktestComparatorConfig (thresholds configurables)
  - Pearson correlation, PnL diff, DD diff, Sharpe diff
  - Discrepancy detection + auto_analyze_discrepancy flag

- [x] T8: Crear `agents/backtest_analyzer.md`
  - Discrepancy Classification Taxonomy (4 tipos)
  - Analysis Protocol (4 pasos)
  - Output format JSON
  - Configuration YAML

### Phase 4: JForex Deployment + Compiler Fix Loop (C8)

- [x] T9: Extender JForexDeployStage + CompilerFixLoop + KB write
  - JForexDeployStage._write_to_kb() → KnowledgeStore.write()
  - Error info: strategy_id, jfx_path, error, timestamp, type
  - CompilerFixLoop: KB write por iteración (compiler_fixloop category)

### Phase 4: Live-Ops Pool + Guardian (C10)

- [x] T10: Extender LiveOpsStage + Guardian para pool live-ops
  - LiveCandidate dataclass
  - LiveOpsPool (add/remove/update/retire)
  - LiveOpsStage con pool integrado
  - Guardian evaluate_live() pool-aware

### Phase 5: Testing & Documentation

- [x] T11: Tests unitarios + integración Bloque C
  - sdk/tests/exploration/ (35 tests)
  - sdk/tests/pipeline/test_config_builder_stage.py
  - sdk/tests/pipeline/test_backtest_comparator_stage.py
  - sdk/tests/exploration/test_*.py

- [ ] T12: SDD docs (proposal/design/tasks/specs)
  - proposal.md ✓
  - design.md (este archivo)
  - tasks.md (este archivo)
  - specs/ (por componente)
  - apply-progress.md
  - verify-report.md

## Acceptance Criteria Checklist

### C1: Template Selection
- [x] TemplateSelector.select_project() genera CustomProject válido

### C2: ParamMapper
- [x] ParamMapper.map() → dict[task_name, dict[param, value]] completo
- [x] 37 reglas de mapeo cubren todos los 13 campos de ExplorationDecision
- [x] Transform registry para capital→risk, capital→max_lot, timeframe→wf_cycles

### C3: ConfigBuilderStage
- [x] ConfigBuilderStage ejecuta ParamMapper y genera CFX válido
- [x] TemplateParams building desde ExplorationDecision

### C4: ConfigReviewer + HUMAN_APPROVE_CONFIG
- [ ] ConfigReviewer valida (existente)
- [ ] Gate HUMAN_APPROVE_CONFIG bloquea si no aprobado

### C5: CampaignMonitor arranque
- [ ] CampaignMonitor arranca + verifica running en <30s
- [ ] LLMGenerationMonitor integrado

### C6: Mobile Notifications
- [x] MobileNotifier (ntfy/Telegram/webhook/Pushover)
- [x] NotificationManager (dedup window, quiet hours, severity filter)
- [x] VerdictClassifier (dedup window, quiet hours, severity threshold)
- [x] attach_mobile_notifier() para CampaignMonitor + LLMGenerationMonitor

### C7: AnalysisAgent + JForexDeployer
- [ ] AnalysisAgent recomienda estrategias demo con evidencia
- [ ] JForexDeployer despliega estrategias seleccionadas

### C8: JForexDeployer + CompilerFixLoop + KB
- [x] JForexDeployer._write_to_kb() → KnowledgeStore.write()
- [ ] CompilerFixLoop KB write por iteración (compiler_fixloop category)

### C9: BacktestComparator + BacktestAnalyzer
- [x] BacktestComparatorStage (correlation, PnL diff, DD diff, Sharpe diff)
- [x] BacktestAnalyzer agent (4 tipos discrepancia, protocolo 4 pasos)
- [ ] Thresholds configurables en BacktestComparatorConfig

### C10: LiveOpsPool + Guardian
- [x] LiveCandidate, LiveOpsPool, LiveOpsStage
- [ ] Guardian.evaluate_live() pool-aware

## Progress

- Created: 2026-01-15
- Status: Implementation complete, docs in progress
- Next: Complete SDD docs (T12)

## Rationale For Accepted Changes

Completa el loop cerrado QuantLab: Exploración → Configuración → Ejecución → Monitoreo → Resultados → Despliegue → Live-ops. Cada paso es determinista, auditable y auditable por humanos en gates críticos.

## Next Step

Completar SDD docs (proposal/design/tasks/specs) y mergear PRs stacked.