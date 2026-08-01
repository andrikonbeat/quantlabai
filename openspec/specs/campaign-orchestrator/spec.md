# Campaign Orchestrator Specification

## Purpose

End-to-end pipeline runner that orchestrates the full campaign lifecycle: translate DSL → dispatch sqcli → poll status → export results → read → compute stats → store artifacts. Sequential execution with progress callbacks.

## Requirements

### Requirement: Campaign Lifecycle

The system MUST execute the campaign flow with optional reconfiguration. When auto_iterate=True and review_decision=ITERATE, the system SHALL apply parameter changes and rebuild in a versioned directory. When REJECT, it SHALL abort. When APPROVE, it SHALL proceed to portfolio. When auto_iterate=False, it SHALL execute a single iteration.

(Previously: Sequential execution without reconfiguration loop)

#### Scenario: Full campaign completes successfully

- GIVEN a valid ResearchConfig and a licensed SQX environment
- AND auto_iterate is True
- WHEN the orchestrator runs a campaign
- THEN the standard flow executes with optional reconfiguration between iterations
- AND a CampaignMonitor asyncio task runs concurrently during the run/poll phases
- AND the monitor is cancelled when the campaign reaches a terminal state

#### Scenario: Campaign fails at translation — no monitor spawned

- GIVEN a ResearchConfig that fails DSL-to-CFX translation
- WHEN the orchestrator runs the campaign
- THEN a CampaignError is raised at the translate phase
- AND no sqcli commands are dispatched
- AND no CampaignMonitor is spawned

#### Scenario: Campaign times out during polling — monitor cancelled

- GIVEN a campaign that exceeds the configured poll timeout
- WHEN the orchestrator polls for status beyond the limit
- THEN a CampaignError with timeout detail is raised
- AND the sqcli project is stopped via `-project action=stop`
- AND the CampaignMonitor task is cancelled

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
