# Tasks: Results Analysis Stage

## Review Workload Forecast

Estimated: 1300–1800 lines → 4 chained PRs below.

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

1. **Strategies reader** → PR 1. Test: `pytest sdk/tests/test_readers.py -q`. Harness: N/A — pure lib. Rollback: revert databank.py + models.py.
2. **Analysis library (models, engine, selection)** → PR 2. Test: `pytest sdk/tests/test_analysis_engine.py sdk/tests/test_analysis_selection.py -q`. Harness: N/A — pure lib. Rollback: revert analysis/ — inert.
3. **Agent + stage + wiring + AnalysisConfig** → PR 3. Test: `pytest sdk/tests/test_analysis_agent.py sdk/tests/test_pipeline_contracts.py sdk/tests/test_pipeline_agent_stages.py sdk/tests/test_pr2_research_director.py sdk/tests/test_pr2_builder_agent.py -q`. Harness: ResearchDirector + mock campaign. Rollback: revert wiring → statistics→review.
4. **Reviewer + mock strategies.csv + E2E** → PR 4. Test: `pytest sdk/tests/test_pr3_reviewer_agent.py sdk/tests/test_pr3_pipeline_wiring.py -q`. Harness: MockSQXServer campaign. Rollback: revert reviewer → NO_DATA fallback.

## Phase 1: Reader

- [x] 1.1 Add `StrategySummary` to `sdk/quantlab/readers/models.py` — strategy_name, PF, Sharpe, win_rate, trades, max_drawdown, mc_p10, wf_is/oos_sharpe, wf_cycles (all Optional)
- [x] 1.2 Add `STRATEGY_COLUMNS` + `read_strategies()` to `sdk/quantlab/readers/databank.py` (`_find_column`/`_safe_*`; unknown cols ignored; absent → None)
- [x] 1.3 Add fixture `sdk/tests/fixtures/strategies.csv` (alias-form + extra cols)
- [x] 1.4 Tests test_readers.py: alias "Profit Factor"→profit_factor; unknown cols tolerated; absent → None; corrupt → ParseError

## Phase 2: Analysis library

- [x] 2.1 Create `sdk/quantlab/analysis/__init__.py` + `models.py`: `StrategyAnalysis` (name, metrics: StatsResult, flags, score); `SelectionResult` (analyses, verdicts, selected, warnings)
- [x] 2.2 Create `sdk/quantlab/analysis/reader.py`: `AnalysisReader.parse(path)` → `list[StrategySummary]`
- [x] 2.3 Create `sdk/quantlab/analysis/engine.py`: metrics via `StatsResult` + `StatisticsEngine` statics; heuristics: PF/Sharpe extremes vs `min_trades`, `mc_p10 < 0`, OOS/IS < `oos_is_threshold` (data-gated)
- [x] 2.4 Create `sdk/quantlab/analysis/selection.py`: ACCEPT (no flags)/REJECT (any flag); weighted score; selected desc; empty-selection warning
- [x] 2.5 Tests test_analysis_engine.py: PF 5.0/5 trades flagged; mc_p10 breach; WF 0.5 < 0.7; overrides; absent cols → None
- [x] 2.6 Tests test_analysis_selection.py: 8/30 ACCEPT, 22 REJECT; ordering; empty warning

## Phase 3: Agent + stage contract + wiring

- [x] 3.1 agent_stages.py: add `AnalysisStage` (name "analysis"; requires export_paths+statistics; provides strategy_analysis/selected_strategies/strategy_verdicts/wf_cycles); add `strategy_analysis` to `ReviewStage.requires`
- [x] 3.2 Create `sdk/quantlab/agents/analysis_agent.py` — mirror StatisticsAgent: resolve strategies.csv → parse → analyze → select → artifacts; missing/corrupt → warning + empty (never raises); thresholds from `research_config.analysis`
- [x] 3.3 sdk/quantlab/pipeline/registry.py: import AnalysisAgent; map `"analysis"`; add to `agent_names`
- [x] 3.4 dsl/models.py: add `AnalysisConfig` (min_trades, extreme_pf/sharpe, oos_is_threshold, weights); `analysis` field on `ResearchConfig`
- [x] 3.5 research_director.py: insert analysis stage between statistics and review; drop `selected_strategies` from `EXTERNAL_INPUTS`; keep `setdefault`
- [x] 3.6 builder_agent.py: insert analysis stage between statistics and review in `generate_pipeline_config`
- [x] 3.7 Update test_pr2_research_director.py (12→13 stages) + test_pr2_builder_agent.py counts
- [x] 3.8 Tests: AnalysisStage I/O, registry lookup, ReviewStage.requires, chain (test_pipeline_contracts.py, test_pipeline_agent_stages.py); new test_analysis_agent.py (missing/unparseable → empty; full run)

## Phase 4: Reviewer + mock + E2E

- [x] 4.1 reviewer_agent.py run(): consume `strategy_analysis`/`wf_cycles` when present; keep NO_DATA fallback
- [x] 4.2 mock_sqx_server.py `_generate_mock_exports`: emit `strategies.csv` — multi-row, alias-form cols ("Profit Factor", "Trades", …)
- [x] 4.3 Tests test_pr3_reviewer_agent.py: WF computed from wf_cycles; NO_DATA fallback preserved
- [x] 4.4 E2E test_pr3_pipeline_wiring.py: round-trip — strategies.csv → analysis → review WF on real data → selected_strategies → portfolio
