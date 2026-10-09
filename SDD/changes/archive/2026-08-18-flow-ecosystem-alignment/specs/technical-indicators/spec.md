# Delta for technical-indicators

## ADDED Requirements

### Requirement: IndicatorEngine Production Wiring (REQ-315)

`IndicatorEngine` (analysis/indicators.py:122) and `compute_indicators` (data/technical/indicators.py:44) MUST be reachable from the research data flow — the Dukascopy market block MUST invoke them and consume compact zone labels. The engines SHALL no longer be orphaned: a production caller MUST exist.

#### Scenario: Research flow computes zones

- GIVEN Dukascopy bars fetched for research
- WHEN the market block is built
- THEN IndicatorEngine computes the requested indicators
- AND zone labels are injected into the prompt

#### Scenario: Fail-soft on data gaps

- GIVEN bars insufficient for the requested period
- WHEN the engine computes
- THEN `zone="insufficient_data"` is returned
- AND no exception propagates to the research agent