# QuantLab Orchestrator Specification

## Purpose

Defines the `quantlab-orchestrator` agent entry in `opencode.json` and its prompt file with skill resolver. The agent serves as the primary entry point for SDD, CLI, and dashboard intents in the hybrid platform.

## Requirements

### Requirement: Agent registration in opencode.json

The system MUST register `quantlab-orchestrator` as a subagent in `opencode.json` with `mode: subagent`, a description, a prompt file reference, and a scoped tool set.

#### Scenario: Agent appears in opencode.json agents map

- GIVEN `opencode.json` exists at `~/.config/opencode/opencode.json`
- WHEN the quantlab-orchestrator agent is configured
- THEN `agents.quantlab-orchestrator` exists in the JSON
- AND its `mode` is `"subagent"`
- AND its `description` contains "QuantLab orchestrator"

#### Scenario: Agent prompt references the orchestrator prompt file

- GIVEN the agent is registered in `opencode.json`
- WHEN the agent config is read
- THEN `prompt` is set to `{file:~/.config/opencode/prompts/quantlab/orchestrator.md}`

#### Scenario: Agent has scoped tools

- GIVEN the quantlab-orchestrator agent config
- WHEN tools are listed
- THEN `bash`, `edit`, `read`, `write`, and `task` are allowed
- AND `question` is allowed for permission prompts

### Requirement: Prompt file with skill resolver

The system MUST create `~/.config/opencode/prompts/quantlab/orchestrator.md` containing the agent prompt with a skill resolver that loads relevant SDD skills via `## Skills to load before work`.

#### Scenario: Prompt file exists at the expected path

- GIVEN the orchestrator is configured
- WHEN `~/.config/opencode/prompts/quantlab/orchestrator.md` is checked
- THEN the file exists
- AND it is readable

#### Scenario: Prompt includes skill resolver directive

- GIVEN the orchestrator prompt file exists
- WHEN the prompt is read
- THEN it contains a `## Skills to load before work` section
- AND the section lists `sdd-spec`, `sdd-design`, `sdd-tasks`, `sdd-apply`, `sdd-verify`, `sdd-archive`

#### Scenario: Prompt includes intent routing instructions

- GIVEN the orchestrator prompt file exists
- WHEN the prompt is read
- THEN it contains routing rules for SDD, CLI, and dashboard intents
- AND it references `gentle-orchestrator` for SDD requests
- AND it references `sqcli` for CLI requests
- AND it states dashboard requests are queued for Phase 2

### Requirement: Permission scope prevents destructive ops without approval

The system MUST scope the `quantlab-orchestrator` agent permissions so that destructive bash operations require explicit user approval via the `question` tool.

#### Scenario: Destructive bash commands require approval

- GIVEN the quantlab-orchestrator agent is invoked
- WHEN a bash command that modifies files outside the project is attempted
- THEN the permission model requires `question: "allow"` for that command
- AND the command does not execute until approved

#### Scenario: Read-only and project-scoped ops are allowed

- GIVEN the quantlab-orchestrator agent is invoked
- WHEN read-only operations within the project directory are performed
- THEN they execute without approval prompts
- AND `edit`, `read`, `write`, and `task` tools are available without gate

### Requirement: Agent does not implement SDK logic directly

The system MUST ensure the `quantlab-orchestrator` agent dispatches to existing SDK and CLI tools rather than reimplementing research logic.

#### Scenario: Agent delegates to gentle-orchestrator for SDD tasks

- GIVEN an SDD intent (e.g., `sdd-propose`, `sdd-spec`)
- WHEN the orchestrator receives the intent
- THEN it delegates to `gentle-orchestrator` via the `task` tool
- AND it does not reimplement proposal or spec logic

#### Scenario: Agent delegates to sqcli for CLI operations

- GIVEN a CLI intent (e.g., `run campaign`, `deploy`)
- WHEN the orchestrator receives the intent
- THEN it invokes `sqcli` via bash subprocess
- AND it does not reimplement sqcli logic
