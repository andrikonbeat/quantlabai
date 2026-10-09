# Delta for guardian-orchestrator

## MODIFIED Requirements

### Requirement: HUMAN_APPROVE_REPLACEMENT Live Gate (REQ-824)

The system MUST implement a `HUMAN_APPROVE_REPLACEMENT` live gate with fail-closed semantics (D10/D11): it is the ONLY path that changes a live position; the system MUST NEVER auto-replace a strategy. The gate MUST present a complete envelope, accept exactly one answer, and re-present + STOP on missing or invalid input. A HOLD, missing, or non-approved decision SHALL block the replacement; `guardian-orchestrator` SHALL present the gate via the decision-file protocol and MUST NOT execute without approval.
(Previously: the gate used fail-closed semantics but did not enforce lossless blocking-prompt discipline.)

#### Scenario: Replacement waits for human

- GIVEN a degrading strategy with a replacement candidate
- WHEN `HUMAN_APPROVE_REPLACEMENT` fires
- THEN the replacement is held pending a human decision
- AND no live position changes

#### Scenario: Non-approval fails closed

- GIVEN a HOLD decision on `HUMAN_APPROVE_REPLACEMENT`
- WHEN the gate resolves
- THEN the replacement is blocked
- AND the strategy is not replaced

#### Scenario: Exact-one answer required

- GIVEN `HUMAN_APPROVE_REPLACEMENT` firing
- WHEN the human provides multiple or invalid answers
- THEN the gate re-presents the complete envelope
- AND blocks until a single valid answer is given

#### Scenario: Invalid answer halts

- GIVEN a gate receiving an unrecognized response
- WHEN the validation runs
- THEN the gate re-presents the envelope
- AND stops without proceeding

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | `HUMAN_APPROVE_REPLACEMENT` is the only path to change a live position |
| 2 | Gate presents complete envelope with exact-one answer discipline |
| 3 | Missing/invalid input triggers re-present + STOP |
| 4 | Non-approval fails closed |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/agents/guardian-orchestrator.md` | Lossless replacement gate |
