# Delta for Campaign Orchestrator

## MODIFIED Requirements

### Requirement: Orchestrated Campaign Loop (REQ-01)

The `quantlab-campaign` subagent MUST own the orchestrated phase loop across the full 14-phase lifecycle: research → hypothesis → SQX config → config review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops (Guardian watching the demo account). Each phase MUST be delegated to its dedicated per-phase subagent via the `task` tool, and each delegated agent MUST return the Result Contract envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`) wrapped as a `PhaseResult` (REQ-802). The loop MUST fold each `PhaseResult` before dispatching the next phase, MUST NOT stop at optimize, and MUST proceed through deploy, demo, and archive. `quantlab-orchestrator` SHALL remain the router.
(Previously: the campaign subagent executed all phases inline in its own session; per-phase `task` delegation did not exist.)

#### Scenario: Full loop runs all 14 phases

- GIVEN a campaign objective entered in OpenCode chat
- WHEN `quantlab-campaign` runs the loop
- THEN each of the 14 phases executes via its dedicated per-phase agent dispatched with `task`
- AND each `PhaseResult` envelope is folded before the next phase is dispatched
- AND the loop terminates at archive with a maintenance plan and statistics

#### Scenario: Phase failure halts for human

- GIVEN a phase that fails
- WHEN the phase agent returns its `PhaseResult`
- THEN the envelope carries `status=failed` and the loop halts awaiting a human decision
- AND no subsequent phase is dispatched

## ADDED Requirements

### Requirement: Per-Phase Delegation Dispatch (REQ-811)

The campaign loop MUST dispatch exactly one phase agent per phase, in `PHASES` order, using the `task` tool. The loop MUST NOT skip, reorder, or inline any phase; each dispatch MUST pass the bounded `PhaseDirective` (REQ-801) and MUST NOT run long-running operations itself (REQ-809). A dispatch failure SHALL halt the loop with the agent's `PhaseResult` preserved.

#### Scenario: Dispatch order matches PHASES

- GIVEN a full campaign run
- WHEN the loop dispatches phase agents
- THEN dispatch order matches the `PHASES` tuple exactly
- AND each agent receives a `PhaseDirective` for its own phase only

#### Scenario: No inlining fallback

- GIVEN a phase agent that is unavailable
- WHEN the loop reaches that phase
- THEN the loop halts with the error surfaced
- AND it does not fall back to inline execution