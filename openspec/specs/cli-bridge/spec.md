# CLI Bridge Specification

## Purpose

Defines the CLI bridge that invokes existing `sqcli` and SDK pipeline commands from the `quantlab-orchestrator` agent, providing a clean interface between intent classification and command execution.

## Requirements

### Requirement: sqcli invocation with structured arguments

The system MUST invoke the `sqcli` binary at `assets/SQX_144_2953_linux_20260601/sqcli` with arguments passed as structured `key=value` pairs, where each pair is a separate subprocess argument.

#### Scenario: sqcli command executes with key=value args

- GIVEN a CLI intent to run a campaign with `action=loadconfig name=my campaign`
- WHEN the bridge constructs the subprocess call
- THEN `sqcli` receives 3 separate arguments: `action=loadconfig`, `name=my campaign`, and any remaining args
- AND the space in `my campaign` is preserved (not split)

#### Scenario: sqcli binary path is resolved correctly

- GIVEN the bridge needs to locate the `sqcli` binary
- WHEN the path is resolved
- THEN it checks `assets/SQX_144_2953_linux_20260601/sqcli` relative to the project root
- AND if not found, checks the `SQCLI_PATH` environment variable
- AND if neither exists, returns an error: "sqcli binary not found"

#### Scenario: sqcli timeout is enforced

- GIVEN a long-running `sqcli` command
- WHEN the execution exceeds the configured timeout (default 300s)
- THEN the subprocess is terminated
- AND a `TimeoutError` is raised with the command and duration

### Requirement: SDK pipeline command invocation

The system MUST invoke SDK pipeline commands via the existing `sdk/quantlab/pipeline/` interface, passing the pipeline name and parameters as structured input.

#### Scenario: Pipeline command executes successfully

- GIVEN a request to run a pipeline named `wf_opt`
- WHEN the bridge invokes the SDK pipeline command
- THEN the pipeline executes with the provided parameters
- AND the result is returned as structured output

#### Scenario: Pipeline command returns error

- GIVEN a request to run a pipeline that does not exist
- WHEN the bridge invokes the SDK pipeline command
- THEN an error is returned with the pipeline name and error detail
- AND the orchestrator does not crash

### Requirement: CLI bridge returns structured results

The system MUST return CLI command results in a structured format including exit code, stdout, stderr, and duration.

#### Scenario: Successful command returns structured result

- GIVEN a successful `sqcli` command execution
- WHEN the bridge returns the result
- THEN the result contains: `exit_code: 0`, `stdout`, `stderr`, `duration_ms`
- AND `stdout` contains the command output

#### Scenario: Failed command returns error result

- GIVEN a failed `sqcli` command execution (non-zero exit code)
- WHEN the bridge returns the result
- THEN the result contains: `exit_code: <non-zero>`, `stdout`, `stderr`, `duration_ms`
- AND `stderr` contains the error output
- AND the result is marked as failed

### Requirement: CLI bridge does not modify existing SDK modules

The system MUST implement the CLI bridge using existing `sqcli` and SDK pipeline commands without creating new SDK modules or modifying existing agent classes.

#### Scenario: No new SDK modules are created

- GIVEN the CLI bridge is implemented
- WHEN the project structure is inspected
- THEN no new files are added under `sdk/quantlab/`
- AND existing `sdk/quantlab/` files are not modified

#### Scenario: No existing agent classes are modified

- GIVEN the CLI bridge is implemented
- WHEN existing agent class files are inspected
- THEN no agent class files are modified
