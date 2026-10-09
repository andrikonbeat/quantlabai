# Proposal: Research Real Analysis Frame

## Intent

Add a perception-layer stage that enriches campaign execution with live market context (technical zones, regime, sentiment) and produces a serializable Frame model. This context feeds Research hypothesis filtering and primes the future guardian-orchestrator (SDD 5). It complements—not replaces—AnalysisAgent and ReviewerAgent.

## Scope

### In Scope
- Market data normalization (Dukascopy/Yahoo OHLCV bars)
- Technical context engine (`ta` wrapper returning zones, not signals)
- Regime classifier (trending/range/volatile/quiet + confidence)
- Sentiment scorer (news → bullish/bearish/neutral)
- Frame model (Pydantic aggregator)
- Pipeline integration (new `MarketAnalysisStage` between `StatisticsStage` and `ReviewStage`)
- Guardian-ready serialization

### Out of Scope
- Signal generation / entry-exit logic
- Modifications to `AnalysisAgent` or `ReviewerAgent`
- Manual indicator implementations
- Live broker feed integration beyond bar normalization

## Capabilities

> This section is the CONTRACT between proposal and specs phases.

### New Capabilities
- `market-frame`: Pydantic Frame model aggregating technical context, regime, sentiment, and metadata
- `technical-context-engine`: `ta`-based wrapper returning contextual zones (overbought/oversold, trending/range, volatility buckets)
- `regime-classifier`: Rule-based classifier producing trending/range/volatile/quiet + confidence
- `sentiment-scorer`: News-to-sentiment pipeline (bullish/bearish/neutral score from news items)
- `market-data-normalizer`: OHLCV bar normalization from Dukascopy/Yahoo providers

### Modified Capabilities
- `pipeline-core`: Add `MarketAnalysisStage` I/O contract between `StatisticsStage` and `ReviewStage`

## Approach

Introduce a new `MarketAnalysisStage` that runs after `StatisticsStage`. It pulls normalized OHLCV bars from existing data providers, computes technical context via a thin `ta` wrapper, classifies regime, scores sentiment from cached news, and aggregates everything into a `Frame` model stored in pipeline context. Frame is serializable (JSON + Pydantic) so SDD 5 can consume it without coupling.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modified | Add `MarketAnalysisStage` ABC between `StatisticsStage` and `ReviewStage` |
| `sdk/quantlab/market/` | New | Frame model, engines, classifier, scorer |
| `sdk/quantlab/data/market/` | New | OHLCV normalizers for Dukascopy/Yahoo |
| `openspec/specs/pipeline-core/spec.md` | Modified | Delta spec for new stage contract |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `ta` version drift breaks wrapper | Med | Pin `ta` in requirements; add compatibility test in CI |
| Free data providers have gaps | Med | Graceful fallback to cached bars; schema validates partial data |
| LLM cost for sentiment scoring | Low | Rule-based scorer first; LLM as optional enhancer in later PR |
| Regime false signals in choppy markets | Med | Require confidence threshold; expose fallback to UNKNOWN |
| Frame ownership conflicts with SDD 5 | Low | Stable JSON schema; versioned serialization contract |

## Rollback Plan

Revert `MarketAnalysisStage` registration and remove new packages. AnalysisAgent/ReviewerAgent remain untouched. Frame artifacts are additive; removing them does not affect existing pipeline outputs.

## Dependencies

- `ta` library (Technical Analysis Library, pure Python)
- Existing Dukascopy/Yahoo provider interfaces
- Existing `NewsItem` model (already has optional sentiment field)

## Success Criteria

- [ ] All new engines have unit tests with `pytest` and `SQX_FORCE_MOCK=1 PYTHONPATH=sdk`
- [ ] Pipeline integration test: stage runs between Statistics and Review without side effects
- [ ] Frame serializes/deserializes with Pydantic v2; schema version included
- [ ] Indicator-free: zero manual RSI/MACD/BB/SMA/EMA/ATR implementations in new code
- [ ] Performance: 1 year H1 bars processed in <2s on CI runner
