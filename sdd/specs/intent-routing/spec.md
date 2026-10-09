# Intent Routing Specification

## Purpose

Defines the routing logic that directs incoming intents to the correct execution path: SDD requests to `gentle-orchestrator`, CLI commands to `sqcli`, dashboard requests to Phase 2 queue, and knowledge queries to CodeGraph.

## Requirements

### Requirement: SDD intents route to gentle-orchestrator

The system MUST route any intent matching `sdd-*` verbs (e.g., `sdd-propose`, `sdd-spec`, `sdd-design`, `sdd-tasks`, `sdd-apply`, `sdd-verify`, `sdd-archive`) to the `gentle-orchestrator` agent via the `task` tool.

#### Scenario: SDD propose request routes correctly

- GIVEN a user message containing `sdd-propose`
- WHEN the orchestrator parses the intent
- THEN the intent is classified as `SDD`
- AND the request is dispatched to `gentle-orchestrator` via `task`
- AND the original user message is forwarded unchanged

#### Scenario: SDD spec request routes correctly

- GIVEN a user message containing `sdd-spec`
- WHEN the orchestrator parses the intent
- THEN the intent is classified as `SDD`
- AND the request is dispatched to `gentle-orchestrator` via `task`

#### Scenario: Unknown SDD verb is rejected

- GIVEN a user message containing an unrecognized `sdd-*` verb
- WHEN the orchestrator classifies the intent
- THEN the intent is classified as `SDD`
- AND the orchestrator returns an error: "Unknown SDD verb: {verb}"

### Requirement: CLI intents route to sqcli

The system MUST route intents matching CLI patterns (`run campaign`, `deploy`, `sqcli`, `campaign`, `execute`) to the `sqcli` binary via subprocess execution.

#### Scenario: Run campaign command routes to sqcli

- GIVEN a user message containing `run campaign`
- WHEN the orchestrator classifies the intent
- THEN the intent is classified as `CLI`
- AND the request is routed to `sqcli` for execution
- AND the result is returned to the user

#### Scenario: Deploy command routes to sqcli

- GIVEN a user message containing `deploy`
- WHEN the orchestrator classifies the intent
- THEN the intent is classified as `CLI`
- AND the request is routed to `sqcli` for execution

#### Scenario: CLI command returns structured output

- GIVEN a valid `sqcli` command is routed
- WHEN the command completes
- THEN the output is captured as structured text
- AND exit code 0 returns success output
- AND non-zero exit code returns an error message with the exit code

### Requirement: Dashboard intents queue for Phase 2

The system MUST route intents matching dashboard or UI patterns (`dashboard`, `UI`, `web interface`, `visualize`) to a Phase 2 queue with a clear user-facing response.

#### Scenario: Dashboard request is queued

- GIVEN a user message containing `dashboard`
- WHEN the orchestrator classifies the intent
- THEN the intent is classified as `DASHBOARD`
- AND the user receives: "Dashboard UI is queued for Phase 2. CLI commands remain available now."
- AND no execution is attempted

#### Scenario: UI request is queued

- GIVEN a user message containing `UI`
- WHEN the orchestrator classifies the intent
- THEN the intent is classified as `DASHBOARD`
- AND the user receives the Phase 2 queue message

### Requirement: Knowledge queries route to CodeGraph and read

The system MUST route intents matching knowledge patterns (`what does`, `explain`, `how does`, `describe`) to CodeGraph exploration followed by file reads for context.

#### Scenario: "What does X do" routes to CodeGraph

- GIVEN a user message containing `what does`
- WHEN the orchestrator classifies the intent
- THEN the intent is classified as `KNOWLEDGE`
- AND CodeGraph is invoked to explore the relevant symbol or file
- AND the result is returned with source context

#### Scenario: "Explain X" routes to CodeGraph + read

- GIVEN a user message containing `explain`
- WHEN the orchestrator classifies the intent
- THEN CodeGraph is invoked for the target
- AND relevant source files are read for additional context
- AND a concise explanation is returned

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
