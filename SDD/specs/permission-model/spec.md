# Permission Model Specification

## Purpose

Defines the permission model for the `quantlab-orchestrator` agent, ensuring destructive operations require explicit user approval while read-only and project-scoped operations proceed without friction.

## Requirements

### Requirement: Destructive bash operations require approval

The system MUST require explicit user approval via the `question` tool before executing any bash command that modifies files outside the project directory or performs destructive filesystem operations.

#### Scenario: File deletion requires approval

- GIVEN the orchestrator receives a bash command containing `rm` or `rm -rf`
- WHEN the permission check evaluates the command
- THEN the command is flagged as destructive
- AND `question: "allow"` is presented to the user
- AND the command does NOT execute until the user approves

#### Scenario: Git force-push requires approval

- GIVEN the orchestrator receives a bash command containing `git push --force`
- WHEN the permission check evaluates the command
- THEN the command is flagged as destructive
- AND `question: "allow"` is presented to the user

#### Scenario: Project-scoped edits do not require approval

- GIVEN the orchestrator receives a bash command that only modifies files within the project directory
- WHEN the permission check evaluates the command
- THEN the command is NOT flagged as destructive
- AND it executes without a permission prompt

### Requirement: Read operations are unrestricted within the project

The system MUST allow all `read` tool operations within the project directory without permission gates.

#### Scenario: Reading project files is unrestricted

- GIVEN the orchestrator needs to read a file within the project
- WHEN the `read` tool is invoked
- THEN the operation proceeds without approval
- AND the file content is returned

#### Scenario: Reading sensitive files outside project is denied

- GIVEN the orchestrator attempts to read a file outside the project matching `**/.env*`, `**/*.pem`, or `**/.ssh/**`
- WHEN the permission check evaluates the read
- THEN the operation is denied
- AND an error message is returned: "Read denied: sensitive file outside project scope"

### Requirement: Permission scope is auditable

The system MUST log all permission checks (approved and denied) with the command, timestamp, and outcome for audit purposes.

#### Scenario: Permission check is logged on approval

- GIVEN a destructive command is submitted
- WHEN the user approves the command
- THEN the approval is logged with: command text, timestamp, user decision

#### Scenario: Permission check is logged on denial

- GIVEN a destructive command is submitted
- WHEN the user denies the command
- THEN the denial is logged with: command text, timestamp, user decision

### Requirement: Permission model does not block SDK pipeline commands

The system MUST allow SDK pipeline commands (e.g., `sdk/quantlab/pipeline/` invocations) to execute without permission gates, as they are non-destructive by design.

#### Scenario: SDK pipeline command executes without approval

- GIVEN a request to run an SDK pipeline command
- WHEN the permission check evaluates the command
- THEN the command is classified as non-destructive
- AND it executes without a permission prompt

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
