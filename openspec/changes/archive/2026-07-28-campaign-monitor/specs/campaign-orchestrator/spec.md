# Delta for Campaign Orchestrator

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Campaign Lifecycle

The system MUST execute the full sequential campaign flow: translate ResearchConfig to CFX, start sqcli daemon, load CFX into a project, run the project, poll for completion, export results, read exports, compute statistics, and store artifacts.
(Previously: phases executed sequentially without a background monitor)

#### Scenario: Full campaign completes successfully with monitor

- GIVEN a valid ResearchConfig and a licensed SQX environment
- WHEN the orchestrator runs a campaign
- THEN the standard 9-phase flow executes as before
- AND a CampaignMonitor asyncio task runs concurrently during the run/poll phases
- AND the monitor is cancelled when the campaign reaches a terminal state

#### Scenario: Campaign fails at translation phase — no monitor spawned

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
