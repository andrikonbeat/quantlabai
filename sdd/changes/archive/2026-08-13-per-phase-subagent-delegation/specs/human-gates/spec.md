# Delta for Human Gates

## MODIFIED Requirements

### Requirement: Demo-Flow Human Gates (REQ-38)

The pipeline MUST add `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and `HUMAN_APPROVE_ARCHIVE` to `HUMAN_GATE_IDS`, mirroring `HUMAN_APPROVE_CONFIG`: in autonomous mode they MUST always block for a human decision (fail-closed); approval proceeds, denial blocks the phase. Each gate MUST be resolvable via the decision-file protocol — `QuestionToolGateCallback` writes `pending.json`, polls for `decision.json`, and resolves it; `StdinGateCallback` reads JSON decisions from stdin or a decisions file. `HUMAN_APPROVE_DEMO` and `HUMAN_APPROVE_ARCHIVE` MUST be real interceptors wired to the internal `pending_gate` markers of the demo deployer and the archive phase. Phase subagents MUST present gates through the same protocol: a phase agent SHALL use the `question` tool (permission `question: allow`) and MUST NOT auto-approve; a HOLD or unanswered gate MUST fail closed (REQ-11).
(Previously: gates were presented by the campaign loop; phase agents did not exist as gate presenters.)

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

#### Scenario: Phase agent presents gate fail-closed

- GIVEN a phase agent at HUMAN_APPROVE_DEPLOY
- WHEN it presents the gate via the `question` tool
- THEN the flow blocks until a human decision arrives
- AND a HOLD or unanswered gate fails closed without auto-approval