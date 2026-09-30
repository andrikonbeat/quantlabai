# Apply Progress: Guardian Control Loop

> Snapshot written at implementation close (ruta directa — SDD phase dispatch
> was latched after `sdd_task_result_empty`; user approved direct implementation).
> Phase status: **all tasks complete**, full-suite verification done, pending archive.

## Phase 2: Slice A — Structural (PR 1) ✅

| Task | Result |
|------|--------|
| 2.1 Orchestrator provider contract tests | ✅ `tests/guardian/test_provider_fail_closed.py` |
| 2.2 `validate_guardian_providers()` + `_NullDataProvider` removed | ✅ `sdk/quantlab/guardian/orchestrator.py` |
| 2.3 `_build_guardians` call sites require providers | ✅ `sdk/quantlab/pipeline/stages/agent_stages.py` (raises at line 452) |
| 2.4–2.5 BuilderStage `portfolio_state` gate | ✅ `_assert_portfolio_state_permits_build`, `tests/pipeline/test_portfolio_state_gate.py` |
| 2.6–2.7 `RiskConfigMapper` | ✅ `sdk/quantlab/cfx/risk_mapper.py`, `tests/cfx/test_risk_mapper.py` |
| 2.8 Focused verify | ✅ 37 guardian/cfx/pipeline tests + 5 stage_contract passed |

Key decisions:

- **Fail-closed at the stage, not silent degradation**: `GuardianEvaluationAgentStage` requires `portfolio_data_provider` and `strategy_performance_provider` in `ctx.config`; missing → `GuardianProviderError`. The legacy `_NullDataProvider` pass-through is gone.
- **`PortfolioStateBlockedError`** gates `BuilderStage` for `QUARANTINE`/`DEFENSIVE` — a blocked portfolio can never reach CFX dispatch without an explicit human override.
- **`RiskConfigMapper` bounds**: `max_portfolio_drawdown` (0, 1], `max_strategy_correlation` [0, 1], `max_single_strategy_weight` (0, 1], `kelly_fraction_cap` (0, 1], `var_confidence` [0, 1). CFX keys: `MaxPortfolioDrawdown@value`, `MaxStrategyCorrelation@value`, `MaxStrategyWeight@value`, `KellyFractionCap@value`, `VaRConfidence@value`.
- **Lockstep SDK fix**: the 4 `sdk/tests/test_guardian/test_guardian_agent.py` failures and 1 `tests/campaign/test_flow_segments.py` failure caused by Slice A were fixed by giving `execute_guardian_directive()` an optional `pipeline_config` param (injection of concrete providers) and updating the tests with a concrete provider stub. Re-run green.

## Phase 3: Slice B — Adaptive (PR 2) ✅

| Task | Result |
|------|--------|
| 3.1–3.3 `CorrectionBus` | ✅ `sdk/quantlab/guardian/correction_bus.py`, wired into `GuardianEvaluationStage.execute()` (optional `correction_bus` in ctx.config; stage-local default; `correction_events` artifact) |
| 3.4–3.5 `TemplateSelector` | ✅ `sdk/quantlab/customproject/templates.py` |
| 3.6–3.7 `GuardianFeedbackStore` | ✅ `sdk/quantlab/knowledge/guardian_store.py` (JSONL append-only under `knowledge/guardian-feedback/{campaign_id}/metrics.jsonl`) |
| 3.8 `query_guardian_metrics()` | ✅ `sdk/quantlab/knowledge/store.py` — sole addition; `STRUCTURED_SUB_LAYOUTS` untouched |
| 3.9 Orchestrator persistence | ✅ `MetaGuardianOrchestrator._persist_metrics()` — one `GuardianMetricRecord` per guardian result, opt-in, sink failure logged not thrown |
| 3.10 Focused verify | ✅ 174 guardian/customproject/knowledge tests passed |

Scope notes:

- `guardian-feedback/` directory init (task 1.3) is implemented via `KNOWLEDGE_DIRS` in `store.py` (existing convention); `health.py` does not exist. Per-campaign dir is created on first write.
- **Scope guardrail applied**: a delegated writer twice drifted into `crosschecks-full-parameter-catalog` PR3 territory (`project_builder.py` catalog code, `catalog.py`, `test_project_builder.py` additions, `test_crosschecks_catalog.py`, `test_project_builder_crosschecks.py`). All drift was reverted/deleted; the in-tree crosschecks PR2 files (`cfx/models.py`, `cfx/patcher.py`, their tests) were left untouched.

## Phase 4: Integration Verification ✅

- Full suite: `SQX_FORCE_MOCK=1 python3 -m pytest -q` → **3977 passed, 13 failed, 9 skipped**.
- The 13 failures are ALL pre-existing from other in-flight changes and NOT ours:
  - 4 × `tests/agents/test_research_agent_f1.py` — research-agent-enhancements
  - 8 × `tests/cfx/test_reader_crosschecks.py` + `tests/cfx/test_patcher.py` — crosschecks-full-parameter-catalog PR2 (in-tree)
  - 1 × `sdk/tests/test_knowledge.py::test_fresh_init_creates_all_structured_sub_layouts` — extra sub-layouts seeded by crosschecks PR1 (in-tree); `store.py` diff verified to only add `query_guardian_metrics`
- The 5 failures Slice A introduced were fixed and re-run green (see Slice A note).

## Risks

- `risk_mapper.py` imports private `_MIN_VERSION`/`_MAX_VERSION` from `quantlab.cfx.reader` — fragile if the reader refactors; acceptable for now, worth hardening later.
- **Pre-existing suite failures from parallel changes** must be reported in the archive report as out-of-scope noise, not regressions of this change.
- `CorrectionBus` is stage-local when no bus is injected — cross-phase sharing requires explicit wiring in `ctx.config`.

## Next Recommended

`sdd-archive` — sync delta specs and close the change (direct archive since SDD dispatch is latched this session).