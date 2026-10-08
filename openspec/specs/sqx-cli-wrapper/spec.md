# Delta for SQX CLI Wrapper

## ADDED Requirements

### Requirement: Portfolio Project Actions

The system MUST support sqcli project actions for Portfolio Composer and Portfolio Master projects.

#### Scenario: Loadconfig for portfolio CFX

- GIVEN a Portfolio Composer CFX at "/tmp/portfolio.cfx"
- WHEN `CommandDispatcher.loadconfig("portfolio-1", "/tmp/portfolio.cfx")` is called
- THEN sqcli command `action=loadconfig name=portfolio-1 file=/tmp/portfolio.cfx` is sent
- AND the project is loaded in the SQX daemon

#### Scenario: Loadconfig for portfolio master CFX

- GIVEN a Portfolio Master CFX at "/tmp/master.cfx"
- WHEN `CommandDispatcher.loadconfig("master-1", "/tmp/master.cfx")` is called
- THEN sqcli loads the portfolio builder configuration

#### Scenario: Start portfolio optimization

- GIVEN a portfolio project loaded
- WHEN `CommandDispatcher.start("portfolio-1")` is called
- THEN `action=start` is sent to the daemon
- AND the portfolio weight optimization begins

#### Scenario: Start portfolio master genetic search

- GIVEN a portfolio master project loaded
- WHEN `CommandDispatcher.start("master-1")` is called
- THEN the genetic portfolio builder starts running

### Requirement: Optimizer Project Actions

The system MUST support sqcli project actions for Optimizer projects.

#### Scenario: Loadconfig for optimizer CFX

- GIVEN an Optimizer CFX at "/tmp/optimizer.cfx"
- WHEN `CommandDispatcher.loadconfig("optimizer-1", "/tmp/optimizer.cfx")` is called
- THEN the optimizer configuration is loaded

#### Scenario: Start optimizer begins walk-forward optimization

- GIVEN an optimizer project loaded
- WHEN `CommandDispatcher.start("optimizer-1")` is called
- THEN the walk-forward optimization begins

#### Scenario: Status polling returns optimizer phase

- GIVEN an optimizer running
- WHEN `CommandDispatcher.status("optimizer-1")` is called
- THEN a CampaignStatus is returned with phase reflecting optimizer state (optimizing, walkforward, completed)

### Requirement: Retester Project Actions

The system MUST support sqcli project actions for Retester projects.

#### Scenario: Loadconfig for retester CFX

- GIVEN a Retester CFX at "/tmp/retester.cfx"
- WHEN `CommandDispatcher.loadconfig("retester-1", "/tmp/retester.cfx")` is called
- THEN the retester configuration is loaded

#### Scenario: Start retester begins Monte Carlo/Walk-Forward

- GIVEN a retester project loaded
- WHEN `CommandDispatcher.start("retester-1")` is called
- THEN Monte Carlo and Walk-Forward retesting begins

#### Scenario: Status returns retester progress

- GIVEN a retester running
- WHEN `CommandDispatcher.status("retester-1")` is called
- THEN CampaignStatus includes current Monte Carlo run and Walk-Forward cycle

### Requirement: Result Export for New Project Types

The system MUST export results from Portfolio, Optimizer, and Retester projects.

#### Scenario: Export portfolio weights CSV

- GIVEN a completed portfolio project
- WHEN `CommandDispatcher.export("portfolio-1", "/tmp/out", format="csv")` is called
- THEN a CSV with strategy IDs and weights is exported

#### Scenario: Export optimizer results CSV

- GIVEN a completed optimizer project
- WHEN `CommandDispatcher.export("optimizer-1", "/tmp/out", format="csv")` is called
- THEN CSV with all parameter combinations and objective values is exported

#### Scenario: Export retester reports

- GIVEN a completed retester project
- WHEN `CommandDispatcher.export("retester-1", "/tmp/out", format="html")` is called
- THEN Monte Carlo report and Walk-Forward report HTML files are exported

#### Scenario: Export retester databank files

- GIVEN a completed retester project with databank export enabled
- WHEN `CommandDispatcher.export("retester-1", "/tmp/out", format="databank")` is called
- THEN exported databank files are saved to output directory

### Requirement: Daemon Lifecycle for GUI Server

The system MUST manage the SQX GUI daemon lifecycle required for HTTP API calls (used by Portfolio Composer and JForex Deploy).

#### Scenario: Start daemon launches SQX with -gui flag

- GIVEN SQX installation path configured
- WHEN `DaemonManager.start()` is called
- THEN `sqcli -gui` is launched as subprocess
- AND the daemon process is tracked

#### Scenario: Stop daemon terminates process

- GIVEN a running SQX GUI daemon
- WHEN `DaemonManager.stop()` is called
- THEN the daemon process is terminated gracefully
- AND any child processes are cleaned up

#### Scenario: Daemon health check verifies HTTP endpoint

- GIVEN a running daemon
- WHEN `DaemonManager.is_healthy()` is called
- THEN an HTTP GET to the API endpoint (default localhost:8888) is attempted
- AND True is returned if 200 OK, False otherwise

#### Scenario: Auto-restart on daemon crash

- GIVEN daemon crashes during operation
- WHEN next command is dispatched
- THEN a new daemon is started automatically
- AND the command is retried once

## MODIFIED Requirements

### Requirement: Subprocess Execution

The system MUST execute `sqcli.exe` commands via subprocess with configurable timeout, stdout/stderr capture, and exit code inspection. Arguments MUST be passed as structured `key=value` pairs — each pair SHALL be a separate subprocess argument, NOT split by spaces. (Previously: Campaign commands only)

#### Scenario: Portfolio command args passed correctly

- GIVEN a portfolio command with arguments `action=loadconfig name=my portfolio file=/tmp/test.cfx`
- WHEN the wrapper executes it
- THEN the subprocess receives 3 separate arguments: `action=loadconfig`, `name=my portfolio`, `file=/tmp/test.cfx`
- AND the command does not split on the space in "my portfolio"
(Previously: only campaign commands were tested)

#### Scenario: Optimizer command args passed correctly

- GIVEN an optimizer command with key=value pairs containing spaces
- WHEN executed
- THEN each pair is a separate subprocess argument
(Previously: only campaign commands were tested)

#### Scenario: Retester command args passed correctly

- GIVEN a retester command with key=value pairs containing special characters
- WHEN executed
- THEN each pair is a separate subprocess argument
(Previously: only campaign commands were tested)

### Requirement: CommandDispatcher

The system MUST provide a `CommandDispatcher` abstraction that manages sqcli daemon lifecycle: start daemon, send commands, keep alive, and stop daemon. The dispatcher SHALL construct all commands using structured `key=value` argument formatting. (Previously: Campaign project lifecycle only)

#### Scenario: Daemon manages portfolio projects

- GIVEN a CommandDispatcher with valid sqcli binary
- WHEN the dispatcher starts the daemon
- THEN the daemon process is launched
- AND subsequent portfolio commands (loadconfig, start, status, export) are sent to the running daemon
(Previously: only campaign projects were managed)

#### Scenario: Daemon manages optimizer projects

- GIVEN a CommandDispatcher
- WHEN optimizer commands are dispatched
- THEN they are routed to the running daemon
(Previously: only campaign projects were managed)

#### Scenario: Daemon manages retester projects

- GIVEN a CommandDispatcher
- WHEN retester commands are dispatched
- THEN they are routed to the running daemon
(Previously: only campaign projects were managed)

#### Scenario: Campaign commands construct correct arguments

- GIVEN a CommandDispatcher with a project named "campaign-1"
- WHEN constructing a loadconfig command with CFX file "/tmp/test.cfx"
- THEN the command is `sqcli -project action=loadconfig name=campaign-1 file=/tmp/test.cfx`
- AND each key=value pair is a separate argument (not split by spaces)
(Previously: this was the only project type supported)

### Requirement: Campaign Result Types

The system MUST provide structured result types for campaign operations: `CampaignStatus` (running, completed, failed, stopped), `CampaignPhase` (enum of all 7 phases), and extended `CliResult` with command metadata (command string, args list, phase). (Previously: Campaign-specific types only)

#### Scenario: PortfolioStatus reflects sqcli output

- GIVEN a completed sqcli portfolio project
- WHEN the dispatcher polls status via `-project action=status`
- THEN a PortfolioStatus with status=completed is returned
- AND the result includes the raw stdout for debugging
(Previously: only CampaignStatus existed)

#### Scenario: OptimizerStatus reflects optimization phase

- GIVEN a running optimizer project
- WHEN status is polled
- THEN an OptimizerStatus with phase="walkforward_3_of_5" is returned
(Previously: only CampaignStatus existed)

#### Scenario: RetesterStatus reflects Monte Carlo progress

- GIVEN a running retester project
- WHEN status is polled
- THEN a RetesterStatus with mc_run=42, mc_total=100 is returned
(Previously: only CampaignStatus existed)

#### Scenario: Extended CliResult includes command metadata

- GIVEN any dispatched command (portfolio, optimizer, retester, campaign)
- WHEN the dispatcher returns the result
- THEN the result includes command string, args list, phase name, and all base CliResult fields (stdout, stderr, exit_code, duration)
(Previously: only campaign command metadata was included)

## REMOVED Requirements

None.

## RENAMED Requirements

None.