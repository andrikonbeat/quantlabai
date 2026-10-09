# Tasks: Research Real Analysis Frame

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,800 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Market data normalization | PR 1 | `pytest sdk/tests/data/test_market.py -q` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk pytest sdk/tests/data/test_market.py -q` | Remove `sdk/quantlab/data/market/` |
| 2 | Technical context engine (ta) | PR 2 | `pytest sdk/tests/analysis/test_indicators.py -q` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk pytest sdk/tests/analysis/test_indicators.py -q` | Remove `sdk/quantlab/analysis/indicators.py` + revert `pyproject.toml` |
| 3 | Regime classifier | PR 3 | `pytest sdk/tests/analysis/test_regime.py -q` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk pytest sdk/tests/analysis/test_regime.py -q` | Remove `sdk/quantlab/analysis/regime.py` |
| 4 | Sentiment scorer + Frame model | PR 4 | `pytest sdk/tests/analysis/test_sentiment.py sdk/tests/analysis/test_frame.py -q` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk pytest ...` | Remove `sdk/quantlab/analysis/{sentiment,frame}.py` |
| 5 | MarketAnalysisStage + pipeline wiring | PR 5 | `pytest sdk/tests/pipeline/test_market_analysis_stage.py -q` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk pytest ...` | Remove `market_analysis_stage.py` + revert `agent_stages.py`, `registry.py` |
| 6 | AnalysisAgent extension + guardian hints + regression | PR 6 | `pytest sdk/tests/ -q --tb=short` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk pytest sdk/tests/ -q --tb=short` | Revert `analysis_agent.py`; hints remain in Frame |

## Phase 1: Foundation / Infrastructure

- [x] T-1.1 [WU1|PR1] RED: `tests/data/test_market.py` with Yahoo/Dukascopy normalization + partial-bar rejection; GREEN: `sdk/quantlab/data/market/__init__.py`, `models.py` (`Bar`, `MarketDataConfig`); AC: 6-field round-trip, empty→[], partial→skip
- [x] T-1.2 [WU1|PR1] GREEN: `sdk/quantlab/data/market/providers.py` with `MarketDataProvider`; AC: UTC timestamps, adjusted close mapped
- [x] T-1.3 [WU1|PR1] GREEN: register `market_data` provider in `registry.py`; AC: provider discoverable

## Phase 2: Core Implementation

 - [x] T-2.1 [WU2|PR2] RED: `tests/analysis/test_indicators.py` with selective computation + zone mapping + insufficient data; GREEN: `sdk/quantlab/analysis/__init__.py`, `indicators.py` (`IndicatorEngine`, `IndicatorResult`); AC: requested-only, zone enum, no exceptions
 - [x] T-2.2 [WU2|PR2] GREEN: add `ta>=0.11.0` to `sdk/pyproject.toml`; AC: version validated at init, clear error below minimum

- [x] T-3.1 [WU3|PR3] RED: `tests/analysis/test_regime.py` with trending/range/volatile/quiet + 3-bar smoothing + triggers; GREEN: `sdk/quantlab/analysis/regime.py` (`RegimeClassifier`); AC: confidence in [0,1], no flip-flops, triggers populated
- [x] T-3.2 [WU4|PR4] RED: `tests/analysis/test_sentiment.py` with bullish/bearish/neutral + empty input; GREEN: `sdk/quantlab/analysis/sentiment.py` (`SentimentScorer`); AC: score in [-1,1], rationale non-empty when score≠0
- [x] T-3.3 [WU4|PR4] RED: `tests/analysis/test_frame.py` with JSON round-trip + schema version + partial frame; GREEN: `sdk/quantlab/analysis/frame.py` (`Frame`, `to_json`, `from_json`); AC: lossless round-trip, schema_version immutable

## Phase 3: Integration / Wiring

- [x] T-4.1 [WU5|PR5] RED: `tests/pipeline/test_market_analysis_stage.py` with happy path + missing input + graceful degradation; GREEN: add `MarketAnalysisStage` ABC to `agent_stages.py`; AC: registered between StatisticsStage and ReviewStage
- [x] T-4.2 [WU5|PR5] GREEN: `sdk/quantlab/pipeline/stages/market_analysis_stage.py` concrete stage; AC: writes `market_analysis` + `frame` artifacts
- [x] T-4.3 [WU5|PR5] GREEN: register `market_analysis` in `registry.py`; AC: stage instantiable by name

## Phase 4: Testing / Verification

- [x] T-5.1 [WU6|PR6] RED: `tests/agents/test_analysis_agent_frame.py` with Frame consumption; GREEN: extend `analysis_agent.py` to read Frame additively; AC: no behavior change when Frame absent
- [x] T-5.2 [WU6|PR6] GREEN: extend `Frame.guardian_hints` with regime/sentiment/volatility expansion; AC: hints dict JSON-serializable
- [x] T-5.3 [WU6|PR6] GREEN: full regression `pytest sdk/tests/ -q --tb=short`; AC: all green, coverage maintained

## Phase 5: Cleanup / Documentation

- [x] T-6.1 [WU6|PR6] GREEN: verify `sdk/quantlab/market/__init__.py` and `sdk/quantlab/analysis/__init__.py` exports; AC: public API discoverable
- [x] T-6.2 [WU6|PR6] GREEN: add `tests/contract/test_ta_version.py`; AC: init fails below `ta>=0.11.0`
- [x] T-6.3 [WU6|PR6] GREEN: verify Frame JSON schema stable for SDD 5; AC: schema_version="1.0" round-trips cleanly

## TDD Cycle Evidence

| Task | RED (failing test) | GREEN (impl) | REFACTOR |
|------|-------------------|--------------|----------|
| T-1.1/1.2/1.3 | `test_market.py` normalization + rejection | `models.py`, `providers.py`, registry | Extract shared bar validation |
| T-2.1/2.2 | `test_indicators.py` selective + zones + version | `indicators.py` ta wrapper | Extract zone mapping helper |
| T-3.1 | `test_regime.py` smoothing + triggers | `regime.py` classifier | Extract ADX/DMI signal helper |
| T-3.2 | `test_sentiment.py` rule-based scoring | `sentiment.py` scorer | N/A |
| T-3.3 | `test_frame.py` round-trip + schema | `frame.py` model + hints | N/A |
| T-4.1/4.2/4.3 | `test_market_analysis_stage.py` integration | `agent_stages.py`, `market_analysis_stage.py`, registry | Extract engine factory |
| T-5.1/5.2/5.3 | `test_analysis_agent_frame.py` + contract | `analysis_agent.py` + guardian_hints + regression | N/A |
