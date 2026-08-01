# Design: Results Analysis Stage

## Technical Approach

Insert a deterministic `AnalysisStage` between statistics and review. Mirror the existing stats pattern: pure library (`quantlab.analysis`) + thin pipeline agent (`AnalysisAgent`). The agent resolves `strategies.csv` from `export_paths`, parses it via a new `STRATEGY_COLUMNS` reader (alias-mapped like `TRADE_COLUMNS`), computes per-strategy metrics reusing `StatsResult`, applies threshold-based overfit heuristics, and selects strategies. Artifacts `strategy_analysis`, `strategy_verdicts`, `selected_strategies`, `wf_cycles` feed ReviewStage and PortfolioStage, closing the review data gap. Graceful degradation: missing/unparseable CSV never hard-fails the pipeline.

## Architecture

```
sdk/quantlab/analysis/
├── models.py      # StrategyAnalysis, SelectionResult
├── reader.py      # AnalysisReader — path resolution + databank delegate
├── engine.py      # AnalysisEngine — metrics + overfit heuristics
└── selection.py   # SelectionEngine — scoring + verdicts + selection
sdk/quantlab/agents/analysis_agent.py          # AnalysisAgent(AnalysisStage)
```

- `readers/databank.py`: `STRATEGY_COLUMNS` + `read_strategies()` → `list[StrategySummary]` (model added to `readers/models.py`).
- `AnalysisStage` ABC in `pipeline/stages/agent_stages.py`: `requires=["export_paths","statistics"]`, `provides=["strategy_analysis","selected_strategies","strategy_verdicts","wf_cycles"]`.
- Registry: `"analysis" → AnalysisAgent`; `agent_names` set updated.
- `research_director.build_pipeline` and `builder_agent.generate_pipeline_config`: insert analysis between statistics and review; remove `selected_strategies` from `EXTERNAL_INPUTS` (analysis now provides it).
- `ReviewStage.requires` += `strategy_analysis`; ReviewerAgent reads `strategy_analysis`/`wf_cycles` (already reads `wf_cycles`; extraction shape kept compatible).
- Thresholds: new `AnalysisConfig` on `ResearchConfig` (`dsl/models.py`), read from `research_config` artifact with defaults fallback.
- Mock server: emit `strategies.csv` alongside trades/equity.

## Data Flow

```
builder ──export_paths──▶ AnalysisAgent ──resolve strategies.csv──▶ AnalysisReader.parse
  └─▶ DatabankCSVReader.read_strategies ──▶ list[StrategySummary]
        └─▶ AnalysisEngine.analyze ──▶ list[StrategyAnalysis]  (metrics=StatsResult, flags, score)
              └─▶ SelectionEngine.select ──▶ SelectionResult
                    ├─ strategy_analysis ──▶ ReviewStage (overfit flags)
                    ├─ strategy_verdicts   ──▶ context
                    ├─ wf_cycles           ──▶ ReviewerAgent.check_wf_overfitting
                    └─ selected_strategies ──▶ PortfolioStage
```

## Architecture Decisions

| # | Decision | Options | Tradeoffs | Chosen |
|---|----------|---------|-----------|--------|
| 1 | Reader location | (a) `readers/databank.py` (b) inside `analysis/` | (b) duplicates TRADE_COLUMNS pattern, violates `result-reader` delta; (a) mirrors existing parser, one alias-mapping home | (a) — `STRATEGY_COLUMNS` + `read_strategies`; `AnalysisReader` is a thin export-path wrapper |
| 2 | StatsResult reuse | (a) map parsed columns into `StatsResult` fields + derive MAR/recovery via `StatisticsEngine` statics (b) re-run `compute_all()` per strategy (c) new metrics schema | (b) needs per-strategy trades/equity — out of scope; (c) duplicates schema; (a) honest reuse: fields are Optional, absent → None | (a) — `StatsResult` is the per-strategy metrics container |
| 3 | Heuristic location | (a) `AnalysisEngine` (pure lib) (b) in ReviewerAgent (c) in agent | (b) reviewer is campaign-level, spec needs per-strategy; (c) untestable; (a) deterministic, unit-testable, mirrors engine pattern | (a) — `engine.py` returns flags; agent only persists |
| 4 | Selection scoring | (a) pure threshold pass/fail (b) weighted composite score + thresholds | (a) spec scenario 8/30 is threshold-only, but requirement says "score each strategy"; (b) deterministic bounded score orders ACCEPT list for portfolio | (b) — composite score for ordering; verdicts remain threshold-gated (ACCEPT/REJECT; ITERATE reserved for LLM layer) |
| 5 | Stage contract shape | (a) `provides` incl. `wf_cycles` (b) wf data inside `strategy_analysis` | (a) reviewer reads `wf_cycles` artifact today — zero reviewer extraction changes; (b) forces reviewer rework | (a) — plus `requires=["statistics"]` for cross-check context |
| 6 | Graceful degradation | (a) warn + empty artifacts (b) raise | (b) kills portfolio/review on one bad file; (a) matches reviewer NO_DATA fallback | (a) — `ParseError`/missing file → warning + empty artifacts; stage never raises |
| 7 | Mock format | (a) alias-form column names (b) canonical names | (a) exercises alias mapping end-to-end (spec: "Alias mapping"); (b) hides drift risk | (a) — e.g. `Profit Factor`, `Sharpe Ratio`, `Trades` |

## Interfaces

```python
STRATEGY_COLUMNS = {  # readers/databank.py
    "strategy_name": ["Name", "Strategy", "StrategyName"],
    "profit_factor": ["Profit Factor", "PF", "ProfitFactor"],
    "sharpe_ratio": ["Sharpe Ratio", "Sharpe", "SharpeRatio"],
    "win_rate": ["Win Rate", "WinRate", "Win %"],
    "total_trades": ["Trades", "Total Trades", "TradesCount"],
    "max_drawdown": ["Max DD", "MaxDrawdown", "Max Drawdown"],
    "mc_p10": ["MC p10", "MC P10", "Monte Carlo p10"],
    "wf_is_sharpe": ["WF IS Sharpe", "IS Sharpe"],
    "wf_oos_sharpe": ["WF OOS Sharpe", "OOS Sharpe"],
    "wf_cycles": ["WF Cycles", "WF_Cycles"],
}

class AnalysisReader:   # analysis/reader.py
    def parse(self, path: str | Path) -> list[StrategySummary]  # delegates; raises ParseError on corrupt CSV

class AnalysisEngine:   # analysis/engine.py
    def analyze(self, strategies, thresholds) -> list[StrategyAnalysis]
        # metrics: StatsResult (absent columns → None)
        # derived: mar_ratio/recovery_factor via StatisticsEngine statics
        # heuristics (deterministic): extreme PF/Sharpe below min_trades;
        #   mc_p10 < 0; wf_oos/wf_is ratio < oos_is_threshold

class SelectionEngine:  # analysis/selection.py
    def select(self, analyses, thresholds) -> SelectionResult
        # verdict: ACCEPT (no flags), REJECT (any flag); score = bounded
        #   weighted sum; selected = ACCEPT names ordered by score desc

# agent_stages.py
class AnalysisStage(Stage):
    name = "analysis"
    requires = ["export_paths", "statistics"]
    provides = ["strategy_analysis", "selected_strategies", "strategy_verdicts", "wf_cycles"]
```

## Error Handling Chain

1. No `strategies.csv` in `export_paths` → warning; empty artifacts.
2. `read_strategies` raises `ParseError` (corrupt CSV) → caught in agent; warning; empty artifacts.
3. Bad cell values → `_safe_float`/`_safe_int` → `None` → metric `None`, heuristic skipped (data-gated).
4. Heuristics only trigger on present data — no exception path.
5. `wf_cycles` absent → `[]`; reviewer keeps `needs_review`/NO_DATA fallback (empty list is falsy).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `STRATEGY_COLUMNS` alias resolution, unknown-column tolerance, `None` on absent | `tests/test_readers.py` additions, fixture CSV |
| Unit | Heuristics: extreme PF + 5 trades → flag; mc_p10 breach; WF ratio 0.5 < 0.7; config overrides | `tests/test_analysis_engine.py` |
| Unit | Selection: 8/30 ACCEPT, empty-selection warning, score ordering | `tests/test_analysis_selection.py` |
| Integration | Agent run: missing/unparseable CSV → empty artifacts, pipeline continues | `tests/test_analysis_agent.py` |
| Integration | Contract: order statistics→analysis→review→portfolio; registry lookup; ReviewStage.requires | `test_pipeline_contracts.py` + `test_pipeline_agent_stages.py` |
| E2E | Mock round-trip: campaign → strategies.csv → analysis → review wf check on real data | `test_pr3_pipeline_wiring.py` / mock server test |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. CSV parsing is a data-format boundary (tolerant alias parser + `ParseError` + graceful degradation), and `export_paths` file IO mirrors the existing statistics stage — no new boundary.

## Migration / Rollout

No data migration. Rollback = revert wiring (registry, `research_director`, `generate_pipeline_config`) → statistics→review restored; analysis module stays inert; graceful degradation prevents silent breakage.

## Open Questions

- [ ] Real `strategies.csv` sample still unavailable (proposal CRITICAL risk) — fixture approximates; tolerant parser is the mitigation. Validate `mc_p10`/WF column shapes on first real export.
- [ ] Keep `ctx.artifacts.setdefault("selected_strategies", [])` in `research_director` as defensive default alongside removing it from `EXTERNAL_INPUTS`? (Suggested: yes, harmless for analysis-less pipelines.)
