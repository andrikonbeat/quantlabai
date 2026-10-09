# Delta for autonomous-monitor

## ADDED Requirements

### Requirement: Monitor Integrates KnowledgeStore Health

The system MUST integrate `KnowledgeStoreHealthCheck` into the `AutonomousMonitorDaemon` alerting pipeline. The daemon MUST check store health at the start of each compute interval and include the status in its heartbeat and metrics output.

#### Scenario: Healthy store in heartbeat

- GIVEN the KnowledgeStore is healthy
- WHEN the daemon emits a heartbeat
- THEN `store_status: healthy` is included in the heartbeat payload

#### Scenario: Unhealthy store triggers alert

- GIVEN the KnowledgeStore health check returns UNHEALTHY
- WHEN the daemon's compute interval starts
- THEN a `STORE_UNHEALTHY` WARNING alert is dispatched via NotifierDispatcher
- AND the alert includes the health check failure reason

#### Scenario: Store health in status output

- GIVEN a running daemon
- WHEN `daemon.status()` is called
- THEN the status includes `store_health: healthy|unhealthy`
- AND includes the last health check timestamp

## MODIFIED Requirements

### Requirement: Alert Dispatch

The daemon MUST route alerts via `NotifierDispatcher` mapping severity to notifier channels from `notifiers.py`. Each alert SHALL carry `timestamp`, `type`, `severity`, `strategy_id`, `message`, `details`. The system MAY now include `store_health` in the `details` field of alerts when store health is degraded.

(Previously: alerts did not include KnowledgeStore health status in details)

#### Scenario: CRITICAL to all notifiers (unchanged)

- GIVEN Slack + Email configured
- WHEN `DRAWDOWN_BREACH` fires
- THEN dispatcher calls both `send()` with full payload

#### Scenario: Notifier failure (unchanged)

- GIVEN a notifier raises on `send()`
- WHEN alert dispatch triggered
- THEN failure logged at WARNING, daemon continues

### Requirement: Time-Series Persistence

The daemon SHALL persist metrics and alerts to Knowledge Lake as append-only time-series. Each entry SHALL include `timestamp`, `strategy_id`, `metric_name`, `value`. The system SHALL also persist store health status entries with `metric_name: "store_health"` and `value: "healthy"|"unhealthy"`.

(Previously: only metrics and alerts persisted; store health not in time-series)

- GIVEN a daemon running 3 compute intervals
- WHEN each interval completes
- THEN a metrics row is appended
- AND queryable by strategy_id + time range