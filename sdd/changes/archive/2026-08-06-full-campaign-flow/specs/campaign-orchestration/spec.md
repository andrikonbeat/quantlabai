# Delta for campaign-orchestration

## MODIFIED Requirements

### Requirement: Orchestrated Campaign Loop (REQ-01)

The `quantlab-campaign` subagent MUST own the orchestrated phase loop across the full 14-phase lifecycle: research → hypothesis → SQX config → config review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops (Guardian watching the demo account). Each phase MUST return the Result Contract envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`). The loop MUST NOT stop at optimize; it MUST proceed through deploy, demo, and archive. `quantlab-orchestrator` SHALL remain the router.
(Previously: 8-phase loop halting after optimize with recommendations (D1); no deploy or post-deploy orchestration.)

#### Scenario: Full loop runs all 14 phases

- GIVEN a campaign objective entered in OpenCode chat
- WHEN `quantlab-campaign` runs the loop
- THEN the 14 phases execute in order, each returning the Result Contract envelope
- AND the loop terminates at archive with a maintenance plan and statistics

#### Scenario: Phase failure halts for human

- GIVEN a phase that fails
- WHEN the phase returns its envelope
- THEN the envelope carries `status=failed` and the loop halts awaiting a human decision

## ADDED Requirements

### Requirement: Flow-Integrity Invariant (REQ-37)

The full lifecycle MUST retain all 14 flow phases plus the Guardian live flow, in order, each gated by human confirmation. Simplification MUST apply only to code/infrastructure (shared substrate, consolidated generators); it MUST NOT remove, reorder, merge, or auto-approve any flow phase. Phase count and order MUST be asserted at campaign start and after any harness change.

#### Scenario: Harness change preserves flow

- GIVEN a refactored harness (e.g., substrate rollout)
- WHEN the campaign starts
- THEN the 14 phases plus the Guardian flow are asserted present and in order
- AND each phase blocks on its human gate before proceeding

#### Scenario: Dropped phase fails the assert

- GIVEN a harness missing the archive phase
- WHEN the campaign start assertion runs
- THEN the campaign aborts with a flow-integrity error
- AND no execution begins
