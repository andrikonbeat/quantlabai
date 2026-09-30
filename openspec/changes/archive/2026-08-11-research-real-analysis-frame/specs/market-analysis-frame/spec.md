# Delta for market-analysis-frame

## ADDED Requirements

### Requirement: REQ-301 MarketDataProvider normalizes OHLCV bars

The system MUST normalize OHLCV bars from Dukascopy/Yahoo into a common `Bar` model with timestamp, open, high, low, close, volume.

#### Scenario: Dukascopy normalization
- GIVEN raw Dukascopy OHLCV feed
- WHEN normalized
- THEN `Bar(timestamp, open, high, low, close, volume)` with UTC timestamps

#### Scenario: Yahoo normalization
- GIVEN raw Yahoo OHLCV feed
- WHEN normalized
- THEN matches same `Bar` schema with adjusted close mapped

#### Scenario: Partial bar rejection
- GIVEN bar missing high field
- WHEN normalization runs
- THEN incomplete bar is skipped; no exception raised

**Acceptance**: Round-trip preserves all 6 fields.  
**Error**: Returns empty list when input is empty or all bars invalid.

### Requirement: REQ-302 IndicatorEngine wraps ta library

The system MUST wrap `ta`; compute RSI, MACD, Bollinger Bands, SMA, EMA, ATR on `list[Bar]`; return typed `IndicatorResult` with values + zones. No entry/exit signals.

#### Scenario: Compute requested indicators
- GIVEN 50 Bars
- WHEN RSI(14) and MACD(12,26,9) requested
- THEN `IndicatorResult` includes `indicator_name`, `value`, `zone`, `metadata`
- AND no signal fields present

#### Scenario: Bollinger Bands zone
- GIVEN price crossing upper band
- WHEN Bollinger Bands computed
- THEN zone is "overbought" when price > upper band

#### Scenario: ATR volatility zone
- GIVEN spike volatility bars
- WHEN ATR computed
- THEN zone is "high_vol" when ATR percentile > 80

**Acceptance**: Every result has indicator_name, value, zone, metadata.  
**Error**: Returns `zone="insufficient_data"` when bars are below minimum; no exception.

### Requirement: REQ-303 RegimeClassifier produces regime and confidence

The system MUST produce `(regime: str, confidence: float)` from ADX/DMI + volatility percentile + trend persistence. Regimes: trending, range-bound, volatile, quiet. Confidence in [0, 1].

#### Scenario: Trending regime
- GIVEN Bars with ADX > 25 and +DMI > -DMI
- WHEN evaluated
- THEN regime is "trending"
- AND confidence reflects ADX strength and persistence

#### Scenario: Range-bound regime
- GIVEN Bars with ADX < 20 and low volatility percentile
- WHEN evaluated
- THEN regime is "range-bound"

#### Scenario: Volatile regime
- GIVEN Bars with ATR percentile > 90
- WHEN evaluated
- THEN regime is "volatile"
- AND confidence is high when expansion persists > 3 bars

**Acceptance**: Output tuple `(str, float)` with confidence clamped to [0, 1].  
**Error**: Returns `("unknown", 0.0)` when inputs are insufficient.

### Requirement: REQ-304 SentimentScorer ingests news and returns score

The system MUST ingest `NewsItem` list, return `sentiment_score: float` in [-1, 1] with rationale. Rule-based first; LLM enhancement is optional follow-up.

#### Scenario: Bullish news
- GIVEN NewsItems with bullish keywords ("beat", "upgraded")
- WHEN processed
- THEN sentiment_score > 0
- AND rationale lists triggering keywords

#### Scenario: Bearish news
- GIVEN NewsItems with bearish keywords ("missed", "downgrade")
- WHEN processed
- THEN sentiment_score < 0
- AND rationale lists triggering keywords

#### Scenario: Empty input
- GIVEN empty NewsItem list
- WHEN processed
- THEN sentiment_score is 0.0
- AND rationale indicates insufficient data

**Acceptance**: Score always in [-1, 1]; rationale non-empty when score != 0.  
**Error**: Returns 0.0 with empty rationale on empty input; no exception.

### Requirement: REQ-305 Frame model aggregates and serializes

The system MUST provide a Pydantic Frame model aggregating regime, regime_confidence, sentiment, technical_context, risk, capital, timeframe, edge, instruments. Serializable to JSON/YAML. Schema versioned.

#### Scenario: JSON serialization
- GIVEN populated Frame model
- WHEN to_json() called
- THEN output is valid JSON with all fields
- AND includes `schema_version`

#### Scenario: JSON deserialization
- GIVEN JSON with `schema_version="1.0"`
- WHEN from_json() called
- THEN all fields restored to original types
- AND Pydantic validation passes

#### Scenario: Partial frame
- GIVEN only regime and sentiment populated
- WHEN instantiated
- THEN optional fields default to None
- AND serialization omits null values

**Acceptance**: Round-trip JSON/YAML is lossless; schema_version immutable.  
**Error**: Raises ValidationError on schema version mismatch or missing required fields.

### Requirement: REQ-306 MarketAnalysisStage plugs into pipeline

The system MUST provide MarketAnalysisStage between StatisticsStage and ReviewStage; requires market_data + market_context; produces market_analysis + frame.

#### Scenario: Happy path
- GIVEN pipeline context with market_data and market_context after StatisticsStage
- WHEN MarketAnalysisStage runs
- THEN context gains market_analysis and frame
- AND ReviewStage receives these as inputs

#### Scenario: Missing required input
- GIVEN pipeline context without market_data
- WHEN MarketAnalysisStage runs
- THEN stage raises a clear error
- AND no partial frame is emitted

**Acceptance**: Stage registered between StatisticsStage and ReviewStage in pipeline DAG.  
**Error**: Fails fast with descriptive message when market_data or market_context is missing.

### Requirement: REQ-307 Guardian-ready contract

The system MUST include `guardian_hints` in Frame output with degradation signals (regime shift, sentiment shift, volatility expansion) consumable by future SDD 5.

#### Scenario: Regime shift hint
- GIVEN Frame where regime changed from trending to range-bound within lookback
- WHEN guardian_hints generated
- THEN hints includes `"regime_shift": true` with previous and current regime

#### Scenario: Volatility expansion hint
- GIVEN Frame where ATR percentile jumped from 30 to 95
- WHEN guardian_hints generated
- THEN hints includes `"volatility_expansion": true` with percentile delta

#### Scenario: Stable conditions
- GIVEN stable market conditions
- WHEN guardian_hints generated
- THEN hints contains only keys with active signals
- AND absent signals are omitted or null

**Acceptance**: `guardian_hints` is a dict; all values JSON-serializable.  
**Error**: Returns empty dict when no degradation signals detected.
