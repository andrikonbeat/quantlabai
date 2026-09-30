# Tasks: research-agent-improvements

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,100 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: F1 core + tests → PR 2: F2 core + tests → PR 3: F3 feedback |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

## Phase 1 (F1) — Quick Wins

- [x] 1.1 T-001 EconomicSenseValidator core — Create `sdk/quantlab/agents/economic_sense/validator.py`. Range checks for RSI(2-200), BB(0.1-5.0), SMA/EMA(2-500), ATR(2-200), MACD fast/slow(2-200), signal(2-100). Coherence: warn if BB/SMA ratio >3× or <0.33×, or MACD fast≥slow. Returns warnings list; never raises.
- [x] 1.2 T-002 TagCalibrator core — Create `sdk/quantlab/agents/tag_calibrator.py`. LRU cache by frozenset(tags). Confidence = base × percentile(tag_mean_sharpe, global_dist) clamped [0.1, 1.0]. Bayesian smoothing for n<5.
- [x] 1.3 T-010 HypothesisConfig + F1 wiring — Add `validation_warnings: list[str]` to HypothesisConfig in `sdk/quantlab/dsl/models.py`. Wire validator and calibrator into `ResearchAgent.formulate_hypotheses()`.
- [x] 1.4 T-003 F1 integration tests — Parametrized tests for valid/invalid params and coherence. Mocked KnowledgeStore for TagCalibrator. End-to-end ResearchAgent asserts warnings attached and confidence adjusted.

## Phase 2 (F2) — Enrichment

- [ ] 2.1 T-004 SQXDocProvider core — Create `sdk/quantlab/knowledge/sqX_doc_provider.py`. Reads YAML from `structured/sqx-kb/{ver}/parameters/{tab}/{param}.yaml`. Falls back to `_BUILD_CONFIG_MAP` with warning. Version isolation enforced.
- [ ] 2.2 T-005 ParameterValidator — Create `sdk/quantlab/agents/parameter_validator.py`. Delegates to SQXDocProvider. Returns ValidationResult(valid, errors). Blocks unknown indicators, out-of-range values, type mismatches.
- [ ] 2.3 T-006 SemanticSimilarityQuery — Extend `sdk/quantlab/knowledge/query.py` with `search_similar_campaigns(text, top_k=10)`. Uses sentence-transformers when available; token+char 3-gram cosine fallback.
- [ ] 2.4 T-011 RuleMode + LLMMode F2 wiring — In `hypothesis_builder/rule.py`, validate overrides before defaults. In `hypothesis_builder/llm.py`, validate parsed JSON and drop invalid hypotheses.
- [ ] 2.5 T-012 LLMResearchAgent prompt wiring — Inject SQX Reference section into `build_prompt()`. Validate parsed responses against SQXDocProvider in `parse_response()`.
- [ ] 2.6 T-007 F2 integration tests — SQXDocProvider with temp YAML + fallback. ParameterValidator blocking invalid sets. SemanticSimilarityQuery with/without embeddings.

## Phase 3 (F3) — Closed Loop

- [ ] 3.1 T-008 KnowledgeLakeFeedbackWriter — Create `sdk/quantlab/agents/feedback_writer.py` and add `HypothesisFeedbackRecord` to `sdk/quantlab/knowledge/models.py`. Async `write_feedback()` appends to `structured/{campaign_id}/metadata.yaml` under `feedback:`. `auto_adjust` defaults to False.
- [ ] 3.2 T-009 F3 integration tests — Async write path with temporary Knowledge Lake. Verify metadata.yaml append. Confirm read-only mode default blocks auto-adjust.

## Execution Order

1. T-001 (EconomicSenseValidator)
2. T-002 (TagCalibrator)
3. T-004 (SQXDocProvider)
4. T-006 (SemanticSimilarityQuery)
5. T-010 (HypothesisConfig + F1 wiring)
6. T-003 (F1 tests) — after T-001, T-002, T-010
7. T-005 (ParameterValidator) — after T-004
8. T-011 (RuleMode + LLMMode wiring) — after T-005, T-006
9. T-012 (LLMResearchAgent wiring) — after T-004, T-005
10. T-007 (F2 tests) — after T-005, T-006, T-011, T-012
11. T-008 (FeedbackWriter)
12. T-009 (F3 tests) — after T-008

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | F1 validators + calibrator + wiring + tests | PR 1 | `pytest tests/agents/test_economic_sense_validator.py tests/agents/test_tag_calibrator.py tests/agents/test_research_agent_f1.py -x` | N/A — pure unit/integration, no live broker or SQX dependency | Revert `sdk/quantlab/agents/economic_sense/`, `sdk/quantlab/agents/tag_calibrator.py`, and model/wiring changes without affecting F2/F3 |
| 2 | F2 doc provider + validator + semantic query + wiring + tests | PR 2 | `pytest tests/knowledge/test_sqx_doc_provider.py tests/agents/test_parameter_validator.py tests/knowledge/test_semantic_similarity.py -x` | N/A — pure unit/integration, temp YAML files and monkeypatched fallbacks | Revert `sdk/quantlab/knowledge/sqX_doc_provider.py`, `sdk/quantlab/agents/parameter_validator.py`, and query.py additions without affecting F1/F3 |
| 3 | F3 feedback writer + tests | PR 3 | `pytest tests/agents/test_feedback_writer.py -x` | N/A — async test with temporary Knowledge Lake directory | Revert `sdk/quantlab/agents/feedback_writer.py` and `HypothesisFeedbackRecord` model addition without affecting F1/F2 |

## Review Workload Forecast (summary)

- Estimated changed lines: ~1,100
- Chained PRs recommended: Yes
- 400-line budget risk: High
- Delivery strategy: ask-on-risk
- Decision needed before apply: Yes
- Suggested work-unit PR split: PR 1: F1 Quick Wins → PR 2: F2 Enrichment → PR 3: F3 Closed Loop

### Next Step

Ask the user to confirm chain strategy (stacked-to-main vs feature-branch-chain vs size:exception) before sdd-apply.
