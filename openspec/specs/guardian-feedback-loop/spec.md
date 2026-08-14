# Delta for guardian-feedback-loop

## ADDED Requirements

### Requirement: Live Demo Account Feed

The system MUST stream live demo-account equity, positions, and costs to MetaGuardian for real-time state transitions. The feed SHALL originate from the autonomous monitor and MUST NOT be spoofed by backtest data. If the live stream is lost, MetaGuardian SHALL enter STREAM_LOST hold.

#### Scenario: Live feed triggers DEFENSIVE state

- GIVEN MetaGuardian receives live demo equity data
- WHEN live drawdown exceeds 10%
- THEN MetaGuardian transitions to DEFENSIVE
- AND the transition is recorded in the feedback log

#### Scenario: Stream loss triggers hold

- GIVEN the live demo feed disconnects
- WHEN MetaGuardian detects stream loss for 60 seconds
- THEN MetaGuardian enters STREAM_LOST hold
- AND a reconnection alert is emitted

### Requirement: Parameter Matrix Feedback

The system MUST feed parameter justification matrix deltas into the generation flow. When live performance shows a parameter is consistently underperforming, the feedback SHALL flag it for review in the next research cycle.

#### Scenario: Underperforming parameter flagged

- GIVEN a parameter with confidence < 0.3 in live performance
- WHEN the feedback loop evaluates the matrix
- THEN the parameter is flagged for review
- AND next-cycle research receives the flag

## MODIFIED Requirements

### Requirement: Live Feedback into Generation (REQ-34)

The system MUST feed MetaGuardian live evaluations (degradation, drawdown, regime, cost, parameter matrix delta) into the generation flow: the feedback SHALL inform reconfiguration decisions and next-cycle research inputs, and SHALL be persisted as a feedback record per campaign. Feedback MUST NOT alter the 14-phase flow order (REQ-37) or bypass human gates. The system MUST also stream live demo-account equity/positions/costs to MetaGuardian for real-time state transitions.
(Previously: live degradation/drawdown/regime/cost into generation flow; persisted feedback record; never bypasses gates or flow order)

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
