# Delta for campaign-orchestrator

## MODIFIED Requirements

### Requirement: Orchestrated Campaign Loop (REQ-01)

The `quantlab-campaign` subagent MUST own the orchestrated phase loop across the full 14-phase lifecycle: research → hypothesis → SQX config → config review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops (Guardian watching the demo account). Each phase MUST be delegated to its dedicated per-phase subagent via the `task` tool, and each delegated agent MUST return the Result Contract envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`) wrapped as a `PhaseResult` (REQ-802). The loop MUST fold each `PhaseResult` before dispatching the next phase, MUST NOT stop at optimize, and MUST proceed through deploy, demo, and archive. A post-phase gatekeeper MUST validate contract conformance, artifact read-back, no-hallucination, no-input-drift, and routing coherence before the next phase. The gatekeeper MUST allow exactly one corrective re-run per failed phase, then stop and report. `quantlab-orchestrator` SHALL remain the router.
(Previously: the campaign subagent executed phases via task delegation but had no post-phase gatekeeper loop.)

#### Scenario: Full loop runs all 14 phases

- GIVEN a campaign objective entered in OpenCode chat
- WHEN `quantlab-campaign` runs the loop
- THEN each of the 14 phases executes via its dedicated per-phase agent dispatched with `task`
- AND each `PhaseResult` envelope is folded and validated by the gatekeeper before the next phase is dispatched
- AND the loop terminates at archive with a maintenance plan and statistics

#### Scenario: Phase failure halts for human

- GIVEN a phase that fails
- WHEN the phase agent returns its `PhaseResult`
- THEN the envelope carries `status=failed` and the loop halts awaiting a human decision
- AND no subsequent phase is dispatched

#### Scenario: Gatekeeper validates envelope

- GIVEN a phase returning a `PhaseResult`
- WHEN the post-phase gatekeeper runs
- THEN it validates contract conformance, artifact read-back, no-hallucination, no-input-drift, and routing coherence
- AND only then dispatches the next phase

#### Scenario: Exactly-once corrective re-run

- GIVEN a phase that fails validation on first attempt
- WHEN the gatekeeper re-runs it
- THEN the phase executes exactly once more
- AND if it fails again, the loop stops and reports

### Requirement: Flow-Integrity Invariant (REQ-37)

The full lifecycle MUST retain all 14 flow phases plus the Guardian live flow, in order, each gated by human confirmation. Simplification MUST apply only to code/infrastructure (shared substrate, consolidated generators); it MUST NOT remove, reorder, merge, or auto-approve any flow phase. Phase count and order MUST be asserted at campaign start, at CLI run-flow start, and after any harness change.
(Previously: preflight was restored but the assertion timing was not fully explicit across all entry points.)

#### Scenario: Harness change preserves flow

- GIVEN a refactored harness (e.g., sync extension)
- WHEN the campaign starts
- THEN the 14 phases plus the Guardian flow are asserted present and in order
- AND each phase blocks on its human gate before proceeding

#### Scenario: Dropped phase fails the assert

- GIVEN a harness missing the archive phase
- WHEN the campaign start assertion runs
- THEN the campaign aborts with a flow-integrity error
- AND no execution begins

#### Scenario: Preflight runs after harness change

- GIVEN a harness change (e.g., sync extension)
- WHEN the campaign starts
- THEN the REQ-37 invariant is asserted
- AND a broken pipeline aborts with a flow-integrity error and non-zero exit

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | Post-phase gatekeeper validates `PhaseResult` envelope before next phase |
| 2 | Gatekeeper allows exactly one corrective re-run, then stops |
| 3 | REQ-37 asserted at campaign start, CLI run-flow start, and after harness change |
| 4 | 14 phases plus Guardian flow retained in order |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/agents/campaign.md` | Gatekeeper loop; lossless gate protocol; canonical contract |
| `ai/opencode/skills/quantlab-run-campaign/SKILL.md` | Restore preflight parity; dedupe to pointer |
