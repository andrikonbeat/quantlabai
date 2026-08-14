# Delta for technical-indicators

## ADDED Requirements

### Requirement: REQ-311 IndicatorEngine accepts requested indicators only

The system MUST accept a list of indicator names + Bar list; return only requested indicators (no eager computation of all).

#### Scenario: Selective computation
- GIVEN Bar list and requested indicators ["RSI", "MACD"]
- WHEN IndicatorEngine computes
- THEN only RSI and MACD results are returned
- AND no other indicators are computed

#### Scenario: Single indicator request
- GIVEN Bar list and requested indicator ["ATR"]
- WHEN IndicatorEngine computes
- THEN exactly one `IndicatorResult` is returned
- AND computation completes without computing RSI/MACD/SMA/EMA/BB

**Acceptance**: Computation scales with requested indicator count, not total supported indicators.  
**Error**: Returns empty list when indicator names list is empty.

### Requirement: REQ-312 IndicatorResult typed dict with normalized zones

The system MUST provide `IndicatorResult` as a typed dict with `indicator_name`, `value`, `zone`, `metadata`. Zones are normalized: overbought/oversold/neutral for oscillators; high/normal/low for volatility; trending/range for ADX.

#### Scenario: Oscillator zone normalization
- GIVEN RSI value of 78
- WHEN IndicatorResult is created
- THEN zone is "overbought"
- AND value is the raw RSI float

#### Scenario: Volatility zone normalization
- GIVEN ATR percentile of 85
- WHEN IndicatorResult is created
- THEN zone is "high"
- AND metadata includes percentile

#### Scenario: ADX trend zone normalization
- GIVEN ADX value of 30
- WHEN IndicatorResult is created
- THEN zone is "trending"
- AND metadata includes ADX value

**Acceptance**: Zone values are from a fixed enum; no ad-hoc strings.  
**Error**: Returns `zone="insufficient_data"` when value cannot be computed.

### Requirement: REQ-313 Missing data returns insufficient_data zone

The system MUST return `zone="insufficient_data"` with no exception raised for missing or insufficient data.

#### Scenario: Insufficient bars for RSI
- GIVEN 5 Bars and RSI(14) requested
- WHEN IndicatorEngine computes
- THEN result has `zone="insufficient_data"`
- AND no exception is raised

#### Scenario: All NaN prices
- GIVEN Bars where all close values are NaN
- WHEN any indicator is requested
- THEN result has `zone="insufficient_data"`
- AND no exception is raised

**Acceptance**: Consumer can always iterate results without try/except.  
**Error**: No exceptions propagate for data quality issues.

### Requirement: REQ-314 ta version drift handling

The system MUST handle `ta` version drift by version-pinning in pyproject.toml; IndicatorEngine validates `ta.__version__` at init and raises a clear error if below minimum.

#### Scenario: Valid ta version
- GIVEN `ta` version meets minimum
- WHEN IndicatorEngine initializes
- THEN init succeeds
- AND version is recorded

#### Scenario: Outdated ta version
- GIVEN `ta` version below minimum
- WHEN IndicatorEngine initializes
- THEN raises `ImportError` or `RuntimeError` with clear message
- AND message includes required and actual versions

#### Scenario: Missing ta package
- GIVEN `ta` is not installed
- WHEN IndicatorEngine initializes
- THEN raises clear error
- AND error message instructs to install pinned version

**Acceptance**: Minimum version is defined in code and documented.  
**Error**: Init fails before any computation when version is invalid.
