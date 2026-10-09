# Delta for meta-guardian

## ADDED Requirements

### Requirement: Live Account Feed (REQ-40)

MetaGuardian MUST evaluate against live demo-account data (equity, positions, costs) streamed by the autonomous monitor (REQ-41) during the demo phase, in addition to backtest-derived signals. Live drawdown/degradation SHALL drive state transitions and feed the Guardian feedback record (REQ-34). Data scope is Dukascopy-only.

#### Scenario: Live drawdown drives DEFENSIVE

- GIVEN a live account stream with drawdown > 10%
- WHEN MetaGuardian evaluates
- THEN the state transitions to DEFENSIVE
- AND the transition is recorded for feedback

#### Scenario: No stream fails closed

- GIVEN the live stream is unavailable
- WHEN MetaGuardian would evaluate live data
- THEN evaluation holds with a STREAM_LOST alert
- AND no live-based state transition occurs
