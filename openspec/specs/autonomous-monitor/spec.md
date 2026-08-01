# Autonomous Monitor Specification

## Purpose

Long-running asyncio daemon for live equity streaming, rolling metrics, regime detection, alert dispatch, and auto-actions. Independent of the one-shot pipeline `MonitorStage`.

## Requirements

### Requirement: Daemon Lifecycle

The system MUST implement `AutonomousMonitorDaemon` as a persistent asyncio task with `start()`, `stop()`, and `status()`. Graceful shutdown SHALL complete the current iteration, close the stream, flush alerts, and cancel within 5s.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Start and stream | stopped daemon, valid config | `daemon.start()` called | background task streams equity via `ResultReader.stream_live()`, computes metrics |
| Graceful stop | running daemon mid-iteration | `daemon.stop()` called | iteration finishes, alerts flush, task completes ≤5s |
| Status check | any daemon state | `daemon.status()` called | returns `running`/`stopped`/`error` + uptime + last heartbeat |

### Requirement: Equity Streaming

The daemon MUST consume `ResultReader.stream_live(campaign_id)`. Stalls beyond `stream_timeout` (default 60s) SHALL trigger reconnect with 5s exponential backoff. After `max_retries` (default 5) failures, SHALL emit `STREAM_LOST` CRITICAL alert and enter `error`.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Transient reconnect | stream drops for 30s | `stream_timeout` exceeded | daemon reconnects, resumes from last checkpoint |
| Max retries lost | 5 consecutive failures | last retry fails | `STREAM_LOST` CRITICAL dispatched, daemon → `error` |

### Requirement: Rolling Metrics & Regime Detection

The daemon SHALL periodically invoke `MonitoringAgent.compute_rolling_metrics()` and `MonitoringAgent.detect_regime_change()` every `compute_interval` (default 60s). Latest metrics SHALL be available via `daemon.latest_metrics`.

- GIVEN a daemon streaming equity for 120s
- WHEN the first `compute_interval` elapses
- THEN rolling Sharpe, drawdown, volatility are computed
- AND regime changes detected

### Requirement: Alert Dispatch

The daemon MUST route alerts via `NotifierDispatcher` mapping severity to notifier channels from `notifiers.py`. Each alert SHALL carry `timestamp`, `type`, `severity`, `strategy_id`, `message`, `details`.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| CRITICAL to all notifiers | Slack + Email configured | `DRAWDOWN_BREACH` fires | dispatcher calls both `send()` with full payload |
| Notifier failure | notifier raises on `send()` | alert dispatch triggered | failure logged at WARNING, daemon continues |

### Requirement: Auto-Actions

The system MAY execute actions on threshold breaches. Three actions SHALL be supported: `stop_strategy`, `reduce_position` (50%), and `re_optimize`. Each MAY be enabled per strategy. Executed actions SHALL be logged and persisted to Knowledge Lake.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Stop on drawdown | `stop_strategy` enabled for X | CRITICAL `DRAWDOWN_BREACH` fires | `stop_strategy` dispatched, `STRATEGY_STOPPED` event persisted |
| Reduce on regime | `reduce_position` enabled | `REGIME_SHIFT` WARNING fires | position reduced 50% |

### Requirement: Threshold Configuration

Thresholds SHALL be per-strategy with global defaults fallback. Supported: `drawdown_threshold`, `sharpe_degradation_pct`, `compute_interval`, `stream_timeout`. Config MAY load from YAML with env override (`AUTONOMOUS_MONITOR_*`).

- GIVEN global `drawdown_threshold: 0.15` and strategy X override `0.10`
- WHEN computing alerts for X
- THEN `0.10` applies; other strategies use `0.15`

### Requirement: Time-Series Persistence

The daemon SHALL persist metrics and alerts to Knowledge Lake as append-only time-series. Each entry SHALL include `timestamp`, `strategy_id`, `metric_name`, `value`. Schema SHALL support SQL queries.

- GIVEN a daemon running 3 compute intervals
- WHEN each interval completes
- THEN a metrics row is appended
- AND queryable by strategy_id + time range

### Requirement: CLI Integration

The system MUST expose `quantlab monitor start/stop/status` following CLI patterns in `main.py`. `start` SHALL accept `--strategy`, `--config`, `--daemon`.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Start foreground | `quantlab monitor start --strategy X` | command runs | daemon starts, streaming output to stderr |
| Status check | running daemon | `quantlab monitor status` invoked | JSON output: `state`, `uptime_seconds`, `last_heartbeat`, `metrics_count` |

### Requirement: Heartbeat Health Check

The daemon MUST emit a heartbeat every `heartbeat_interval` (default 30s) with `timestamp`, `strategy_id`, `equity_count`, `alert_count`. 3 consecutive missing heartbeats SHALL be considered failure.

| Scenario | GIVEN | WHEN | THEN |
|----------|-------|------|------|
| Regular heartbeat | running daemon | 30s elapses | heartbeat persisted, available via `status()` |
| Stale heartbeat | daemon stopped heartbeating | 90s since last | health check returns `unhealthy`, `DAEMON_FAILURE` CRITICAL emitted |
