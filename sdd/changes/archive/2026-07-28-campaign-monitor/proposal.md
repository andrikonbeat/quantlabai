# Proposal: Campaign Monitor

## Intent

SQX campaigns can run for hours silently producing zero strategies while burning compute. Today we discovered this at 40+ minutes — no alerts, no visibility. The Campaign Monitor is a background watcher that detects stalled or misconfigured campaigns by interpreting SQX HTTP API responses in **context** (timeframe, WF/MC flags, expected generation output) and notifies the user for approval before taking action.

## Scope

### In Scope
- Background watcher task that polls SQX status concurrently with campaign execution
- Context-aware stall detection (M1 ≠ H1, WF+MC ≠ vanilla)
- Active polling of per-campaign strategy/results count via HTTP API
- Notification to user with campaign state snapshot (stalled, config error, etc.)
- User approval gate before corrective action (stop/reconfigure)
- Integration with `cli_wrapper.py`'s dispatch flow

### Out of Scope
- Auto-healing without user approval
- Historical monitoring / dashboard UI
- Multi-campaign parallel monitoring (beyond active campaign)
- Integration with MetaGuardian or portfolio-level alerts

## Capabilities

### New Capabilities
- `campaign-monitor`: Asynchronous watcher that polls SQX daemon status, tracks strategy output rate against config-aware baselines, and emits stall/config-error detection events

### Modified Capabilities
- `campaign-orchestrator`: Add optional `on_watcher_event` callback hook; `CampaignResult` gains `watcher_events` field
- `sqx-cli-wrapper`: Expose `extract_results_count(status_text)` and `extract_error_patterns(status_text)` as public helpers

## Approach

Launch a `CampaignMonitor` asyncio task alongside `_dispatch_real`. The monitor:
1. Reads campaign config (timeframe, WF/MC flags, generations, population) to compute expected baselines
2. Polls `-project action=status name=<campaign>` at a configurable interval (5-10s)
3. Parses results count (strategies generated, generation number) from status text
4. Detects: zero-growth stalls, startup-timeout violations (M1 gets 60s grace, H1 gets 15s), config errors present in status output
5. Emits structured events to a callback — user receives notification via `rich` prompt or hook
6. Pauses campaign on user approval; fires `-project action=stop` after explicit yes

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/sqx/campaign_monitor.py` | New | Watcher module (~250 LOC) |
| `sdk/quantlab/sqx/cli_wrapper.py` | Modified | `_dispatch_real` spawns monitor task; passes `on_watcher_event` |
| `sdk/quantlab/sqx/project_builder.py` | Modified | Expose config params (timeframe, WF/MC) for baseline computation |
| `tests/` | New | Unit + integration tests for monitor |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| False positives on slow-but-healthy campaigns | Medium | Config-aware baselines + tunable thresholds; start relaxed, tighten via user feedback |
| Monitor overhead skews metrics | Low | Single HTTP poll per tick; ~5ms at localhost |
| Race condition on campaign stop | Low | Monitor checks "is campaign still running" before firing events |

## Rollback Plan

Remove `campaign_monitor.py`, revert `cli_wrapper.py` to pre-monitor dispatch, revert `project_builder.py` exports. No schema migration required.

## Dependencies

- httpx (already present for SQX API calls)
- No new external dependencies

## Success Criteria

- [ ] Monitor detects a stalled campaign (no new strategies in 3x expected generation time) and notifies user
- [ ] Monitor detects a config error (invalid engine, bad dates, broken XML) from status response
- [ ] User receives notification and can approve/deny corrective action
- [ ] M1 campaigns get longer startup grace than H1
- [ ] WF+MC campaigns get relaxed baselines for early generations
- [ ] All existing campaign-orchestrator scenarios still pass
