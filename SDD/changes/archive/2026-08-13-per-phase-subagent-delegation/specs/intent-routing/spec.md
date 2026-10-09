# Delta for Intent Routing

## ADDED Requirements

### Requirement: Phase Routing Note in Orchestrator (REQ-814)

`orchestrator.md` MUST document that CAMPAIGN intents route to `quantlab-campaign`, which then dispatches per-phase work to the 14 phase subagents via `task` (REQ-811). The orchestrator SHALL NOT route phase-level intents directly to phase agents; phase dispatch is internal to the campaign loop. The routing note SHALL also state that long-running phase operations are executed on the orchestrator shell, never waited on by a subagent (REQ-809).

#### Scenario: Campaign intent routes through campaign loop

- GIVEN a user message containing `run campaign`
- WHEN the orchestrator classifies the intent
- THEN the intent is routed to `quantlab-campaign` via `task`
- AND per-phase dispatch happens inside the campaign loop, not at the orchestrator

#### Scenario: Phase intents are not routed directly

- GIVEN a user message referencing a single phase (e.g., "run retest")
- WHEN the orchestrator classifies the intent
- THEN the orchestrator does not dispatch a phase agent directly
- AND the intent follows the existing CAMPAIGN or CLI routing row

#### Scenario: Routing note carries long-running policy

- GIVEN an updated `orchestrator.md`
- WHEN the routing note is consulted
- THEN it states that long-running operations execute on the orchestrator shell
- AND it states that phase subagents never wait on them