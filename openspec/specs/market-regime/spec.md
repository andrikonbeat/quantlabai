# Delta for market-regime

## ADDED Requirements

### Requirement: REQ-321 RegimeClassifier accepts Bars and lookback

The system MUST accept Bar list + optional lookback window; return regime + confidence in [0, 1].

#### Scenario: Default lookback
- GIVEN Bar list without explicit lookback
- WHEN RegimeClassifier evaluates
- THEN default lookback is applied
- AND regime + confidence are returned

#### Scenario: Custom lookback
- GIVEN Bar list and lookback=20
- WHEN RegimeClassifier evaluates
- THEN analysis uses only the last 20 bars
- AND result reflects that window

**Acceptance**: Confidence is always a float in [0, 1].  
**Error**: Returns `("unknown", 0.0)` when Bar list is empty.

### Requirement: REQ-322 Regime transitions are smoothed

The system MUST smooth regime transitions; minimum persistence of 3 bars before regime change is reported.

#### Scenario: Stable regime holds
- GIVEN Bars consistently indicating "trending"
- WHEN RegimeClassifier evaluates each bar
- THEN regime remains "trending" for all bars

#### Scenario: Flip-flop suppression
- GIVEN Bars that alternate between trending and range-bound signals
- WHEN RegimeClassifier evaluates
- THEN regime does not change until a single regime persists for 3 bars

#### Scenario: Confirmed transition
- GIVEN 3 consecutive bars indicating "range-bound" after trending
- WHEN RegimeClassifier evaluates the third bar
- THEN regime changes to "range-bound"
- AND confidence reflects the new regime

**Acceptance**: No adjacent bars have different regimes unless persistence threshold is met.  
**Error**: Returns previous regime with reduced confidence when data is noisy but insufficient for transition.

### Requirement: REQ-323 Regime output includes triggers list

The system MUST include `triggers` list in regime output explaining which signals fired (ADX > 25, volatility percentile > 90, etc.).

#### Scenario: Trending triggers
- GIVEN Bars with ADX > 25 and +DMI > -DMI
- WHEN RegimeClassifier evaluates
- THEN triggers includes "ADX > 25" and "+DMI > -DMI"
- AND regime is "trending"

#### Scenario: Volatile triggers
- GIVEN Bars with ATR percentile > 90
- WHEN RegimeClassifier evaluates
- THEN triggers includes "volatility_percentile > 90"
- AND regime is "volatile"

#### Scenario: No triggers
- GIVEN Bars with no strong signals
- WHEN RegimeClassifier evaluates
- THEN triggers is an empty list or omitted
- AND regime reflects the dominant but weak signal

**Acceptance**: Triggers are human-readable strings matching documented signal names.  
**Error**: Returns empty triggers list when no signals exceed threshold.
