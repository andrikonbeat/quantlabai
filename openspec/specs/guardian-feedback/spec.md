# Guardian Feedback Specification

## Purpose

Wires live Guardian degradation/drawdown/regime/cost data from the demo account into the generation flow so the next campaign cycle starts from observed live behavior (Dukascopy-only).

## Requirements

### Requirement: Live Feedback into Generation (REQ-34)

The system MUST feed MetaGuardian live evaluations (degradation, drawdown, regime, cost) into the generation flow: the feedback SHALL inform reconfiguration decisions and next-cycle research inputs, and SHALL be persisted as a feedback record per campaign. Feedback MUST NOT alter the 14-phase flow order (REQ-37) or bypass human gates.

#### Scenario: Live degradation feeds next cycle

- GIVEN MetaGuardian reports a strategy DEGRADING during the demo window
- WHEN the campaign archives
- THEN the feedback record is attached to the campaign archive
- AND next-cycle generation receives the degradation signal as input

#### Scenario: Feedback never bypasses gates

- GIVEN live drawdown data arriving
- WHEN the generation flow consumes it
- THEN all human gates remain in force
- AND flow phase order is unchanged
