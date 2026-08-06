# Campaign Monitor Specification

## Purpose

Background watcher that polls SQX daemon status concurrently with campaign execution, detects stalled or misconfigured campaigns using config-aware baselines, and notifies the user for approval before corrective action.

## Requirements

### Requirement: Monitor Lifecycle

The system MUST launch a `CampaignMonitor` asyncio task alongside campaign execution. It SHALL poll `-project action=status name=<campaign>` at a configurable interval (default 5s). The task SHALL cancel when the campaign reaches a terminal state (completed, failed, or stopped).

#### Scenario: Monitor launches and polls during campaign

- GIVEN a campaign starting with default 5s poll interval
- WHEN `_dispatch_real` begins execution
- THEN a CampaignMonitor asyncio task is spawned
- AND it sends a status request every 5s
- AND no status requests are sent before the first interval elapses

#### Scenario: Monitor cancels on terminal state

- GIVEN an active CampaignMonitor polling a running campaign
- WHEN the campaign completes or stops
- THEN the monitor task is cancelled within one poll cycle
- AND no further HTTP requests are sent

### Requirement: Config-Aware Baselines

The system MUST compute expected generation baselines from campaign config parameters exposed by `project_builder.py`. M1 timeframe SHALL receive a 60s startup grace period; H1 and shorter timeframes SHALL receive 15s. When WF and MC are both enabled, expected generation time SHALL be doubled for the first 3 generations.

#### Scenario: M1 receives longer grace than H1

- GIVEN an M1 campaign
- WHEN the monitor computes baselines
- THEN startup grace period is 60s
- AND an H1 campaign receives 15s grace

#### Scenario: WF+MC doubles early-generation baseline

- GIVEN a campaign with WF and MC both enabled
- WHEN computing baselines for generations 1-3
- THEN the expected generation time is 2x the standard baseline
- AND after generation 3, standard baselines apply

### Requirement: Stall Detection

The system MUST detect three stall patterns. (1) **Startup stall**: 0 strategies generated after startup grace + one expected generation time → WARNING. (2) **Zero-growth stall**: strategy count unchanged for N consecutive polls (N = ceil(expected_gen_time / poll_interval) × 3) after startup throughput was established → WARNING. (3) **Excessive rejection**: 100% rejection rate after M generations (M = 3 for gen count < 100, else 5) → INFO.

#### Scenario: Startup stall triggers warning

- GIVEN an M1 campaign with 60s startup grace
- WHEN 60s + one expected generation time passes with 0 strategies
- THEN a startup_stall WARNING event is emitted
- AND event details include elapsed seconds and final strategy count

#### Scenario: Zero-growth stall after initial throughput

- GIVEN a campaign that produced strategies but then stalled
- WHEN the strategy count is unchanged for N consecutive polls (N = stall threshold)
- THEN a zero_growth_stall WARNING event is emitted
- AND event details include stalled count and elapsed duration

#### Scenario: Healthy campaign emits no stall events

- GIVEN a campaign generating strategies at expected rate
- WHEN the monitor runs for the full campaign duration
- THEN no stall events are emitted
- AND the monitor completes without user notification

### Requirement: Config Error Detection

The system MUST inspect each status response for error patterns matching SQX daemon error messages. The patterns SHALL include `Cannot start project`, `config errors`, `Error:`, and `Cannot get`. When found, the monitor SHALL emit a `config_error` CRITICAL event immediately.

#### Scenario: Config error detected from status text

- GIVEN a status response containing "Cannot start project 'X', it has config errors in task 'Build'"
- WHEN the monitor parses the response
- THEN a config_error CRITICAL event is emitted immediately
- AND the event details contain the full error text

#### Scenario: Clean status produces no error event

- GIVEN a status response showing strategies, running time, and databank count
- WHEN the monitor parses the response
- THEN no config_error event is emitted
- AND polling continues normally

### Requirement: Watcher Events

The system MUST emit structured `WatcherEvent` objects. Each event SHALL contain: `timestamp` (ISO 8601 str), `campaign_id` (str), `event_type` (Literal), `severity` (Literal), and `details` (dict). Valid event types: `startup_stall`, `config_error`, `zero_growth_stall`, `campaign_complete`, `excessive_rejection`. Valid severities: `INFO`, `WARNING`, `CRITICAL`.

#### Scenario: All event types carry correct structure

- GIVEN any detected condition (stall, error, or completion)
- WHEN a WatcherEvent is emitted
- THEN it contains timestamp, campaign_id, event_type, severity, and details
- AND the event is JSON-serializable

### Requirement: User Notification

The system MUST accept an optional callback `on_watcher_event(event: WatcherEvent) -> None`. When no callback is provided, WARNING and CRITICAL events SHALL prompt the user via `rich.prompt.Confirm("Campaign seems stalled. Stop?", default=False)`. On user approval, the campaign SHALL be stopped via `-project action=stop`. INFO events SHALL NOT prompt.

#### Scenario: Callback receives events

- GIVEN a CampaignMonitor with on_watcher_event registered
- WHEN a stall event is detected
- THEN the callback is invoked with the WatcherEvent
- AND no rich prompt is shown

#### Scenario: CLI mode prompts for stall events

- GIVEN no callback registered (CLI mode)
- WHEN a startup_stall or zero_growth_stall event is emitted
- THEN a rich Confirm prompt is shown with "Campaign seems stalled. Stop?"
- AND the function blocks until user responds
- AND on "y", `-project action=stop name=<campaign>` is dispatched

#### Scenario: INFO events do not prompt in CLI mode

- GIVEN no callback registered
- WHEN an excessive_rejection INFO event is emitted
- THEN no user prompt is shown
- AND the event information is logged at info level

### Requirement: Substrate-Backed Event Detection (REQ-42)

`CampaignMonitor` MUST run as the event-detection component of the unified execution substrate (REQ-26), parameterized per phase, detecting stalls/config errors across build/retest/optimize/portfolio phases. Existing signals (status text, exported `strategies.csv`, REQ-21) SHALL remain.

#### Scenario: Monitor runs on substrate

- GIVEN the unified flag enabled and a running phase
- WHEN the substrate executes the phase
- THEN event detection runs on the substrate's polling
- AND stall/config events flow as WatcherEvents

#### Scenario: Legacy monitor unchanged

- GIVEN the unified flag disabled
- WHEN dispatch spawns a monitor
- THEN prior standalone behavior is preserved
