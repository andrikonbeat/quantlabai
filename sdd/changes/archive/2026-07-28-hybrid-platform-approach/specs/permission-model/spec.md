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
