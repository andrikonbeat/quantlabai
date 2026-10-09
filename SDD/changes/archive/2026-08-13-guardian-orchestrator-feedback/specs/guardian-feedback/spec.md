# Delta for guardian-feedback

## MODIFIED Requirements

### Requirement: Live Feedback into Generation (REQ-34)

The system MUST feed MetaGuardian live evaluations (degradation, drawdown, regime, cost) into the generation flow: the feedback SHALL inform reconfiguration decisions and next-cycle research inputs, and SHALL be persisted as a feedback record per campaign. Feedback MUST NOT alter the 14-phase flow order (REQ-37) or bypass human gates. Feedback SHALL cross the agent boundary as a bidirectional envelope: the guardian MUST deliver `guardian_state` plus the `FeedbackRecord` payload via `next_cycle_inputs()`, and MUST accept orchestrator directives bounded to evaluation and advice — directives MUST NOT auto-approve, reorder, or gate the flow. Escalation ack SHALL round-trip through the ops surface (REQ-36).
(Previously: one-directional data-level feedback into generation; persisted per campaign; never bypasses gates or flow order)

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

#### Scenario: Envelope delivers feedback to orchestrator

- GIVEN `quantlab-guardian` completes a live evaluation
- WHEN it returns the report envelope
- THEN the envelope contains `guardian_state` and a `FeedbackRecord`
- AND `next_cycle_inputs()` values are consumable by next-cycle generation

#### Scenario: Directive stays advisory

- GIVEN the orchestrator sends a directive to `quantlab-guardian`
- WHEN the directive requests advice on a DEFENSIVE state
- THEN the agent returns evaluation and advice only
- AND human gates and phase order remain unchanged
