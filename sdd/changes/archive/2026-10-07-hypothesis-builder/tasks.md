# Tasks: Hypothesis Builder

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 650–950 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Rule) → PR 2 (LLM) → PR 3 (Stage) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Rule mode + validator | PR 1 | `pytest tests/unit/agents/test_hypothesis_builder.py -x -k "rule"` | `pytest tests/unit/agents/ -x` | Revert `hypothesis_builder.py` only |
| 2 | LLM mode + fallback | PR 2 | `pytest tests/unit/agents/test_hypothesis_builder.py -x -k "llm"` | `pytest tests/unit/agents/ -x` | Revert LLM-only additions |
| 3 | Stage + pipeline wiring | PR 3 | `pytest tests/integration/ -x -k "hypothesis_builder"` | `pytest tests/integration/pipeline/ -x` | Revert `agent_stages.py`, `registry.py` changes |

## PR 1: Rule Mode Engine + Validator

### RED tests
- [x] 1.1 RED: parametrized test each RB-4 keyword → expected BuildingBlock set
- [x] 1.2 RED: test `_validate_blocks()` rejects unknown indicator, missing params, dupes, dangling refs
- [x] 1.3 RED: test `HypothesisBuilder` facade dispatches to RuleMode

### GREEN implementation
- [x] 1.4 Create `sdk/quantlab/agents/hypothesis_builder/rule.py`: `RuleMode` with `_KEYWORD_MAP` + `build()`
  (Deviation: package structure instead of single file — see summary)
- [x] 1.5 Add `BuildingBlockValidator` in `sdk/quantlab/agents/hypothesis_builder/validate.py` with all RB-5 checks
- [x] 1.6 Implement `HypothesisBuilder` facade in `sdk/quantlab/agents/hypothesis_builder/__init__.py` with Strategy dispatch

### REFACTOR
- [x] 1.7 Clean up types, imports, docstrings, edge cases

## PR 2: LLM Mode + Fallback

### RED tests
- [x] 2.1 RED: test `LLMMode._build_prompt()` includes rationale, sources, JSON schema
- [x] 2.2 RED: test `LLMMode._parse_response()` returns valid BuildingBlock/Strategy
- [x] 2.3 RED: test fallback chain (RB-6): mock LLM throws → Rule returns valid
- [x] 2.4 RED: test S-1 LLM mode with detailed rationale (AsyncMock instead of respx)

### GREEN implementation
- [x] 2.5 Add `LLMMode` with `_build_prompt()`, `_parse_response()`, reuse `call_llm()`
- [x] 2.6 Wire fallback in `HypothesisBuilder.build()`: log warning → Rule retry
- [x] 2.7 Support per-call `mode` override on `build()`

### REFACTOR
- [x] 2.8 Clean up error handling, logging, edge cases

## PR 3: Stage + Pipeline Wiring

### RED tests
- [ ] 3.1 RED: test `StageRegistry.get_stage_class("hypothesis_builder")` returns class
- [ ] 3.2 RED: test `build_pipeline()` inserts stage between research and builder
- [ ] 3.3 RED: integration test S-9 context contract (requires/provides)
- [ ] 3.4 RED: integration test S-4 to S-6 full round-trip: hypothesis → blocks → validate

### GREEN implementation
- [ ] 3.5 Add `HypothesisBuilderStage` in `sdk/quantlab/pipeline/stages/agent_stages.py`
- [ ] 3.6 Register `"hypothesis_builder"` in `sdk/quantlab/pipeline/registry.py` with inner wrapper
- [ ] 3.7 Insert stage in `build_pipeline()` / `generate_pipeline_config()` after research

### REFACTOR
- [ ] 3.8 Clean up: verify all existing pipeline tests pass unchanged
