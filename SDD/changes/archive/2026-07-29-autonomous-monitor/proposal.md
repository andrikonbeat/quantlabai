# Proposal: Autonomous Monitor Daemon

## Intent

Live performance monitoring runs one-shot inside the pipeline stage — it computes metrics when equity arrives, but never sustains a persistent watch loop. Alerts are dicts in artifacts that no one dispatches. The existing `notifiers.py` infrastructure (Slack/Email/Webhook) is ready but unconnected. This change turns monitoring into a long-running autonomous daemon that streams equity in real time, detects regime shifts, dispatches notifications, and can take automated actions.

## Scope

### In Scope
- **Phase 1**: AutonomousMonitorDaemon — persistent asyncio loop pulling from `ResultReader.stream_live()`, rolling metrics, regime detection, alert dispatch via `notifiers.py`
- **Phase 2**: Auto-actions (stop strategy, reduce size, re-optimize) + time-series storage in Knowledge Lake
- **Phase 3**: Configurable thresholds + full test suite
- CLI command `quantlab monitor start/stop/status`

### Out of Scope
- Dashboard UI for live monitoring
- Historical alert analytics
- Modifying the existing pipeline `MonitorStage` contract
- SQX campaign monitor changes (separate `campaign-monitor` spec)

## Capabilities

### New Capabilities
- `autonomous-monitor`: Persistent daemon for live equity streaming, rolling metrics computation, regime detection, alert dispatch via configured notifiers, auto-actions, and time-series persistence

### Modified Capabilities
- None — existing monitoring is pipeline-stage-bound and has no standalone spec

## Approach

Extend `MonitoringAgent` with an `AutonomousMonitorDaemon` wrapping an asyncio loop. Reuse `compute_rolling_metrics`, `detect_regime_change`, `check_alerts`, and all `notifiers.py` classes. Consume `ResultReader.stream_live()` as the equity source. Add a `NotifierDispatcher` that routes alert dicts → configured notifier channels. CLI entry points via `quantlab` CLI extension. Persist metrics as time-series in Knowledge Lake (SQLite-backed, not ad-hoc YAML). Thresholds loaded from config with env var override.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/monitoring_agent.py` | Modified | Add `AutonomousMonitorDaemon` class |
| `sdk/quantlab/gates/notifiers.py` | Modified | Add `NotifierDispatcher` router |
| `sdk/quantlab/cli/` | New | `quantlab monitor start/stop/status` |
| `sdk/quantlab/knowledge/` | Modified | Time-series storage schema |
| `tests/agents/test_monitoring*.py` | New | Full test suite |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Daemon blocks on stream stalls | Med | Configurable timeout + heartbeat health check |
| Notifier failure amplifies | Low | Fail-logged, never retried (existing pattern) |
| CLI conflicts with existing commands | Low | Review CLI tree before implementation |

## Rollback Plan

Stop the daemon (`quantlab monitor stop`). Remove daemon class, CLI commands, and threshold config. The existing pipeline `MonitorStage` is untouched — no rollback needed there.

## Dependencies

- `ResultReader.stream_live()` AsyncGenerator (already exists)
- `notifiers.py` classes (already exist)
- `KnowledgeStore` for time-series (exists, needs schema extension)

## Success Criteria

- [ ] Daemon streams live equity, computes rolling metrics, dispatches alerts via configured notifiers
- [ ] `quantlab monitor start/stop/status` works end-to-end
- [ ] Slack/Email/Webhook notifications fire on alert events
- [ ] Auto-actions execute on configurable threshold breaches
- [ ] Time-series queryable from Knowledge Lake
- [ ] Tests cover: daemon lifecycle, alert dispatch, auto-actions, threshold config
