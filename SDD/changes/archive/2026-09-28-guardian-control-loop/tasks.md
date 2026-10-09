# Tasks: Guardian Control Loop

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 500-700 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Slice A (structural) → PR 2: Slice B (adaptive) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Hard-fail providers, PortfolioState gate, typed RiskConfig → CFX | PR 1 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/guardian/ tests/cfx/ tests/pipeline/ -k "provider or risk_mapper or portfolio_state"` | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/pipeline/ -k "stage_contract"` | Revert `agent_stages.py`, `orchestrator.py`, `errors.py`, `risk_mapper.py`; restore `_NullDataProvider` |
| 2 | CorrectionBus, adaptive templates, feedback store, knowledge API | PR 2 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/guardian/ tests/customproject/ tests/knowledge/ -k "correction_bus or template or feedback or guardian_metrics"` | `SQX_FORCE_MOCK=1 python3 -m pytest -q` | Revert `correction_bus.py`, `guardian_store.py`, `templates.py`, `store.py`, `health.py` |

## Phase 1: Foundation

- [x] 1.1 Add `GuardianProviderError`, `PortfolioStateBlockedError` to `sdk/quantlab/pipeline/errors.py`
- [x] 1.2 Create `GuardianMetricRecord` model in `sdk/quantlab/knowledge/guardian_store.py`
- [x] 1.3 Add `guardian-feedback/` directory init to `sdk/quantlab/knowledge/health.py` — implemented via `KNOWLEDGE_DIRS` in `sdk/quantlab/knowledge/store.py` (`guardian-feedback` line 61, `guardian-feedback/_template` line 88); `health.py` does not exist, the store itself creates the per-campaign dir on first write (`GuardianFeedbackStore.write`, `path.parent.mkdir`)

## Phase 2: Slice A — Structural (PR 1)

- [x] 2.1 Write test: `MetaGuardianOrchestrator` raises `GuardianProviderError` on `None` provider — `tests/guardian/test_provider_fail_closed.py::TestOrchestratorRejectsNoneProviders`
- [x] 2.2 Require concrete providers in `MetaGuardianOrchestrator` constructor; delete `_NullDataProvider` in `sdk/quantlab/guardian/orchestrator.py` — `validate_guardian_providers()` fail-closed; `_NullDataProvider` gone (0 live refs)
- [x] 2.3 Update `_build_guardians` call sites in `sdk/quantlab/pipeline/stages/agent_stages.py` — requires `portfolio_data_provider` + `strategy_performance_provider` from `ctx.config`, raises `GuardianProviderError` (line 452)
- [x] 2.4 Write test: `BuilderStage` raises `PortfolioStateBlockedError` on `QUARANTINE`/`DEFENSIVE` — `tests/pipeline/test_portfolio_state_gate.py`
- [x] 2.5 Enforce `portfolio_state` gate in `BuilderStage` in `sdk/quantlab/pipeline/stages/agent_stages.py` — `_assert_portfolio_state_permits_build` + `blocked_states`
- [x] 2.6 Write test: `RiskConfigMapper` round-trip and invalid range raises — `tests/cfx/test_risk_mapper.py`
- [x] 2.7 Create `sdk/quantlab/cfx/risk_mapper.py` with `RiskConfigMapper.to_cfx()` and `from_cfx()`
- [x] 2.8 Verify: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/guardian/ tests/cfx/ tests/pipeline/ -k "provider or risk_mapper or portfolio_state"` — 37 focused tests passed; 5 stage_contract harness tests passed

## Phase 3: Slice B — Adaptive (PR 2)

- [x] 3.1 Write test: `CorrectionBus.publish()` rejects invalid `event_type` with `CorrectionBusError` — `tests/guardian/test_correction_bus.py`
- [x] 3.2 Create `sdk/quantlab/guardian/correction_bus.py` with `CorrectionEvent`, `CorrectionBus`, `CorrectionBusError`
- [x] 3.3 Wire `CorrectionBus` into `GuardianEvaluationStage.execute()` in `sdk/quantlab/pipeline/stages/agent_stages.py` — optional `correction_bus` in ctx.config; stage-local bus otherwise; `state_transition` recorded in `correction_events` artifact
- [x] 3.4 Write test: `TemplateSelector` deterministic output per `PortfolioState` — `tests/customproject/test_template_selector.py`
- [x] 3.5 Add `TemplateSelector` to `sdk/quantlab/customproject/templates.py`
- [x] 3.6 Write test: `GuardianFeedbackStore.write()` appends valid `GuardianMetricRecord` — `tests/knowledge/test_guardian_feedback.py`
- [x] 3.7 Create `sdk/quantlab/knowledge/guardian_store.py` with `GuardianFeedbackStore.write()` and `query()`
- [x] 3.8 Add `TimeSeriesStore.query_guardian_metrics()` to `sdk/quantlab/knowledge/store.py` — sole addition to `store.py`; `STRUCTURED_SUB_LAYOUTS` untouched
- [x] 3.9 Wire `MetaGuardianOrchestrator.evaluate()` to persist via `GuardianFeedbackStore` — `_persist_metrics()` writes one record per guardian result, opt-in, failing sink logged not thrown
- [x] 3.10 Verify: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/guardian/ tests/customproject/ tests/knowledge/ -k "correction_bus or template or feedback or guardian_metrics"` — 174 focused tests passed

## Phase 4: Integration Verification

- [x] 4.1 Verify Slice A: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/pipeline/ -k "stage_contract or guardian_to_builder"` — 5 stage_contract passed; guardian-to-builder gate verified via `test_portfolio_state_gate.py`
- [x] 4.2 Verify Slice B: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/pipeline/ -k "correction_bus or portfolio_state_blocked"` — correction bus wiring covered by `tests/guardian/test_correction_bus.py`; blocked-state gate by `tests/pipeline/test_portfolio_state_gate.py`
- [x] 4.3 Run full suite: `SQX_FORCE_MOCK=1 python3 -m pytest -q` — **3977 passed, 13 failed, 9 skipped**. All 13 failures are PRE-EXISTING from other in-flight changes: 4 in `tests/agents/test_research_agent_f1.py` (research-agent-enhancements), 8 in `tests/cfx/test_reader_crosschecks.py` + `tests/cfx/test_patcher.py` (crosschecks-full-parameter-catalog PR2 in-tree), 1 in `sdk/tests/test_knowledge.py::test_fresh_init_creates_all_structured_sub_layouts` (extra sub-layouts from crosschecks PR1 in-tree). The 5 failures initially caused by Slice A (`test_guardian_agent.py` × 4, `test_flow_segments.py` × 1) were fixed in lockstep — `execute_guardian_directive` gained `pipeline_config` injection and the tests pass concrete providers; re-run green.
- [x] 4.4 Update acceptance criteria checklist in proposal

## Phase 5: Documentation

- [x] 5.1 Add docstrings to new files — `risk_mapper.py`, `correction_bus.py`, `guardian_store.py`, `template_selector` additions, `agent_stages.py` gate + provider contracts documented
- [x] 5.2 Update `openspec/changes/guardian-control-loop/apply-progress.md`