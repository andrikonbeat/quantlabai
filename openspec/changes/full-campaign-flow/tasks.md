# Tasks: Full Campaign Flow

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 700–1000 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 Foundation → PR 2 Agents → PR 3 Monitor/Archive → PR 4 Wiring |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Work Units

| Unit | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|-----------|----------------------|-----------------|-------------------|
| 1 | PR 1 | `pytest tests/knowledge/test_knowledge_store_v5.py` | N/A — schema only | `git revert` |
| 2 | PR 2 | `pytest tests/agents/test_builder_agent_matrix.py tests/agents/test_research_agent_extensions.py` | `QUANTLAB_FORCE_MOCK=1` | `git revert` |
| 3 | PR 3 | `pytest tests/agents/test_execution_monitor.py tests/agents/test_archiver.py` | Mock SQX HTTP | `git revert` |
| 4 | PR 4 | `pytest tests/pipeline/test_full_campaign_flow.py` | Mock SQX e2e | `git revert` |

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Extend `sdk/quantlab/knowledge/store.py` `KNOWLEDGE_DIRS` with `campaign-phases`, `parameter-matrix`, `guardian-feedback`, `maintenance`; bump `_version` to `"5"`.
- [x] 1.2 Add Pydantic models in `sdk/quantlab/knowledge/models.py` for `PhaseEnvelope`, `ParameterMatrixEntry`, `FeedbackRecord`, `MaintenancePlan`.
- [x] 1.3 Modify `sdk/quantlab/customproject/generator.py` to embed `phase_type` and `checkpoint_metadata` in `CfxProject`.
- [x] 1.4 Create `tests/knowledge/test_knowledge_store_v5.py` — assert new dirs indexed, legacy readable, `_version == "5"`.

## Phase 2: Core Agents

- [x] 2.1 Extend `sdk/quantlab/agents/builder_agent.py` to generate `parameter_matrix.json`; write list to `ctx.artifacts["parameter_matrix"]`.
- [x] 2.2 Extend `sdk/quantlab/agents/builder_agent.py` unified handoff: append CFX path + phase type + checkpoint metadata to substrate dispatch.
- [x] 2.3 Extend `sdk/quantlab/agents/research_agent.py` for capital-aware reasoning (margin, leverage, cost profiles).
- [x] 2.4 Extend `sdk/quantlab/agents/research_agent.py` extended Knowledge Lake queries beyond Sharpe (regime, cost, drawdown, Guardian feedback).
- [x] 2.5 Create `tests/agents/test_builder_agent_matrix.py` `test_research_agent_extensions.py` — assert matrix entries and extended query results.

## Phase 3: Monitoring & Archive

- [x] 3.1 Create `sdk/quantlab/agents/execution_monitor.py` — `monitor()` with 30s polling, 2x stall detection, daemon-lost, checkpoint write, LLM diagnostics within 60s, HOLD on timeout.
- [x] 3.2 Create `sdk/quantlab/pipeline/stages/execution_monitor_stage.py` — `ExecutionMonitorStage` adapter.
- [x] 3.3 Create `sdk/quantlab/agents/archiver.py` — `archive()` writes maintenance plan, replacement runbook, account stats from Guardian + portfolio data.
- [x] 3.4 Create `sdk/quantlab/pipeline/stages/archiver_stage.py` — `ArchiverStage` adapter.
- [x] 3.5 Modify `sdk/quantlab/substrate/executor.py` to accept `ExecutionMonitor` callback; checkpoint before LLM invocation on stall.
- [x] 3.6 Create `tests/agents/test_execution_monitor.py` `test_archiver.py` — mock stall/DEGRADING, assert `HOLD` and replacement runbook.

## Phase 4: Pipeline Wiring, CLI & Live-ops

- [x] 4.1 Modify `sdk/quantlab/agents/research_director.py` `build_pipeline()` to add `demo`, `archive`, and post-archive `guardian_evaluate` stages.
- [x] 4.2 Modify `sdk/quantlab/pipeline/registry.py` to register `execution_monitor` and `archiver` stages.
- [x] 4.3 Modify `sdk/quantlab/agents/memory.py` `save_decision()` to capture new phase types and `parameter_matrix` metadata.
- [x] 4.4 Modify `sdk/quantlab/substrate/executor.py` `execute_chain()` to pass `ExecutionMonitor` callback and checkpoint metadata.
- [x] 4.5 Modify `sdk/quantlab/guardian/feedback.py` to wire live demo-account feed and parameter matrix delta into feedback record.
- [x] 4.6 Modify `sdk/quantlab/cli/campaign_commands.py` to expose full-campaign-flow entry points.
- [x] 4.7 Create `tests/pipeline/stages/test_execution_monitor_stage.py` `test_archiver_stage.py` — verify `requires`/`provides` match REQ-26.
- [x] 4.8 Create `tests/pipeline/test_full_campaign_flow.py` `test_stage_io_contracts.py` — assert 14 ordered phases, verify I/O keys.

## Remediation: Verify Report Critical Findings (8 items)

Addressed in focused remediation batch after verify-phase detected 8 critical findings.
Evidence revision: sha256:e48d7f7d309c2bc4a3a0fa46b6ecfdbc6b28bbef0be8e00afdf422dff01c26e7

| Finding | Status | What Was Done |
|---------|--------|---------------|
| 1. ParameterMatrixError + rationale validation | ✅ Fixed | `ParameterMatrixError` existed in `parameter_matrix.py`; fixed duplicate `get_tab_for_field` in `project_builder.py` that caused 7 tab-mapping test failures |
| 2. Optimizer/retester matrix generation | ✅ Verified | `generate_run_matrix()` implemented in `parameter_matrix.py`; `OptimizerStage`/`RetesterStage` call it; tests pass in `test_optimizer_retester_matrix.py` |
| 3. QUANTLAB_LEGACY_EXECUTION flag | ✅ Verified | `is_legacy_execution_enabled()` and `select_dispatch_backend()` implemented in `executor.py`; tests pass in `test_executor_legacy_flag.py` |
| 4. LiveOpsStage + registration | ✅ Verified | `LiveOpsStage` exists in `pipeline/stages/live_ops_stage.py` and is registered as `live_ops` in `registry.py`; tests pass in `test_live_ops_stage.py` |
| 5. Handoff failure preserves build artifact | ✅ Verified | `_persist_build_artifacts()` in `builder_agent.py` writes CFX + matrix before dispatch; test passes in `test_builder_agent_matrix.py` |
| 6. source="manual" override path | ✅ Verified | `generate_parameter_matrix()` produces `source="manual"` for justified overrides; test passes in `test_builder_agent_matrix.py` |
| 7. Failed phase envelope records error | ✅ Verified | `save_phase_envelope()` in `knowledge/store.py` records error, artifacts, and HOLD gate; tests pass in `test_knowledge_store_v5.py` |
| 8. Environment-gated e2e test for production daemon | ✅ Verified | `test_production_daemon_e2e.py` exists with `QUANTLAB_PRODUCTION_E2E=1` gate and skipif decorator |

### Remediation Test Command
```bash
.venv/bin/pytest tests/agents/test_builder_agent_matrix.py tests/substrate/test_executor_legacy_flag.py tests/substrate/test_production_daemon_e2e.py tests/pipeline/test_live_ops_stage.py tests/pipeline/test_optimizer_retester_matrix.py tests/knowledge/test_knowledge_store_v5.py::TestFailedPhaseEnvelope -q
```
Result: **20 passed** (2 skipped for environment-gated e2e)

### Regression Command
```bash
.venv/bin/pytest tests/pipeline/ tests/agents/test_execution_monitor.py tests/agents/test_archiver.py tests/substrate/ tests/guardian/test_feedback.py sdk/tests/test_memory_capture.py tests/knowledge/test_knowledge_store_v5.py tests/phase5/test_pipeline_registry.py tests/test_pr2_builder_agent.py -q
```
Result: **203 passed, 2 skipped** (no regressions)
