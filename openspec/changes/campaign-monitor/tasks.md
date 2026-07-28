# Tasks: Campaign Monitor

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~458 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Models+Helpers+Monitor → PR 2: Wiring (merged units 1+2) |
| Delivery strategy | stacked-to-main |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes — resolved: stacked-to-main, PR 1 contains work units 1+2 (Models + Helpers + Monitor class + tests).

### Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|----------------------|-----------------|-------------------|
| 1 | Models + helpers + pure tests | PR 1 | `pytest tests/phase4/test_campaign_monitor.py -k "extract_results or extract_error or compute_baseline or WatcherEvent or BaselineConfig" -v` | N/A — pure functions | Revert campaign_monitor.py models/helpers + tests |
| 2 | CampaignMonitor class + integ tests | PR 1 | `pytest tests/phase4/test_campaign_monitor.py -k "TestCampaignMonitor" -v` | `pytest tests/phase4/test_campaign_monitor.py -k "Integration" -v` | Revert CampaignMonitor class + tests |
| 3 | Wiring dispatch/orchestrator/init | PR 2 | `pytest tests/phase4/test_campaign_monitor.py -v` | `pytest -k "e2e" tests/phase4/test_campaign_monitor.py -v` | Revert cli_wrapper.py, project_builder.py, orchestrator.py, __init__.py |

## Phase 1: Data Models and Helpers

- [x] 1.1 Create `WatcherEvent` dataclass and `BaselineConfig` dataclass in `campaign_monitor.py`
- [x] 1.2 Implement `extract_results_count(status_text) -> int` — parse "Strategies generated N"
- [x] 1.3 Implement `extract_error_patterns(status_text) -> list[str]` — scan SQX error lines (up to 3)
- [x] 1.4 Implement `compute_baseline(config, poll_interval) -> BaselineConfig`

## Phase 2: CampaignMonitor Core

- [x] 2.1 Implement `CampaignMonitor.__init__` with BaselineConfig, callback, HTTP client
- [x] 2.2 Implement `_poll_tick` — extract count/errors, compute elapsed, detect stall patterns
- [x] 2.3 Implement `run()` — asyncio loop polling 5s; detect startup_stall, zero_growth_stall, config_error
- [x] 2.4 Implement `cancel()` + error handling (HTTP failures, CancelledError, daemon death)
- [x] 2.5 Implement CLI prompt (`rich.prompt.Confirm`) and callback dispatch for WARNING/CRITICAL
- [x] 2.6 Implement stop-on-approval via HTTP action=stop

## Phase 3: Integration Wiring

- [ ] 3.1 Add `walk_forward`, `monte_carlo` params to `create_project` in `project_builder.py`
- [ ] 3.2 Modify `_dispatch_real` in `cli_wrapper.py` — spawn CampaignMonitor at Phase 2
- [ ] 3.3 Modify `dispatch_campaign` — add `on_watcher_event` kwarg, collect watcher_events
- [ ] 3.4 Add `watcher_events: list[WatcherEvent]` field to `CampaignResult` in orchestrator
- [ ] 3.5 Add `on_watcher_event` param to `CampaignConfig` and `run_campaign`
- [ ] 3.6 Export `CampaignMonitor`, `WatcherEvent` in `sdk/quantlab/sqx/__init__.py`

## Phase 4: Testing

- [x] 4.1 Unit tests: `extract_results_count` (found, missing, malformed)
- [x] 4.2 Unit tests: `extract_error_patterns` (error lines, clean, 4+→first 3)
- [x] 4.3 Unit tests: `compute_baseline` (M1→60s, H1→15s, WF+MC→2x, no WF→1x)
- [x] 4.4 Unit tests: `WatcherEvent` JSON round-trip, all event types
- [x] 4.5 Integration: monitor with mock SQX (healthy, config-error, cancels-on-done)
- [ ] 4.6 E2E: `dispatch_campaign` with watcher_callback, verify events in result
