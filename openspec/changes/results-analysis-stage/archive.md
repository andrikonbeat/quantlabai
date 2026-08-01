# Archive: Results Analysis Stage

**Status**: archived
**Date**: 2026-07-31
**Mode**: SDD (auto) — explore → propose → spec → design → tasks → apply (4 chained slices) → verify → archive

## Summary

Added a deterministic `AnalysisStage` between statistics and review that parses the strategies databank export (`strategies.csv`), computes per-strategy metrics, applies overfit heuristics, selects strategies worth keeping (`selected_strategies`), and closes ReviewerAgent's data gaps (wf_cycles, benchmark data). The pipeline previously jumped from statistics to review with no judgment about which strategies to keep.

## What Was Built

- **`quantlab.analysis` module** (`sdk/quantlab/analysis/`): models.py (StrategyAnalysis, SelectionResult), reader.py (AnalysisReader), engine.py (AnalysisEngine with 3 deterministic heuristics), selection.py (SelectionEngine with ACCEPT/REJECT verdicts + weighted score)
- **Reader** (`sdk/quantlab/readers/databank.py`): STRATEGY_COLUMNS alias map + read_strategies() — tolerant parser, unknown columns ignored
- **Agent** (`sdk/quantlab/agents/analysis_agent.py`): AnalysisStage implementation mirroring StatisticsAgent; missing/corrupt CSV → warning + empty artifacts + continue
- **Stage contract** (`agent_stages.py`): AnalysisStage (requires export_paths+statistics; provides strategy_analysis/selected_strategies/strategy_verdicts/wf_cycles); ReviewStage.requires += strategy_analysis
- **Registry** (`registry.py`): "analysis" → AnalysisAgent registered
- **Wiring** (`research_director.py` + `builder_agent.py`): analysis inserted between statistics and review; selected_strategies removed from EXTERNAL_INPUTS
- **DSL** (`dsl/models.py`): AnalysisConfig on ResearchConfig (min_trades, extreme_pf/sharpe, oos_is_threshold, score_weights)
- **Reviewer** (`reviewer_agent.py`): consumes strategy_analysis/wf_cycles; NO_DATA fallback preserved
- **Mock** (`mock_sqx_server.py`): emits realistic strategies.csv with alias-form columns

## Files Changed

| File | Action |
|------|--------|
| `sdk/quantlab/analysis/__init__.py` | Created |
| `sdk/quantlab/analysis/models.py` | Created |
| `sdk/quantlab/analysis/reader.py` | Created |
| `sdk/quantlab/analysis/engine.py` | Created |
| `sdk/quantlab/analysis/selection.py` | Created |
| `sdk/quantlab/readers/models.py` | Modified |
| `sdk/quantlab/readers/databank.py` | Modified |
| `sdk/quantlab/agents/analysis_agent.py` | Created |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modified |
| `sdk/quantlab/pipeline/registry.py` | Modified |
| `sdk/quantlab/agents/research_director.py` | Modified |
| `sdk/quantlab/agents/builder_agent.py` | Modified |
| `sdk/quantlab/dsl/models.py` | Modified |
| `sdk/quantlab/agents/reviewer_agent.py` | Modified |
| `sdk/quantlab/sqx/mock_sqx_server.py` | Modified |
| `sdk/tests/test_readers.py` | Modified |
| `sdk/tests/test_analysis_engine.py` | Created |
| `sdk/tests/test_analysis_selection.py` | Created |
| `sdk/tests/test_analysis_agent.py` | Created |
| `sdk/tests/test_pipeline_contracts.py` | Modified |
| `sdk/tests/test_pipeline_agent_stages.py` | Modified |
| `sdk/tests/test_pr2_research_director.py` | Modified |
| `sdk/tests/test_pr2_builder_agent.py` | Modified |
| `sdk/tests/test_pr3_reviewer_agent.py` | Modified |
| `sdk/tests/test_mock_sqx_server.py` | Created |
| `tests/test_pr3_pipeline_wiring.py` | Modified |

## Verification

- 134/134 focused tests pass (reader + analysis + pipeline + reviewer + mock + wiring)
- 10/10 spec requirements compliant
- 19/19 scenarios covered by passing tests
- All acceptance criteria met
- Pre-existing daemon-hang tests excluded (unrelated to this change)

## Key Decisions

1. Pure library + thin agent pattern (mirrors stats/engine.py → StatisticsAgent)
2. Reader in readers/databank.py (single alias-mapping home)
3. StatsResult reuse with Optional fields (absent columns → None)
4. Heuristics in AnalysisEngine (deterministic, unit-testable)
5. Weighted composite score + threshold-gated ACCEPT/REJECT
6. Graceful degradation: missing/unparseable CSV → warning + empty artifacts + continue
7. Mock emits alias-form columns (exercises alias mapping end-to-end)

## Known Limitations

- strategies.csv real format unverified — tolerant parser is the mitigation; mock format approximates
- LLM verdict layer deferred (follow-up, mirroring LLMGenerationMonitor pattern)
- Per-strategy trades/equity not exported from SQX (may not be feasible)
- Phase-4 path parity deferred (separate statistics implementation)

## Next Steps

Pipeline pieces remaining per full-flow gap analysis:
- Reconfiguration loop (reconfigure and relaunch based on results)
