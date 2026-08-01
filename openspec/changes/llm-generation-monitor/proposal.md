# Proposal: LLM Generation Monitor

## Intent

Real campaigns (e.g. `campaign-jforex-m1-2026-07-31`: 58 generated, 0 accepted) produce mass rejection that is only visible after the task finishes. `CampaignMonitor` polls SQX status with regex heuristics and can only stop — it cannot recognize *why* a run is failing. We need an LLM-capable monitor that reads live status + databank counts mid-run, reasons about the run, and flags zero-acceptance early so a user can stop a doomed campaign.

## Scope

### In Scope (Phase 1)
- Standalone `LLMGenerationMonitor` in `sdk/quantlab/sqx/llm_generation_monitor.py`
- Prompt built every N-th poll: status text + `-databank action=list` counts + log tail + baseline (gens, population, WF/MC, criteria)
- Strict JSON verdict: `{assessment, severity, detected_issues[], recommended_action: continue|stop, confidence, reasoning}`
- `ActionExecutor` maps `stop` → `monitor.cancel()`/`-project action=stop`; `continue` → no-op
- Safety rails: reuse `LLMCircuitBreaker`, confidence gate, human-confirm on stop, slow LLM cadence (heuristics every poll)
- Optional hook in `cli_wrapper.dispatch_campaign` (mirrors `on_watcher_event`)
- `-databank action=list` polling added to `CampaignMonitor` observability
- Mock SQX server: realistic rejection simulation (non-growing counts)

### Out of Scope
- Phase 2: `adjust` / `regenerate` / `abort` verdicts
- Phase 2: pipeline stage integration in phase4 orchestrator
- SQX API changes (no pause/resume exists)
- Replacing `CampaignMonitor` heuristics — they remain the always-on fallback

## Capabilities

### New Capabilities
- `llm-generation-monitor`: verdict schema, prompt builder, LLM polling cadence, ActionExecutor (continue/stop), confidence gate + human confirm, circuit-breaker fallback

### Modified Capabilities
- `campaign-monitor`: add `-databank action=list` polling and snapshot hand-off to LLM monitor; keep heuristic events unchanged
- `sqx-cli-wrapper`: add `-databank action=list` support and optional LLM-monitor hook on `dispatch_campaign`

## Approach

Approach 1 from exploration (standalone monitor beside `CampaignMonitor`). Run in the dispatch loop; every N-th poll build compact prompt from shared observability, get verdict, gate on confidence ≥ threshold, human-confirm `stop`, dispatch via same cancel path. LLM failure → heuristics continue. Parse defensively (three parsers already disagree on status text).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/sqx/llm_generation_monitor.py` | New | LLM monitor + ActionExecutor |
| `sdk/quantlab/sqx/campaign_monitor.py` | Modified | Databank polling, snapshot feed |
| `sdk/quantlab/sqx/cli_wrapper.py` | Modified | `dispatch_campaign` hook |
| `sdk/quantlab/sqx/mock_sqx_server.py` | Modified | Rejection simulation |
| `sdk/quantlab/agents/llm_research_agent.py` | Reused | Circuit-breaker pattern |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM flag fatigue (100% rejection) | High | Baseline calibration, confidence gate, human confirm |
| Parser divergence on status text | Med | Defensive parsing, shared helpers |
| Databank format differs real vs mock | Med | Verify real output during impl; tolerate parse failure |
| Stop race with poll loop | Med | Reuse `monitor.cancel()` pattern |

## Rollback Plan

Monitor is opt-in via the dispatch hook: removing the hook registration restores current behavior. Revert `campaign-monitor` databank polling (isolated method, no event changes). No schema/data migrations involved.

## Dependencies

- `LLMConfig` (`sdk/quantlab/dsl/models.py`), `LLMCircuitBreaker` (`llm_research_agent`)
- `project_builder` baselines (`compute_baseline`)
- Mock server realism for tests; mocked LLM for unit tests

## Success Criteria

- [ ] Mocked zero-acceptance campaign triggers `stop` recommendation before task end
- [ ] Low-confidence verdicts never dispatch an action
- [ ] LLM failure falls back to heuristics with zero disruption
- [ ] Existing 530+ tests pass; new tests cover verdict→action mapping
