# Human Gates Specification

## Purpose

Human confirmation gates for the campaign flow. The pipeline adds `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and `HUMAN_APPROVE_ARCHIVE` to `HUMAN_GATE_IDS`, mirroring `HUMAN_APPROVE_CONFIG`: fail-closed in autonomous mode, resolvable via the OpenCode `question`-tool callback with stdin fallback.

## Requirements

### Requirement: Demo-Flow Human Gates (REQ-38)

The pipeline MUST add `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and `HUMAN_APPROVE_ARCHIVE` to `HUMAN_GATE_IDS`, mirroring `HUMAN_APPROVE_CONFIG`: in autonomous mode they MUST always block for a human decision (fail-closed); approval proceeds, denial blocks the phase. Each gate MUST present a complete envelope, accept exactly one answer, and re-present with STOP if the answer is missing or invalid. Each gate MUST be resolvable via the decision-file protocol — `QuestionToolGateCallback` writes `pending.json`, polls for `decision.json`, and resolves it; `StdinGateCallback` reads JSON decisions from stdin or a decisions file. `HUMAN_APPROVE_DEMO` and `HUMAN_APPROVE_ARCHIVE` MUST be real interceptors wired to the internal `pending_gate` markers of the demo deployer and the archive phase. Phase subagents MUST present gates through the same protocol: a phase agent SHALL use the `question` tool (permission `question: allow`) and MUST NOT auto-approve; a HOLD or unanswered gate MUST fail closed (REQ-11).
(Previously: gates were presented by the campaign loop; phase agents did not exist as gate presenters; lossless blocking-prompt discipline was not explicit.)

#### Scenario: Deploy gate blocks autonomously

- GIVEN autonomous mode with HUMAN_APPROVE_DEPLOY pending
- WHEN the gate fires before deploy
- THEN the loop blocks until a human decision arrives
- AND it never auto-approves

#### Scenario: Demo gate blocks before go-live

- GIVEN HUMAN_APPROVE_DEMO pending
- WHEN the demo phase is about to go live
- THEN execution holds pending human approval
- AND denial halts the demo phase

#### Scenario: Archive gate blocks before close

- GIVEN HUMAN_APPROVE_ARCHIVE pending
- WHEN the archive phase completes its plan
- THEN the plan is held for human confirmation
- AND denial returns the campaign to maintenance

#### Scenario: DEMO/ARCHIVE interceptors wired to pending gates

- GIVEN a demo deployer or archive phase exposing an internal `pending_gate` marker
- WHEN the flow reaches the demo or archive gate
- THEN the HUMAN_APPROVE_DEMO or HUMAN_APPROVE_ARCHIVE interceptor fires on that marker
- AND a pending decision is written for resolution

#### Scenario: Decision-file resolution

- GIVEN a pending demo gate in orchestrated mode
- WHEN the gate writes `pending.json` and a decision arrives via `decision.json`
- THEN the gate resolves to the human decision
- AND the flow proceeds or halts accordingly

#### Scenario: Exact-one answer required

- GIVEN a human gate presenting its envelope
- WHEN the user provides multiple answers
- THEN the gate re-presents the complete envelope
- AND stops until a single valid answer is given

#### Scenario: Missing answer re-presents

- GIVEN a gate with no decision
- WHEN the timeout expires
- THEN the gate re-presents the complete envelope
- AND blocks until a decision arrives

#### Scenario: Invalid answer halts

- GIVEN a gate receiving an unrecognized response
- WHEN the validation runs
- THEN the gate re-presents the envelope
- AND stops without proceeding

### Requirement: Headless Gate Decisions

The system MUST support a headless gate channel via the `--gate-decisions-file` flag. In headless mode, gate decisions SHALL be read from a JSON decision file via `StdinGateCallback`; the system MUST NOT prompt interactively. A missing or non-approved decision SHALL fail closed.

#### Scenario: Headless file resolves approval

- GIVEN a run-flow invoked with `--gate-decisions-file decisions.json`
- WHEN the decision file contains an approval for the pending gate
- THEN the gate resolves approved
- AND the flow continues without any interactive prompt

#### Scenario: Missing decision fails closed

- GIVEN a headless run-flow with no decision for the pending gate
- WHEN the gate resolves
- THEN the gate fails closed
- AND the flow stops with a non-zero exit

## ADDED Requirements

### Requirement: Blocking-Prompt Discipline (REQ-11)

All human gates MUST use lossless blocking-prompt discipline: present the complete envelope, accept exactly one answer, and re-present + STOP on missing or invalid input. Auto-approval is prohibited.

#### Scenario: Complete envelope always presented

- GIVEN any human gate
- WHEN the gate fires
- THEN the complete envelope (context, options, consequences) is presented
- AND the flow blocks until resolution

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | All gates present complete envelope |
| 2 | Multiple answers trigger re-present + STOP |
| 3 | Missing/invalid answers trigger re-present + STOP |
| 4 | Auto-approval is impossible |

## Affected Files

| File | Change |
|------|--------|
| `ai/opencode/agents/campaign.md` | Lossless gate protocol |
| `ai/opencode/agents/phase-*.md` (15) | Lossless gate sections |
| `ai/opencode/agents/guardian-orchestrator.md` | Lossless replacement gate |
