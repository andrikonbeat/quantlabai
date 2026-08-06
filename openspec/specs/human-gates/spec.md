# Human Gates Specification

## Purpose

Human confirmation gates for the campaign flow. The pipeline adds `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and `HUMAN_APPROVE_ARCHIVE` to `HUMAN_GATE_IDS`, mirroring `HUMAN_APPROVE_CONFIG`: fail-closed in autonomous mode, resolvable via the OpenCode `question`-tool callback with stdin fallback.

## Requirements

### Requirement: Demo-Flow Human Gates (REQ-38)

The pipeline MUST add `HUMAN_APPROVE_DEPLOY`, `HUMAN_APPROVE_DEMO`, and `HUMAN_APPROVE_ARCHIVE` to `HUMAN_GATE_IDS`, mirroring `HUMAN_APPROVE_CONFIG`: in autonomous mode they MUST always block for a human decision (fail-closed); approval proceeds, denial blocks the phase. Each gate MUST be resolvable via the OpenCode `question`-tool callback with stdin fallback.

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

#### Scenario: Question-tool resolution

- GIVEN orchestrated mode with a pending demo gate
- WHEN the gate raises
- THEN the choice envelope is presented via the `question` tool
- AND the human decision resolves the gate
