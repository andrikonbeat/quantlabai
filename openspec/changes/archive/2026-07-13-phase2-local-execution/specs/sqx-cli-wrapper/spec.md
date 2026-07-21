# SQX CLI Wrapper Specification — Delta

## ADDED Requirements

### Requirement: CommandDispatcher

The system MUST provide a `CommandDispatcher` abstraction that manages sqcli daemon lifecycle: start daemon, send commands, keep alive, and stop daemon. The dispatcher SHALL construct all commands using structured `key=value` argument formatting.

#### Scenario: Daemon starts and accepts commands

- GIVEN a CommandDispatcher targeting a valid sqcli binary
- WHEN the dispatcher starts the daemon
- THEN the daemon process is launched
- AND subsequent commands (loadconfig, status, export) are sent to the running daemon

#### Scenario: Daemon stop terminates the process

- GIVEN a running sqcli daemon
- WHEN the dispatcher stops the daemon
- THEN `sqcli -exit` is sent
- AND the daemon process is terminated

#### Scenario: Campaign commands construct correct arguments

- GIVEN a CommandDispatcher with a project named "campaign-1"
- WHEN constructing a loadconfig command with CFX file "/tmp/test.cfx"
- THEN the command is `sqcli -project action=loadconfig name=campaign-1 file=/tmp/test.cfx`
- AND each key=value pair is a separate argument (not split by spaces)

### Requirement: Campaign Result Types

The system MUST provide structured result types for campaign operations: `CampaignStatus` (running, completed, failed, stopped), `CampaignPhase` (enum of all 7 phases), and extended `CliResult` with command metadata (command string, args list, phase).

#### Scenario: CampaignStatus reflects sqcli output

- GIVEN a completed sqcli project
- WHEN the dispatcher polls status via `-project action=status`
- THEN a CampaignStatus with status=completed is returned
- AND the result includes the raw stdout for debugging

#### Scenario: Extended CliResult includes command metadata

- GIVEN any dispatched command
- WHEN the dispatcher returns the result
- THEN the result includes command string, args list, phase name, and all base CliResult fields (stdout, stderr, exit_code, duration)

## MODIFIED Requirements

### Requirement: Subprocess Execution

The system MUST execute `sqcli.exe` commands via subprocess with configurable timeout, stdout/stderr capture, and exit code inspection. Arguments MUST be passed as structured `key=value` pairs — each pair SHALL be a separate subprocess argument, NOT split by spaces.
(Previously: arguments passed via `command.split()` which breaks on `key=value` pairs with spaces)

#### Scenario: key=value arguments are passed correctly

- GIVEN a command with arguments `action=loadconfig name=my campaign file=/tmp/test.cfx`
- WHEN the wrapper executes it
- THEN the subprocess receives 3 separate arguments: `action=loadconfig`, `name=my campaign`, `file=/tmp/test.cfx`
- AND the command does not split on the space in "my campaign"

#### Scenario: Command executes and returns output

- GIVEN a valid sqcli command with structured key=value args
- WHEN the wrapper executes it
- THEN stdout, stderr, and exit code are captured and returned as a structured result

#### Scenario: Command times out gracefully

- GIVEN a long-running sqcli command
- WHEN the execution exceeds the configured timeout
- THEN the subprocess is terminated and a TimeoutError is raised

### Requirement: Dry-Run Mode

(Unchanged — no modification needed. The existing spec remains valid.)

### Requirement: Cross-Platform Path Resolution

(Unchanged — no modification needed. The existing spec remains valid.)

### Requirement: Structured Results

(Unchanged — no modification needed. The existing spec remains valid. Campaign result types are added as a separate requirement above.)

