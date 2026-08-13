# Campaign Orchestrator Specification

## Purpose

End-to-end pipeline runner that orchestrates the full campaign lifecycle: translate DSL → dispatch sqcli → poll status → export results → read → compute stats → store artifacts. Sequential execution with progress callbacks.

## Requirements

### Requirement: Orchestrated Campaign Loop (REQ-01)

The `quantlab-campaign` subagent MUST own the orchestrated phase loop across the full 14-phase lifecycle: research → hypothesis → SQX config → config review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops (Guardian watching the demo account). Each phase MUST be delegated to its dedicated per-phase subagent via the `task` tool, and each delegated agent MUST return the Result Contract envelope (`status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`) wrapped as a `PhaseResult` (REQ-802). The loop MUST fold each `PhaseResult` before dispatching the next phase, MUST NOT stop at optimize, and MUST proceed through deploy, demo, and archive. `quantlab-orchestrator` SHALL remain the router.
(Previously: the campaign subagent executed all phases inline in its own session; per-phase `task` delegation did not exist.)

#### Scenario: Full loop runs all 14 phases

- GIVEN a campaign objective entered in OpenCode chat
- WHEN `quantlab-campaign` runs the loop
- THEN each of the 14 phases executes via its dedicated per-phase agent dispatched with `task`
- AND each `PhaseResult` envelope is folded before the next phase is dispatched
- AND the loop terminates at archive with a maintenance plan and statistics

#### Scenario: Phase failure halts for human

- GIVEN a phase that fails
- WHEN the phase agent returns its `PhaseResult`
- THEN the envelope carries `status=failed` and the loop halts awaiting a human decision
- AND no subsequent phase is dispatched

### Requirement: Progress Callbacks

The system MUST fire a progress callback at each phase transition with the phase name, status, and optional detail. The callback protocol SHALL be a callable accepting `(phase: CampaignPhase, status: PhaseStatus, detail: str | None)`.

#### Scenario: All phases fire callbacks

- GIVEN a successful campaign run with a registered callback
- WHEN the orchestrator executes all phases
- THEN the callback fires 7 times: translate, daemon_start, load_config, run, poll, export, store

#### Scenario: Error phase fires callback with error status

- GIVEN a campaign that fails at the export phase
- WHEN the orchestrator encounters the failure
- THEN the callback fires with phase=export, status=error, and detail containing the error message

### Requirement: Status Polling

The system MUST poll sqcli project status at a configurable interval (default 30s) until the project reaches a terminal state (completed, failed, stopped) or the poll timeout is exceeded.

#### Scenario: Campaign completes within poll limit

- GIVEN a running campaign with 30s poll interval and 10min timeout
- WHEN the project completes after 3 polls
- THEN the orchestrator detects the completed status and proceeds to export

#### Scenario: Poll timeout raises CampaignError

- GIVEN a running campaign with 30s poll interval and 2min timeout
- WHEN the project does not complete within 4 polls
- THEN a CampaignError with timeout detail is raised
- AND the project is stopped via `-project action=stop`


### Requirement: WatcherEvent Callback

The system MUST accept an optional `on_watcher_event` parameter in the campaign orchestration entry points. When provided, it SHALL be passed to the CampaignMonitor for user notification. When absent, the CampaignMonitor uses its default CLI prompt behavior.

#### Scenario: Callback passed to CampaignMonitor

- GIVEN a campaign run with `on_watcher_event=<callable>`
- WHEN the orchestrator starts campaign execution
- THEN the callable is passed to the CampaignMonitor constructor
- AND the monitor invokes it on stall/error events instead of prompting

#### Scenario: No callback uses CLI prompts

- GIVEN a campaign run without `on_watcher_event`
- WHEN the orchestrator starts campaign execution
- THEN the CampaignMonitor falls back to rich.prompt.Confirm for WARNING/CRITICAL events

### Requirement: CampaignResult Gains Watcher Events

The `CampaignResult` model SHALL gain an optional `watcher_events: list[WatcherEvent]` field defaulting to an empty list. After campaign completion, the orchestrator SHALL collect all WatcherEvents from the monitor and assign them to this field.

#### Scenario: Watcher events collected on completion

- GIVEN a campaign with a CampaignMonitor that emitted events
- WHEN the campaign completes
- THEN CampaignResult.watcher_events contains all events emitted during the run
- AND each event retains its original timestamp, type, severity, and details

#### Scenario: No events yields empty list

- GIVEN a healthy campaign with no stall or error events
- WHEN the campaign completes
- THEN CampaignResult.watcher_events is an empty list

### Requirement: Flow-Integrity Invariant (REQ-37)

The full lifecycle MUST retain all 14 flow phases plus the Guardian live flow, in order, each gated by human confirmation. Simplification MUST apply only to code/infrastructure (shared substrate, consolidated generators); it MUST NOT remove, reorder, merge, or auto-approve any flow phase. Phase count and order MUST be asserted at campaign start, at CLI run-flow start, and after any harness change.

#### Scenario: Harness change preserves flow

- GIVEN a refactored harness (e.g., substrate rollout)
- WHEN the campaign starts
- THEN the 14 phases plus the Guardian flow are asserted present and in order
- AND each phase blocks on its human gate before proceeding

#### Scenario: Dropped phase fails the assert

- GIVEN a harness missing the archive phase
- WHEN the campaign start assertion runs
- THEN the campaign aborts with a flow-integrity error
- AND no execution begins

#### Scenario: CLI run-flow asserts before execution

- GIVEN the user invokes the campaign run-flow command
- WHEN the command starts
- THEN the REQ-37 invariant is asserted before any phase executes
- AND a broken pipeline aborts with a flow-integrity error and non-zero exit

### Requirement: Run-Flow Gate Execution

The system MUST execute every gate in `HUMAN_GATE_IDS` when `cmd_campaign_run_flow` runs the flow. Gate execution SHALL use stop-on-non-approved semantics: any gate that is not approved (REJECT, HOLD, ABORT, or missing decision) SHALL stop the flow with a non-zero exit code. The system MUST NOT auto-approve any gate (REQ-11), and MUST NOT return a false success when dispatch is blocked — a blocked dispatch MUST surface as a visible failure.

#### Scenario: Approved gate continues the flow

- GIVEN a run-flow with a pending config gate
- WHEN the gate decision is approved
- THEN the flow continues to the next phase
- AND dispatch proceeds with an explicit success status

#### Scenario: Rejected gate stops the flow non-zero

- GIVEN a run-flow with a pending human gate
- WHEN the gate decision is REJECT or the gate holds
- THEN the flow stops immediately
- AND the process exits with a non-zero code

#### Scenario: Dispatch is never silently blocked

- GIVEN a run-flow where dispatch would be blocked
- WHEN the gate is not approved
- THEN the flow fails loudly with the gate outcome
- AND no false-success result is returned

### Requirement: Per-Phase Delegation Dispatch (REQ-811)

The campaign loop MUST dispatch exactly one phase agent per phase, in `PHASES` order, using the `task` tool. The loop MUST NOT skip, reorder, or inline any phase; each dispatch MUST pass the bounded `PhaseDirective` (REQ-801) and MUST NOT run long-running operations itself (REQ-809). A dispatch failure SHALL halt the loop with the agent's `PhaseResult` preserved.

#### Scenario: Dispatch order matches PHASES

- GIVEN a full campaign run
- WHEN the loop dispatches phase agents
- THEN dispatch order matches the `PHASES` tuple exactly
- AND each agent receives a `PhaseDirective` for its own phase only

#### Scenario: No inlining fallback

- GIVEN a phase agent that is unavailable
- WHEN the loop reaches that phase
- THEN the loop halts with the error surfaced
- AND it does not fall back to inline execution
