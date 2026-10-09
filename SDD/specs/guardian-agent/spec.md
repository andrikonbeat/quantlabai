# Guardian Agent Specification

## Purpose

Defines the `quantlab-guardian` orchestration agent: a first-class subagent that gives the Guardian library subsystem an identity at the orchestration surface, receives orchestrator directives, and returns feedback through a bidirectional envelope — without extending the 14-phase pipeline (REQ-37).

## Requirements

### Requirement: Guardian Agent Identity (REQ-641)

The system MUST provide a first-class `quantlab-guardian` subagent that executes Guardian evaluation and live-ops status intents on behalf of the orchestrator. The agent SHALL be dispatched through `task` delegation and SHALL return the Result Contract envelope. The agent MUST NOT introduce a new pipeline phase; it SHALL wrap the existing `guardian_evaluate` and `live-ops` stages, keeping `PHASES` at 14 (REQ-37).

#### Scenario: Orchestrator dispatches guardian task

- GIVEN the orchestrator holds a GUARDIAN intent
- WHEN it dispatches via `task` to `quantlab-guardian`
- THEN the agent runs the Guardian evaluation
- AND returns the Result Contract envelope

#### Scenario: Agent never adds a phase

- GIVEN the guardian agent executes an evaluation
- WHEN `assert_flow_integrity` runs
- THEN `PHASES` remains 14
- AND no new flow stage is registered

### Requirement: GUARDIAN Intent Routing (REQ-642)

Both orchestrators MUST route guardian intents (directives, live-ops status, feedback) to `quantlab-guardian` through a GUARDIAN route in their routing tables. Non-guardian intents MUST NOT be dispatched to the agent.
(Previously: only `quantlab-orchestrator` held the GUARDIAN route.)

#### Scenario: Directives route to guardian

- GIVEN the routing table of either orchestrator contains the GUARDIAN route
- WHEN a guardian directive arrives
- THEN it is dispatched to `quantlab-guardian`
- AND no other agent receives it

#### Scenario: Unknown intent stays with orchestrator

- GIVEN an intent that is not guardian-related
- WHEN the routing table evaluates it
- THEN it does not match the GUARDIAN route
- AND the owning orchestrator handles it

#### Scenario: guardian-orchestrator routes to quantlab-guardian

- GIVEN a live-ops evaluation intent routed to `guardian-orchestrator`
- WHEN it dispatches
- THEN it delegates to `quantlab-guardian` via `task`
- AND the `GuardianReport` envelope returns (REQ-644)

### Requirement: Directive Intake (REQ-643)

The guardian agent MUST accept structured orchestrator directives: evaluate, live-ops status, and escalation ack. Directives SHALL be bounded to evaluation and advice. Directives MUST NOT auto-approve, reorder, or gate the flow; human gates remain in force (REQ-34). Escalation ack SHALL round-trip through the ops surface (REQ-36).

#### Scenario: Live-ops status directive

- GIVEN the orchestrator requests live-ops status
- WHEN the agent receives the directive
- THEN it evaluates current live state
- AND reports status without altering flow order

#### Scenario: Escalation ack round-trips

- GIVEN an escalation was raised via the ops surface
- WHEN the orchestrator sends an ack directive
- THEN the agent acknowledges through the ops surface
- AND no gate or phase is affected

### Requirement: Report Envelope (REQ-644)

The guardian agent MUST return a report envelope wrapping `guardian_state` and the `FeedbackRecord` payload exposed by `next_cycle_inputs()` (REQ-34). The envelope SHALL be the guardian-to-orchestrator feedback channel and SHALL be consumable by next-cycle generation.

#### Scenario: Report carries state and record

- GIVEN the agent completed a live evaluation
- WHEN it returns the Result Contract envelope
- THEN the envelope contains `guardian_state`
- AND a `FeedbackRecord` with `next_cycle_inputs()` values

#### Scenario: Report without live signals

- GIVEN an evaluation produced no live signals
- WHEN the agent builds the envelope
- THEN the `FeedbackRecord` reflects no degradation
- AND the envelope still carries `guardian_state`
