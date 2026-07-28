# SQX CLI Wrapper Specification

## Purpose

Cross-platform subprocess wrapper around StrategyQuant's `sqcli.exe`. Provides a clean Python interface for SQX operations with full dry-run support, enabling development and testing without an SQX installation.

## Requirements

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

The system MUST provide a dry-run mode where no subprocess is spawned. In dry-run mode, the system SHALL return documented mock results.

#### Scenario: Dry-run returns mock success

- GIVEN the wrapper is in dry-run mode
- WHEN any `sqcli.exe` command is invoked
- THEN no subprocess is created and a structured mock result is returned with exit code 0 and documented mock output

#### Scenario: Dry-run mode is configurable per-call

- GIVEN a wrapper instance initialized with dry-run=true
- WHEN a command is invoked with dry-run=false override
- THEN the subprocess is executed (not mocked) for that call

### Requirement: Cross-Platform Path Resolution

The system MUST resolve the `sqcli.exe` path according to the host OS. On Windows, it SHALL search common installation paths. On Linux/WSL, it SHALL use a configurable path or raise a clear error.

#### Scenario: Windows finds sqcli.exe automatically

- GIVEN Windows with SQX installed in Program Files
- WHEN the wrapper resolves the sqcli path
- THEN the default installation path is found without manual configuration

#### Scenario: Linux reports sqcli not found

- GIVEN Linux/WSL without a configured sqcli path
- WHEN the wrapper attempts to resolve sqcli
- THEN a clear error is raised indicating sqcli is not installed and suggesting dry-run mode

### Requirement: Structured Results

The system MUST wrap all subprocess results in a structured Pydantic model containing stdout, stderr, exit code, and execution metadata (duration, dry-run flag, platform).

#### Scenario: Result model contains all metadata

- GIVEN any command execution (real or dry-run)
- WHEN the wrapper completes
- THEN a structured result with stdout, stderr, exit_code, duration_seconds, is_dry_run, and platform fields is returned

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


### Requirement: extract_results_count Helper

The system MUST expose a public function `extract_results_count(status_text: str) -> int` that parses the "Strategies generated" line from SQX status plain text output and returns the integer count. If the pattern is not found, it SHALL return 0.

#### Scenario: Parses strategies generated count

- GIVEN status text containing "Strategies generated 255"
- WHEN extract_results_count is called
- THEN it returns 255

#### Scenario: Missing pattern returns zero

- GIVEN status text without "Strategies generated" (e.g., error message)
- WHEN extract_results_count is called
- THEN it returns 0

### Requirement: extract_error_patterns Helper

The system MUST expose a public function `extract_error_patterns(status_text: str) -> list[str]` that scans status text for SQX error patterns. The function SHALL detect: `Cannot start project`, `config errors`, `Error:`, and `Cannot get`. Each matched line (up to 3) SHALL be returned. If no patterns match, it SHALL return an empty list.

#### Scenario: Detects config error line

- GIVEN status text containing "Cannot start project 'X', it has config errors in task 'Build'"
- WHEN extract_error_patterns is called
- THEN it returns a list with one entry matching the error line

#### Scenario: Clean status returns empty list

- GIVEN a clean status response with strategies, running time, and databank
- WHEN extract_error_patterns is called
- THEN it returns an empty list

#### Scenario: Multiple errors detected

- GIVEN status text with multiple error lines
- WHEN extract_error_patterns is called
- THEN it returns up to 3 matched lines
- AND each line is the full text from the status response
