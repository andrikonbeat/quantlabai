# Guardian Feedback Specification

## Purpose

Wires live Guardian degradation/drawdown/regime/cost data from the demo account into the generation flow so the next campaign cycle starts from observed live behavior (Dukascopy-only).

## Requirements

### Requirement: Live Feedback into Generation (REQ-34)

The system MUST feed MetaGuardian live evaluations (degradation, drawdown, regime, cost, parameter matrix delta) into the generation flow: the feedback SHALL inform reconfiguration decisions and next-cycle research inputs, and SHALL be persisted as a feedback record per campaign. Feedback MUST NOT alter the 14-phase flow order (REQ-37) or bypass human gates. The system MUST also stream live demo-account equity/positions/costs to MetaGuardian for real-time state transitions. Feedback persistence MUST use a structured schema (`GuardianMetricRecord`) written to `knowledge/guardian-feedback/{campaign_id}/metrics.jsonl`; a `GuardianMetricsStore` read API MUST expose query-by-campaign and query-by-state-range capabilities.
(Previously: feedback persisted as a feedback record per campaign; no structured schema or read API)

#### Scenario: Live degradation feeds next cycle

- GIVEN MetaGuardian reports a strategy DEGRADING during the demo window
- WHEN the campaign archives
- THEN the feedback record is attached to the campaign archive
- AND next-cycle generation receives the degradation signal as input
- AND a `GuardianMetricRecord` is appended to `metrics.jsonl`

#### Scenario: Feedback never bypasses gates

- GIVEN live drawdown data arriving
- WHEN the generation flow consumes it
- THEN all human gates remain in force
- AND flow phase order is unchanged

#### Scenario: Metrics persist for next-cycle work

- GIVEN a completed campaign run
- WHEN `GuardianMetricsStore.query(campaign_id=...)` is called
- THEN all guardian scores, state transitions, and risk metrics are returned
- AND the data is available for next-cycle research

### Requirement: Guardian Feedback Schema

`GuardianMetricRecord` MUST be a typed Pydantic model with fields: `record_id` (UUID), `campaign_id` (str), `timestamp` (datetime UTC), `guardian_name` (str), `score` (float | None), `portfolio_state` (PortfolioState), `risk_metrics` (dict[str, Any] | None), `correlation_id` (str | None), and `source` (Literal["evaluation", "live_stream", "manual"]). The system SHALL validate records before writing; invalid records MUST raise `GuardianFeedbackError`.

#### Scenario: Valid record written

- GIVEN a well-formed `GuardianMetricRecord`
- WHEN `GuardianFeedbackStore.write(record)` is called
- THEN the record is appended to `metrics.jsonl`
- AND the write is atomic

#### Scenario: Invalid record rejected

- GIVEN a `GuardianMetricRecord` with an out-of-range `score`
- WHEN `GuardianFeedbackStore.write(record)` is called
- THEN `GuardianFeedbackError` is raised
- AND no partial write occurs
