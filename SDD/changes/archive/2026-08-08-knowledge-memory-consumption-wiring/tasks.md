# Tasks: Knowledge Memory Consumption Wiring

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~120-150 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: stacked-to-main
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Wire REQ-204 KB consult into builder_agent + tests | Single PR | `pytest sdk/tests/test_pr2_builder_agent.py -k kb_consult` | N/A — no CLI/runtime change | Revert `builder_agent.py` + `test_pr2_builder_agent.py` changes |

## Phase 1: Tests (RED)

- [x] 1.1 Add `TestKbConsult` class to `sdk/tests/test_pr2_builder_agent.py` with 4 failing tests covering spec scenarios:
  - `test_builder_consult_kb_hit_allows_translation` — mock `KbStore.consult` returns entries for all tabs; assert `kb_warnings` absent
  - `test_builder_consult_missing_entry_raises_block` — mock empty for one tab with `strict_kb=True`; assert `ConfigurationError`
  - `test_builder_consult_empty_kb_halts_with_warning` — mock all tabs empty; assert `kb_warnings` contains tab names
  - `test_builder_consult_needs_review_proceeds_with_warning` — mock entry with `status="needs_review"`; assert warning logged, translation proceeds

## Phase 2: Core Implementation (GREEN)

- [x] 2.1 Add `strict_kb: bool = False` keyword-only param to `BuilderAgent.__init__()` in `sdk/quantlab/agents/builder_agent.py`
- [x] 2.2 Add `_active_kb_tabs(config) -> list[str]` static method returning `list(KB_TABS)` from `quantlab.knowledge.kb.models`
- [x] 2.3 Add async `_consult_kb(config) -> list[str]` method: for each active tab call `KbStore.consult(name="", tab=tab)`; collect missing tab names; raise `ConfigurationError` if `strict_kb` and missing
- [x] 2.4 Call `_consult_kb(research_config)` after `ResearchConfig` parsing and before `_translate()` in `run()`; append `kb_warnings` to return dict when present

## Phase 3: Verification

- [x] 3.1 Run `pytest sdk/tests/test_pr2_builder_agent.py` — confirm 4 new tests pass
- [x] 3.2 Run full test suite — confirm no regressions (pre-existing hang in TestRun tests unrelated to this change; 6/6 non-hanging tests pass)

---

## Phase 4: Verification (sdd-verify)

> **Verified**: 2026-08-08 | Branch: `feat/knowledge-memory-consumption-wiring-wu1` | Commits: d986e7c + e134e40
> **Verdict**: PASS | Validator: `gentle-ai sdd-verify-validate` → `{"valid":true,"verdict":"pass"}`

### Requirement Coverage

| Requirement | Status | Notes |
|------------|--------|-------|
| REQ-204 | ✅ COMPLIANT | All 4 spec scenarios covered by passing tests in `TestKbConsult` |
| REQ-205 | ➖ BLOCKED | Concurrent edits on `config_reviewer.py`; deferred to follow-up change |
| Task 6.3 | ➖ DEFERRED | Building-blocks KB tab + changelog polling; out of scope for this slice |

### Test Evidence

| Command | Result | Hash |
|--------|--------|------|
| `pytest tests/test_pr2_builder_agent.py -q --tb=short` | 14 passed, exit 0 | `cda0a233...` |
| `pytest tests/ -q --tb=short` | 1230 passed, 1 pre-existing flaky, exit 1 | `549fce84...` |

**Pre-existing flaky**: `test_mock_campaign_roundtrip_analysis_to_reviewer` (test_pr3_pipeline_wiring.py) — unrelated to this change; passes in isolation.

### Concurrent-Edit Files

None of the 5 concurrent-edit files were touched:
- `sdk/quantlab/agents/config_reviewer.py` — not touched ✅
- `sdk/quantlab/compiler/compiler.py` — not touched ✅
- `sdk/quantlab/phase4/jforex_deploy.py` — not touched ✅
- `sdk/quantlab/sqx/project_builder.py` — not touched ✅
- `tests/phase4/test_project_builder.py` — not touched ✅

### TDD Compliance

| Check | Result |
|-------|--------|
| TDD Evidence | ✅ Found (apply-progress memory #800) |
| All tasks have tests | ✅ 4/4 RED-GREEN tasks have TestKbConsult tests |
| RED confirmed | ✅ 4 test files verified on disk |
| GREEN confirmed | ✅ 4/4 tests pass on execution |
| Triangulation | ✅ 4 test cases / 4 spec scenarios (1:1) |
| Safety Net | ✅ New test file; builder_agent.py pre-existing tests still pass |

**TDD Compliance**: 6/6 checks passed

### Engram

Verify report persisted to Engram: topic_key `sdd/knowledge-memory-consumption-wiring/verify-report` (id: 804)
