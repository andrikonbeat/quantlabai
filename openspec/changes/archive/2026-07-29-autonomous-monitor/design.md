# Design: Autonomous Monitor Daemon

## Technical Approach

New `AutonomousMonitorDaemon` asyncio class that wraps `MonitoringAgent`'s metrics/regime/alert functions (reused, not duplicated) in a persistent loop consuming `ResultReader.stream_live()`. Alert routing via a lightweight `NotifierDispatcher`. Time-series metrics persisted via SQLite in the Knowledge Lake. CLI follows existing `add_*_subparser` pattern.

## Architecture Decisions

### Decision: Daemon as separate file

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Inline in `monitoring_agent.py` | Reuses imports but contaminates pipeline-bound class | **New `autonomous_monitor.py`** — keeps pipeline contract pristine |
| New file | Extra import, but clean separation of concerns | ✓ Selected |

### Decision: NotifierDispatcher collocated

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Separate `notifier_dispatcher.py` | ~60 LOC, adds module overhead | **Collocated in daemon file** — simple severity→channel map, not a framework |
| Inside daemon file | Tight coupling, but low complexity | ✓ Selected; extract if >3 routing rules emerge |

### Decision: SQLite for time-series

| Option | Tradeoff | Decision |
|--------|----------|----------|
| YAML append (current pattern) | No SQL queries, reads require full scan | **New `TimeSeriesStore` class in `store.py`** — stdlib sqlite3, zero dependency, supports `SELECT WHERE strategy_id + time` |
| Parquet/Arrow | Overkill for append-only metrics | ✗ Rejected |

### Decision: Config in daemon file

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `sdk/quantlab/monitor/config.py` | New module directory for one class | **`MonitorConfig` dataclass in `autonomous_monitor.py`** — config is daemon-specific |
| In daemon file | No reuse possible outside daemon | ✓ Selected; extract when a second consumer appears |

### Decision: CLI as external subparser

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Inline in `main.py` | Violates established pattern | **New `monitor_commands.py`** matching `agent_commands.py` pattern |
| External subparser | One extra file, clean registration in `build_parser()` | ✓ Selected |

## Data Flow

```
CLI ──→ monitor_commands.py
           │
           ▼
      AutonomousMonitorDaemon.start()
           │
           ├─ asyncio.create_task(_run_loop())
           │      │
           │      ├─ ResultReader.stream_live() ──→ stall? → reconnect (exp backoff)
           │      │
           │      ▼  (every compute_interval)
           │    compute_rolling_metrics()
           │    detect_regime_change()
           │    check_alerts()
           │      │
           │      ▼
           │    alerts[]
           │      │
           │      ├─→ NotifierDispatcher → SlackNotifier / EmailNotifier / WebhookNotifier
           │      ├─→ AutoActionExecutor  → stop / reduce / re_optimize
           │      └─→ TimeSeriesStore.append() (SQLite)
           │
           └─ status() → {state, uptime, heartbeat, metrics_count}
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/autonomous_monitor.py` | Create | Core daemon: `AutonomousMonitorDaemon`, `NotifierDispatcher`, `AutoActionExecutor`, `MonitorConfig` |
| `sdk/quantlab/knowledge/store.py` | Modify | Add `TimeSeriesStore` class with SQLite schema for metrics, alerts, heartbeats |
| `sdk/quantlab/cli/monitor_commands.py` | Create | `add_monitor_subparser()`, `cmd_monitor_start/stop/status` |
| `sdk/quantlab/cli/main.py` | Modify | Import + register `add_monitor_subparser` in `build_parser()` |
| `tests/agents/test_autonomous_monitor.py` | Create | Unit + integration tests |

## Interfaces / Contracts

```python
# autonomous_monitor.py
@dataclass
class MonitorConfig:
    strategy_id: str
    drawdown_threshold: float = 0.15
    sharpe_degradation_pct: float = 0.4
    compute_interval: int = 60
    stream_timeout: int = 60
    heartbeat_interval: int = 30
    max_retries: int = 5
    knowledge_root: str = "knowledge"
    notifiers: dict[str, dict] = field(default_factory=dict)  # {"slack": {...}}

class AutonomousMonitorDaemon:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def status(self) -> dict: ...     # state, uptime, heartbeat, metrics_count

# store.py
class TimeSeriesStore:
    def __init__(self, db_path: str) -> None: ...
    def append_metrics(self, strategy_id, timestamp, metrics: dict) -> None: ...
    def append_alert(self, alert: dict) -> None: ...
    def append_heartbeat(self, heartbeat: dict) -> None: ...
    def query_metrics(self, strategy_id, since, until) -> list[dict]: ...
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Daemon lifecycle (start/stop/status) | Mock `ResultReader.stream_live()`, verify state transitions |
| Unit | NotifierDispatcher routing | Verify severity→channel mapping, failure logging |
| Unit | AutoActionExecutor actions | Mock strategy control, verify dispatch |
| Unit | TimeSeriesStore CRUD | In-memory SQLite, append + query round-trip |
| Unit | MonitorConfig YAML + env override | Temp YAML, set `AUTONOMOUS_MONITOR_*` env vars |
| Integration | CLI commands | CliRunner, verify argparse + handler wiring |
| E2E | Full daemon loop | Mock stream yields 3 equity points, verify alerts fired + persisted |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. New SQLite database created on first daemon start. Existing `knowledge/monitoring/latest_metrics.yaml` is left intact — the daemon writes to a separate `knowledge/timeseries/monitor.db`.

## Open Questions

- [ ] AutoActionExecutor: how does `stop_strategy` reach the strategy? Needs a strategy-control interface (MQTT/SQX API/CLI). Phase 2 detail — mark as deferred.
- [ ] `--daemon` (fork to background): Python asyncio daemonization is OS-specific. Consider `supervisord` or systemd unit instead. Mark as stretch goal.
