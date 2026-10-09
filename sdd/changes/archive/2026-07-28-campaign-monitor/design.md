# Design: Campaign Monitor

## Technical Approach

New `CampaignMonitor` asyncio task runs alongside `_dispatch_real`'s Phase 2 (poll status). It independently polls the SQX HTTP API at 5s intervals, analyzes responses against config-aware baselines (timeframe, WF/MC flags), and emits `WatcherEvent`s. WARNING/CRITICAL events trigger a `rich.prompt.Confirm` (CLI mode) or a registered callback (programmatic mode). On user approval, the monitor dispatches `-project action=stop` via the existing `_send_http`. All events are collected into the return value/`CampaignResult` on completion.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Poll ownership | Independent asyncio task | Share completion loop's HTTP responses | Diff intervals (5s vs 10s), diff concerns. Decoupling avoids timing coupling. ~5ms localhost overhead is negligible. |
| Monitor location | `_dispatch_real` spawns it | CampaignOrchestrator pipeline owns it | `_dispatch_real` is the concrete HTTP dispatch layer. Pipeline stages are one level abstracted. Monitor must live close to the HTTP flow it watches. |
| WF/MC source | Extract from config, pass to both `create_project` and `CampaignMonitor` | Hardcode always-on (current project_builder behavior) | Spec requires config-aware baselines. Adding params to `create_project` makes them explicit and guarantees project_builder and monitor share the same values. |
| Return collection | Monitor returns `list[WatcherEvent]`, appended to result dict/`CampaignResult` | Callback-only, no return | Both needed: callback for real-time notification, return value for `CampaignResult.watcher_events` audit trail. |
| Stop on stall | `rich.prompt.Confirm` dispatches `action=stop` via `_send_http` | Return event and let caller stop | User approval is synchronous (blocks monitor). After approval, immediate stop is safer than delegating — one less async hop before the campaign is halted. |

## Data Flow

```
_dispatch_real
  │
  ├── create_project(config)                    # WF/MC flags extracted
  ├── daemon start
  ├── action=start (HTTP)
  │
  ├── completion poll loop (10s) ──→ status_text ──→ check done
  │                                              └── Project execution stopped?
  │                                                  → break, continue to export
  │
  └── CampaignMonitor task (5s)
        │
        ├── HTTP GET /call?cmd=-project action=status name=<id>
        │     ↓
        ├── extract_results_count() → strategy count
        ├── extract_error_patterns() → error lines
        │
        ├── compute elapsed vs baselines
        │     ↓
        ├──┐ Stall detected? ──→ WatcherEvent
        │  │                      ├── callback    (programmatic mode)
        │  │                      └── rich.Confirm (CLI mode)
        │  │                           └── yes → HTTP action=stop
        │  │                                     → completion loop sees "stopped"
        │  └── No stall → continue
        │
        └──┐ Campaign completed externally?
             → emit campaign_complete event, exit
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/sqx/campaign_monitor.py` | Create | `CampaignMonitor` class, `WatcherEvent` dataclass, `extract_results_count`, `extract_error_patterns`, baseline computation (~250 LOC) |
| `sdk/quantlab/sqx/cli_wrapper.py` | Modify | `_dispatch_real` spawns monitor task; `dispatch_campaign` gains `on_watcher_event` kwarg; result dict gains `watcher_events` |
| `sdk/quantlab/sqx/project_builder.py` | Modify | `create_project` gains `walk_forward=True` and `monte_carlo=True` params |
| `sdk/quantlab/phase4/campaign_orchestrator.py` | Modify | `CampaignResult.watcher_events` field; `run_campaign` + `CampaignConfig` gain `on_watcher_event` param |
| `sdk/quantlab/sqx/__init__.py` | Modify | Export `CampaignMonitor`, `WatcherEvent` |
| `tests/phase4/test_campaign_monitor.py` | Create | Unit + integration tests |

## Interfaces / Contracts

```python
@dataclass
class WatcherEvent:
    timestamp: str                      # ISO 8601
    campaign_id: str
    event_type: Literal["startup_stall", "config_error",
                        "zero_growth_stall", "campaign_complete",
                        "excessive_rejection"]
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    details: dict

    def to_dict(self) -> dict: ...      # JSON-serializable

@dataclass
class BaselineConfig:
    startup_grace_s: float              # M1=60, H1=15
    expected_gen_time_s: float          # seconds per gen (pop*symbols/500)
    early_gen_multiplier: float         # 2.0 if WF+MC else 1.0
    early_gen_count: int = 3
    stall_polls_threshold: int          # ceil(gen_time / poll_interval) × 3
    rejection_warn_gens: int            # 3 if total_gens < 100 else 5

class CampaignMonitor:
    def __init__(self, campaign_id: str, base_url: str,
                 baseline: BaselineConfig,
                 poll_interval: float = 5.0,
                 on_watcher_event: Callable[[WatcherEvent], None] | None = None,
                 http_timeout: float = 10.0) -> None: ...

    async def run(self) -> list[WatcherEvent]: ...
    async def cancel(self) -> None: ...

def compute_baseline(config: Any,
                     poll_interval: float = 5.0) -> BaselineConfig: ...

def extract_results_count(status_text: str) -> int: ...
def extract_error_patterns(status_text: str) -> list[str]: ...
```

## Baseline Algorithm

```python
def compute_baseline(config, poll_interval=5.0):
    tf = _get_config_value(config, "timeframe", "H1")
    wf = bool(_get_config_value(config, "walk_forward", True))
    mc = bool(_get_config_value(config, "monte_carlo", True))
    gens = int(_get_config_value(config, "generations", 80))
    pop = int(_get_config_value(config, "population", 200))

    startup_grace = 60.0 if tf.upper() == "M1" else 15.0
    # Rough throughput: ~30s per gen baseline
    expected_gen = max(15.0, pop * gens / 500.0)
    early_mult = 2.0 if (wf and mc) else 1.0
    stall_polls = max(3, math.ceil(expected_gen / poll_interval) * 3)
    reject_gens = 3 if gens < 100 else 5

    return BaselineConfig(
        startup_grace_s=startup_grace,
        expected_gen_time_s=expected_gen,
        early_gen_multiplier=early_mult,
        early_gen_count=3,
        stall_polls_threshold=stall_polls,
        rejection_warn_gens=reject_gens,
    )
```

## Poll Cycle Design

```
def _poll_tick(status_text):
    now = time.monotonic()
    elapsed = now - start_time
    count = extract_results_count(status_text)
    errors = extract_error_patterns(status_text)

    # 1. Config errors → immediate CRITICAL
    if errors:
        emit(CRITICAL, "config_error", {"errors": errors, "elapsed_s": elapsed})

    # 2. Startup phase (0 strategies so far)
    if total_count == 0:
        if elapsed > baseline.startup_grace_s + baseline.expected_gen_time_s:
            emit(WARNING, "startup_stall", {"elapsed_s": elapsed, "count": 0})
        return

    # 3. Zero-growth stall (established throughput then stopped)
    if count == last_count:
        stall_polls += 1
        if stall_polls >= baseline.stall_polls_threshold:
            emit(WARNING, "zero_growth_stall",
                 {"count": count, "elapsed_s": elapsed, "stalled_polls": stall_polls})
    else:
        stall_polls = 0

    # 4. Excessive rejection (after M generations)
    if generation > baseline.rejection_warn_gens and rejection_rate >= 1.0:
        emit(INFO, "excessive_rejection",
             {"generation": generation, "rejection_rate": rejection_rate})
```

## Error Handling

| Condition | Behavior |
|-----------|----------|
| HTTP timeout / connection error | Log warning, skip tick, continue |
| 3 consecutive HTTP failures | Emit WARNING + rich prompt, continue |
| Daemon process dies | Monitor sees HTTP errors → self-cancels |
| Campaign stopped externally | Next poll detects "stopped" → emit `campaign_complete`, exit |
| `rich.Confirm` timeout | Default = False (no stop), continue monitoring |
| Monitor task cancelled during stop | Catch `CancelledError`, return collected events gracefully |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Baseline computation | `@pytest.mark.parametrize`: M1→60s, H1→15s, WF+MC→2x, no WF→1x |
| Unit | `extract_results_count` | Known text→int; missing→0; malformed→0 |
| Unit | `extract_error_patterns` | Error text→matched lines; clean→[]; 4+ errors→first 3 |
| Unit | `WatcherEvent` | JSON round-trip, all event types populated |
| Unit | Stall detection logic | Pure function: count seq + elapsed + baseline → expected event type |
| Integration | Monitor with mock SQX | Start mock, run campaign, run monitor, verify no events on healthy |
| Integration | Config error detection | Inject error text in mock response, verify CRITICAL event emitted |
| Integration | Monitor cancels on done | Fast mock campaign, verify monitor exits and returns events |
| E2E | Full dispatch + monitor | `dispatch_campaign(watcher_callback)`, verify events in result dict |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. All HTTP calls reuse the existing `_send_http` path.

## Migration / Rollout

No migration required. New `on_watcher_event` kwarg defaults to `None` — existing callers get CLI prompt behavior transparently. `create_project`'s new `walk_forward`/`monte_carlo` params have defaults matching current hardcoded behavior.

## Open Questions

None.
