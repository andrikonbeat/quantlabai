# Delta for SQX CLI Wrapper

## ADDED Requirements

### Requirement: Pipeline CLI Subcommand

The system MUST provide a `pipeline` subcommand with `run`, `status`, and `list` sub-subcommands. `pipeline run <pipeline.yaml>` SHALL parse a YAML stage config, build a `Pipeline`, run it via `PipelineRunner`, and stream per-stage status to stdout. `pipeline status <name>` SHALL check pipeline run status. `pipeline list` SHALL list recent pipeline runs.

#### Scenario: pipeline run executes from YAML

- GIVEN a YAML file with 3 stage definitions
- WHEN `pipeline run pipeline.yaml` is executed
- THEN stages are built and executed sequentially
- AND per-stage status is printed to stdout as each completes

#### Scenario: pipeline run with validation error

- GIVEN a YAML file with an unknown stage type
- WHEN `pipeline run pipeline.yaml` is executed
- THEN a PipelineError is raised
- AND the CLI prints the error to stderr and exits with code 1

#### Scenario: pipeline status reports run state

- GIVEN a previous pipeline run with name "test-run"
- WHEN `pipeline status test-run` is executed
- THEN run state (completed/failed/running) is printed
- AND per-stage results are included

#### Scenario: pipeline list shows recent runs

- GIVEN several completed pipeline runs
- WHEN `pipeline list` is executed
- THEN run names, timestamps, and statuses are printed

### Requirement: DaemonContext Helper

The system MUST provide a `DaemonContext` helper class that wraps `SQXDaemonManager` lifecycle (start/stop/health). It SHALL be usable as an async context manager and SHALL reduce CLI daemon boilerplate by at least 60% measured in lines per command.

#### Scenario: DaemonContext manages lifecycle

- GIVEN a CLI command that needs SQX daemon access
- WHEN using `async with DaemonContext(...) as daemon:`
- THEN daemon is started on entry
- AND daemon is stopped on exit (even on error)
- AND base_url and daemon_manager are accessible

#### Scenario: DaemonContext integrates with CLI args

- GIVEN CLI args with --sqx-path and --port
- WHEN DaemonContext is constructed from args
- THEN sqx_path, port, and json flag are consumed from the namespace
