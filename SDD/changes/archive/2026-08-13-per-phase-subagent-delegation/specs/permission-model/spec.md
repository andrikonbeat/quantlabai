# Delta for Permission Model

## ADDED Requirements

### Requirement: Deny-First Phase Agent Allowlists (REQ-812)

The permission model MUST configure each of the 14 per-phase subagents with a deny-first allowlist matching the established `quantlab-campaign`/`quantlab-guardian` pattern: `question: allow`, `task` restricted to `quantlab-*`, and all other tools denied unless explicitly allowed for that phase. A phase agent MUST NOT mutate `flow.py`, bypass gates, or reach tools outside its phase scope (REQ-808). Allowlist changes SHALL be auditable per agent.

#### Scenario: Deny-first default blocks unlisted tools

- GIVEN a phase agent with a deny-first allowlist
- WHEN it invokes a tool not on its allowlist
- THEN the invocation is denied
- AND the denial is logged with the agent name and command

#### Scenario: Phase-scoped allowance proceeds

- GIVEN the dispatch-phase agent with sqcli allowed
- WHEN it invokes an sqcli command in scope
- THEN the command executes without a permission prompt
- AND the allowance is logged

#### Scenario: Cross-phase access denied

- GIVEN a compile-phase agent attempting a deploy-phase action
- WHEN the permission check evaluates the action
- THEN the action is denied
- AND no execution occurs

### Requirement: SDK Pipeline Allowance Applies to Phase Agents (REQ-813)

SDK pipeline commands (`sdk/quantlab/pipeline/` and `sdk/quantlab/campaign/` invocations, including `delegation.py` glue) MUST remain non-destructive and execute without permission gates for phase agents, consistent with the existing orchestrator allowance. The delegation glue MUST NOT require a permission prompt for phase-scoped SDK calls.

#### Scenario: execute_phase runs without prompt

- GIVEN a phase agent calling `execute_phase()` for its own phase
- WHEN the permission check evaluates the call
- THEN the call is classified non-destructive
- AND it executes without a permission prompt

#### Scenario: Out-of-scope SDK call still denied

- GIVEN a phase agent calling an SDK entrypoint outside its phase scope
- WHEN the permission check evaluates the call
- THEN the call is denied
- AND an authority-violation result is returned