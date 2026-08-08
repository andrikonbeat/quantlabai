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
