# Tasks: Reconfiguration Loop

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~200 lines |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Core loop + unit tests | PR 1 | `pytest sdk/tests/phase5/test_reconfiguration_loop.py -k unit` | Mocked BuildConfig + reviewer | Revert `research_director.py` and `builder_agent.py`; versioned dirs are additive |
| 2 | Integration + E2E tests | PR 2 | `pytest sdk/tests/phase5/test_reconfiguration_loop.py -k "integration or e2e"` | Mock SQX server for E2E | Same revert boundary |

> **Archive reconciliation note (2026-07-31)**: All checkboxes below were marked complete at
> archive time. The persisted tasks artifact had never been updated by `sdd-apply` (verify-report
> warning #4). The verify report (`sdd/reconfiguration-loop/verify-report`, Engram #685) proves
> every task implemented: 16/16 tests pass (8 unit + 7 integration + 1 E2E), compileall exit 0,
> source-verified. Task 3.2 text corrected per verify-report warning #1 (project_builder.py gained
> +12 spec-required lines).

## Phase 1: Core Implementation

- [x] 1.1 Add `apply_iteration_proposal()` to `sdk/quantlab/agents/research_director.py`: map known `parameter_changes` keys to `BuildConfig` fields; warn/skip unknown keys; return unchanged config on empty input
- [x] 1.2 Branch `execute_campaign()` on `review_decision`: ITERATE → apply proposal + versioned rebuild; REJECT → abort; APPROVE → exit loop to portfolio
- [x] 1.3 Implement versioned campaign IDs (`f"{base_id}_iter{iteration:02d}"`) and inject into `PipelineContext.config["campaign_id"]`
- [x] 1.4 Add best-result tracking (`selected_strategies` count with aggregate fallback) and degradation abort (2 consecutive worse) to `execute_campaign()`
- [x] 1.5 Modify `sdk/quantlab/agents/builder_agent.py` to read versioned `campaign_id` from `context.config` before UUID generation and use it for project directory dispatch

## Phase 2: Testing

- [x] 2.1 Create `sdk/tests/phase5/test_reconfiguration_loop.py` with unit tests for `apply_iteration_proposal()`: known mappings, unknown keys skipped with warning, empty input returns unchanged
- [x] 2.2 Integration test: ITERATE branch — mock reviewer returns ITERATE + `parameter_changes`; assert versioned build launched with mutated BuildConfig
- [x] 2.3 Integration test: REJECT branch — mock reviewer returns REJECT; assert `state=FAILED` and loop aborts
- [x] 2.4 Integration test: APPROVE branch — mock reviewer returns APPROVE; assert loop exits and `state=COMPLETED`
- [x] 2.5 Integration test: degradation abort — run loop with alternating worse/better results; assert abort after 2 consecutive worse, best result returned
- [x] 2.6 Integration test: `auto_iterate=False` — single iteration executes; no reconfiguration regardless of review_decision
- [x] 2.7 E2E test: full loop with mock SQX; execute 2-iteration loop; assert versioned campaign IDs propagate through context (`{base_id}_iter00`, `{base_id}_iter01`)

## Phase 3: Verification

- [x] 3.1 Run `pytest sdk/tests/phase5/test_reconfiguration_loop.py` and confirm all tests pass
- [x] 3.2 Verify `sdk/quantlab/dsl/models.py` remains unchanged and confirm the delta to `sdk/quantlab/sqx/project_builder.py` is limited to the spec-required `BuildConfig.generations`/`population` fields and `_BUILD_CONFIG_MAP` entries (+12 lines)
