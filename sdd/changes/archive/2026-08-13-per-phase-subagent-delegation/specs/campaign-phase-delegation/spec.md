# Campaign Phase Delegation Specification

## Purpose

SDK contract for per-phase LLM sub-agent delegation: `PhaseDirective` handoffs, `PhaseResult` envelopes, and `execute_phase()` glue that enforces bounded authority without mutating the flow constant.

## Requirements

### Requirement: Phase Directives (REQ-801)

A phase dispatch MUST be expressed as a `PhaseDirective` carrying the phase id, the bounded scope, the directive payload, and a reference to the preceding `PhaseResult`. Directives MUST reference only the 14 canonical phase ids from `PHASES` (REQ-37).

#### Scenario: Directive carries phase and payload

- GIVEN an orchestrator about to dispatch the research phase
- WHEN a `PhaseDirective` is built
- THEN it carries the phase id, bounded scope, and directive payload
- AND it references the preceding `PhaseResult`

#### Scenario: Unknown phase id rejected

- GIVEN a directive whose phase id is not in `PHASES`
- WHEN the delegation layer validates it
- THEN validation fails with a phase-not-found error
- AND no dispatch occurs

### Requirement: PhaseResult Envelope (REQ-802)

Each phase agent MUST return a `PhaseResult` envelope reusing the Result Contract fields (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`) plus `phase_id`, `evidence`, and `handoff_payload`. A `status` other than `success` MUST halt folding until a human decision arrives.

#### Scenario: Success envelope folds

- GIVEN a phase that completed successfully
- WHEN its `PhaseResult` is returned
- THEN the orchestrator folds it into the campaign context
- AND the next phase directive is built from it

#### Scenario: Failed envelope halts

- GIVEN a phase returning `status=failed`
- WHEN the orchestrator receives the envelope
- THEN folding halts awaiting a human decision
- AND no further phase is dispatched

### Requirement: execute_phase Glue (REQ-803)

The system MUST provide `execute_phase()` glue in `sdk/quantlab/campaign/delegation.py` that maps a `PhaseDirective` to the registered phase executor, enforces the agent's bounded authority, and returns a `PhaseResult`. The glue MUST NOT run long-running operations inline; it MUST hand back runnable scripts for orchestrator-shell execution.

#### Scenario: Glue enforces authority

- GIVEN a directive whose executor attempts an out-of-scope action
- WHEN `execute_phase()` runs
- THEN the action is rejected
- AND the result carries an authority violation

#### Scenario: Long-running op returns script

- GIVEN a dispatch-phase directive requiring a long sqcli run
- WHEN `execute_phase()` handles it
- THEN a runnable script is returned in the result for the orchestrator shell
- AND the glue does not wait on completion

### Requirement: Wrap-Only Flow Invariant (REQ-804)

The delegation layer MUST wrap and delegate above the existing `PHASES` tuple and above `sdk/quantlab/agents/`; it MUST NOT mutate, reorder, rename, or remove any entry of `PHASES` in `sdk/quantlab/campaign/flow.py` (REQ-37). An integrity test MUST assert the flow constant is unchanged after this change lands.

#### Scenario: PHASES unchanged

- GIVEN the delegation layer in place
- WHEN `assert_flow` and `assert_flow_segments` run
- THEN both pass against the same 14-phase tuple
- AND the integrity test confirms flow.py untouched

#### Scenario: Mutation attempt detected

- GIVEN an accidental edit to flow.py that drops a phase
- WHEN the integrity test runs
- THEN it fails with a flow-integrity error
- AND no delegation proceeds