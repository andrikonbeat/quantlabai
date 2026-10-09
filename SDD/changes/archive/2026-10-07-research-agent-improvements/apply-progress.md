# Apply Progress: Research-Agent-Improvements

## State

**IMPLEMENTED + VERIFIED (2026-10-07)** — 12/12 tasks complete. F1 (1.1–1.4) and F2 (2.1–2.6)
were implemented and verified during the audit; F1-03 and F1-05 were completed (spec-level wiring
and LRU cache), and F3 (3.1–3.2) was implemented at close with strict TDD (RED → GREEN).

## Progress

| Area | Status | Evidence |
|------|--------|----------|
| F1: EconomicSenseValidator core | ✅ | `economic_sense/validator.py`; never-raises warnings contract |
| F1: TagCalibrator core | ✅ | `tag_calibrator.py`; LRU cache keyed by `frozenset(tags)` completed at close (F1-05) |
| F1: HypothesisConfig + wiring | ✅ | `dsl/models.py:374` `validation_warnings`; ResearchAgent.formulate_hypotheses wiring |
| F1: integration tests | ✅ | `tests/agents/test_economic_sense_validator.py`, `test_tag_calibrator.py`, `test_research_agent_f1.py` |
| **F1-03: validator in both modes** | ✅ COMPLETED | Wired into `RuleMode.build()` (rule.py) and `LLMMode.build()` (llm.py) directly; warnings attach non-blocking. 2 new tests (`TestEconomicSenseValidatorWiring`) |
| **F1-05: LRU frozenset cache** | ✅ COMPLETED | `functools.lru_cache` on `_compute_tag_stats_helper` keyed by `frozenset(tags)`; test proves hits and recomputation on tag-set change |
| F2: SQXDocProvider | ✅ | `knowledge/sqx_doc_provider.py` (12.8K); `_registry_key` normalization |
| F2: ParameterValidator | ✅ | `agents/parameter_validator.py`; ValidationResult(valid, errors) |
| F2: SemanticSimilarityQuery | ✅ | `knowledge/query.py:201` `search_similar_campaigns` |
| F2: RuleMode/LLMMode wiring | ✅ | rule.py:353,377 + llm.py:188 F2 wiring (validate overrides, drop invalid) |
| F2: LLMResearchAgent prompt | ✅ | `llm_research_agent.py` `_render_f2_ranges` (build_prompt:544) SQX parameter reference |
| F2: integration tests | ✅ | `test_doc_provider_docs.py`, `test_parameter_validator.py`, `test_semantic_similarity.py` |
| **F3: KnowledgeLakeFeedbackWriter** | ✅ COMPLETED | `agents/feedback_writer.py` (new); async `write_feedback()`, `auto_adjust=False` default |
| **F3: HypothesisFeedbackRecord** | ✅ COMPLETED | `knowledge/models.py` +30 (dataclass + `to_dict`) |
| **F3: tests** | ✅ COMPLETED | `tests/agents/test_feedback_writer.py` (new): temp Knowledge Lake append + read-only default |

## Verification Evidence

- `pytest sdk/tests/agents/test_hypothesis_builder.py sdk/tests/agents/test_tag_calibrator.py tests/agents/test_feedback_writer.py tests/agents/test_tag_calibrator.py tests/agents/test_economic_sense_validator.py tests/agents/test_research_agent_f1.py tests/agents/test_parameter_validator.py` — **122 passed**
- Regression: `pytest tests/agents/ tests/knowledge/ sdk/tests/agents/` — **615 passed, 0 failures**
- Full suite (prior baseline): 4100 passed / 51 pre-existing env failures (unchanged classification)

## Notes

- Reviewer anti-patterns from the delegated worker were corrected at close: `try/except Exception: pass`
  around a never-raising validator removed (rule.py, llm.py — bugs must propagate), redundant
  `asyncio.create_task` await removed (feedback_writer.py).
- The delegated worker initially destroyed `sdk/tests/agents/test_hypothesis_builder.py` (emptied to 31
  lines); restored from HEAD before finishing, then the missing F1-03 wiring tests were added inline.