# Tasks: Autonomous Monitor Daemon

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~950 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | TimeSeriesStore + MonitorConfig | PR 1 | `pytest -k "timeseries or config" -v` | `python -c "from quantlab.knowledge.store import TimeSeriesStore; t=TimeSeriesStore(':memory:'); t.append_metrics('x',1,{'s':2.0}); print(t.query_metrics('x',0,2))"` | revert store.py, rm MonitorConfig from daemon file |
| 2 | Daemon + Dispatcher + Actions | PR 2 | `pytest -k "daemon or notifier or autoaction" -v` | `python -c "from quantlab.agents.autonomous_monitor import AutonomousMonitorDaemon, MonitorConfig; d=AutonomousMonitorDaemon(MonitorConfig('x')); print(d.status())"` | revert autonomous_monitor.py core classes |
| 3 | CLI + main.py + test glue | PR 3 | `pytest -k "cli" -v` | `quantlab monitor status --help` | revert monitor_commands.py + main.py |

## Phase 1: Foundation

- [x] 1.1 Add `TimeSeriesStore` to `store.py` — SQLite schema for metrics/alerts/heartbeats
- [x] 1.2 Create `MonitorConfig` dataclass in `autonomous_monitor.py` — YAML loading + env override
- [x] 1.3 Unit test: TimeSeriesStore in-memory CRUD, append + query round-trip
- [x] 1.4 Unit test: MonitorConfig YAML + `AUTONOMOUS_MONITOR_*` env var precedence

## Phase 2: Core Daemon

- [x] 2.1 Implement `AutonomousMonitorDaemon` asyncio loop consuming `ResultReader.stream_live()`
- [x] 2.2 Implement stall→reconnect with exponential backoff, max_retries → error state
- [x] 2.3 Implement `NotifierDispatcher` — severity→channel map, failure skip logging
- [x] 2.4 Implement `AutoActionExecutor` — stop_strategy, reduce_position, re_optimize
- [x] 2.5 Wire rolling metrics, regime detection, alert check into compute cycle
- [x] 2.6 Implement heartbeat health check — configurable interval, 3-miss stale detection

## Phase 3: CLI Integration

- [ ] 3.1 Create `monitor_commands.py` — `add_monitor_subparser()`, `cmd_monitor_start/stop/status`
- [ ] 3.2 Modify `main.py` — import + register `add_monitor_subparser` in `build_parser()`
- [ ] 3.3 Integration test: CLI commands via CliRunner

## Phase 4: Tests

- [x] 4.1 Unit test: NotifierDispatcher severity→channel routing + failure skip
- [x] 4.2 Unit test: AutoActionExecutor dispatch per threshold breach
- [x] 4.3 E2E test: mock stream 3 equity points, verify alerts fired + persisted to SQLite
