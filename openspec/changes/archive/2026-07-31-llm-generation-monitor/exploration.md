## Exploration: LLM-Capable Monitor for SQX Generation (Stage 6)

### Current State

The pipeline has **three monitoring layers, none of which use an LLM**, and none
of which can meaningfully act on a running generation:

1. **`MonitoringAgent`** (`sdk/quantlab/agents/monitoring_agent.py`) — monitors
   **live equity after deployment** (rolling Sharpe/drawdown/vol, regime
   detection, threshold alerts, gate decision). Pure numeric heuristics. Not
   involved in generation at all. No LLM.

2. **`AutonomousMonitorDaemon`** (`sdk/quantlab/agents/autonomous_monitor.py`) —
   asyncio daemon wrapping `MonitoringAgent` with `NotifierDispatcher`
   (slack/email/webhook) and `AutoActionExecutor` (3 hard-coded actions:
   `stop_strategy`, `reduce_position`, `re_optimize`). The executor only **logs
   and records events** — "actual strategy-control integration is deferred" per
   its docstring. No LLM, no real control.

3. **`CampaignMonitor`** (`sdk/quantlab/sqx/campaign_monitor.py`) — the only
   component that watches **generation itself**. Polls the SQX HTTP API
   (`-project action=status`) against config-derived baselines
   (`compute_baseline`: startup grace, expected gen time, stall thresholds) and
   emits `WatcherEvent`s via regex heuristics:
   - `startup_stall`, `config_error`, `zero_growth_stall`,
     `campaign_complete`, `excessive_rejection`
   - On WARNING/CRITICAL, either fires a callback or prompts the user; on
     approval dispatches `-project action=stop`.
   - **No LLM. No parameter adjustment. No regeneration. Only stop.**

**The builder handoff** (`sdk/quantlab/agents/builder_agent.py` →
`_dispatch_single` → `sdk/quantlab/sqx/cli_wrapper.py:dispatch_campaign`):
create project → start daemon → `action=start` → poll `action=status` in a
10 s loop (with `CampaignMonitor` running concurrently) → `action=stop` →
`-databank action=export` → stop daemon. Retry logic is **blind**
(timeout/failure → exponential backoff), never informed by what the campaign is
actually doing.

**Real-world evidence this matters**: every real campaign in
`assets/SQX_144_2953_linux_20260601/user/projects/*/log/global_log_*.log` shows
mass rejection. Example (`campaign-jforex-m1-2026-07-31`):
`Strategies generated: 58, Accepted: 0, Rejected: 58` with breakdown
`Initial population filter: Profit factor > 0.50, Count: 30` and
`Automatic filter: no trades, Count: 12`. Zero `.sqx` files ever reached any
`databanks/Results/` directory. This is exactly the "strategy is being filtered
out / conditions never trigger" failure the user wants caught EARLY — currently
it is only visible after the task finishes.

### Affected Areas

| File | Role | Why it matters |
|------|------|----------------|
| `sdk/quantlab/sqx/campaign_monitor.py` | Generation watcher | Core — heuristics only; needs to feed raw snapshots to an LLM and add `-databank action=list` polling |
| `sdk/quantlab/sqx/cli_wrapper.py` | Dispatch loop | Wiring point — LLM monitor must run inside `_dispatch_real`/`_dispatch_mock` and coordinate stop with the poll loop |
| `sdk/quantlab/sqx/mock_sqx_server.py` | Test/demo SQX | Status text + databank counts too simplistic for LLM scenarios; needs realistic rejection simulation |
| `sdk/quantlab/agents/builder_agent.py` | Builder → SQX handoff | Retry is blind; needs to route LLM verdicts (adjust/regenerate) and pass monitor config |
| `sdk/quantlab/agents/monitoring_agent.py` | Live-trading monitor | NOT the right layer for generation monitoring — do not conflate; keep separate |
| `sdk/quantlab/phase4/stages/__init__.py` | Orchestrator poll stage | `SQXPollCampaignStage` polls `CampaignStatus` only; optional LLM integration point |
| `sdk/quantlab/phase4/checkpoint.py` | Checkpoints | Phase-level only, orchestrator path only; could record monitor state |
| `sdk/quantlab/dsl/models.py` | `LLMConfig` | Reusable as-is for the monitor's LLM client |
| `sdk/quantlab/agents/llm_research_agent.py` | `call_llm` pattern | Reference implementation (OpenAI-compatible + circuit breaker) to mirror |

### Approaches

1. **Standalone `LLMGenerationMonitor` + heuristic fallback** (recommended)
   - New module `sdk/quantlab/sqx/llm_generation_monitor.py`; runs beside
     `CampaignMonitor` in the dispatch loop. Every N-th poll it builds a compact
     prompt from: status text, `-databank action=list` record counts, log tail
     (if present), campaign baseline (gens, population, timeframe, WF/MC,
     ranking criteria), and recent `WatcherEvent`s. LLM returns a strict JSON
     verdict: `{assessment, severity, detected_issues[], recommended_action:
     continue|stop|adjust|regenerate|abort, confidence, reasoning}`.
   - An `ActionExecutor` maps verdicts to real SDK actions: `continue` (no-op),
     `stop` (`action=stop`), `adjust/regenerate` (stop → copy databanks →
     rebuild `project.cfx` with relaxed criteria via `project_builder` → start),
     `abort` (stop + mark failed).
   - Safety rails: reuse `LLMCircuitBreaker`; confidence threshold before any
     action; human-confirm gate for `stop`/`abort` (already the CLI pattern);
     LLM runs on a slow cadence, heuristics every poll.
   - Pros: clean separation, LLM fully optional (heuristics keep working),
     testable with a mocked LLM.
   - Cons: new module + new action surface; SQX API limits what "adjust" can do.
   - Effort: **Medium** (Phase 1: continue/stop only — **Low**).

2. **Extend `CampaignMonitor` in place with an LLM tick**
   - Add an optional LLM callback to `_poll_tick` that enriches the heuristic
     decision with an LLM verdict before dispatching the event.
   - Pros: smallest diff, no new module, reuses existing poll cadence/events.
   - Cons: couples LLM to a watcher whose events are already coarse; harder to
     test the LLM path; no natural home for `adjust/regenerate` actions.
   - Effort: **Low-Medium**.

3. **New pipeline stage in the phase4 orchestrator**
   - Add `SQXMonitorStage` (or extend `SQXPollCampaignStage`) with LLM capacity
     inside the 11-stage pipeline; artifacts flow via `PipelineContext`.
   - Pros: consistent with the orchestrator architecture, checkpointable.
   - Cons: `CampaignOrchestrator` is not the path `_run_campaign.py`/builder
     uses today; bigger blast radius; checkpoint manager is phase-level.
   - Effort: **High**.

### Recommendation

**Approach 1, phased.** Build a standalone `LLMGenerationMonitor` that consumes
the same observability the heuristics use, adds `-databank action=list` polling
(the only live signal that reveals zero-acceptance during a run), and keeps the
existing `CampaignMonitor` as the always-on fallback. Wire it into
`cli_wrapper.dispatch_campaign` via a new optional hook, exactly like
`on_watcher_event` already works. This preserves the working path
(builder → cli_wrapper) and leaves the orchestrator path untouched.

Observability inventory the monitor can act on (all verified in the codebase):

- **Live, every poll**: status text (`Strategies generated: N`, `Running time
  so far`, `In databank N`, `Status:`); `-databank action=list` record counts
  (`Results, Records: N`); HTTP error prefixes in command responses.
- **At task end**: `user/projects/{campaign_id}/log/global_log_*.log` — the gold
  source for rejection reasons with per-filter counts (`Initial population
  filter: ...`, `Automatic filter: no trades`), accepted/rejected totals,
  databank before/after counts, duration.
- **On demand**: `-databank action=export` → CSVs; export paths under
  `user/projects/{campaign_id}/exports`, `user/settings/Exports/{campaign_id}`,
  `/tmp/sqx-exports/{campaign_id}`.
- **Config expectations**: `compute_baseline` already encodes what "normal"
  looks like (gen time, stall thresholds) — feed these into the LLM prompt.

Checkpoint reality: `CheckpointManager` is phase-level and only in the
orchestrator path; there is **no pause/resume API on the SQX side**
(only `action=start|stop|list|status`). "Pause" and "adjust parameters" must be
simulated as stop → rebuild `project.cfx` → start. Generation itself is not
resumable mid-run; databanks must be exported/copied before a rebuild destroys
them (`create_project` rmtree's the project dir).

### Risks

- **SQX API limits**: no pause, no live parameter mutation. "Adjust" is
  stop + rebuild + restart, which loses in-progress generation state unless
  databanks are copied first. `create_project` deletes the project dir.
- **Early-detection blind spot**: `global_log` is written at task finish; early
  detection must rely on status text + databank counts, not the log. Verify real
  `-databank action=list` output format against the mock (mock: `Results,
  Records: 3`; real server format must be confirmed during implementation).
- **Parser divergence**: three parsers already disagree on status text
  (`CampaignMonitor.extract_results_count` expects `Strategies generated  N`;
  `BuilderAgent._parse_status` expects `Strategies generated: N`). The monitor
  must parse defensively.
- **Alert fatigue**: real campaigns show 100 % rejection; the LLM will flag
  constantly. Needs baseline calibration, confidence gating, and
  human-confirm on destructive actions.
- **LLM latency/cost per poll**: keep LLM cadence slow (every N polls), reuse
  `LLMCircuitBreaker`, and fall back to heuristics on any LLM failure.
- **Mock realism**: mock status/databank text must simulate rejection for tests
  (e.g., counts that do not grow across generations).
- **Stop coordination**: the poll loop and the monitor both hit the HTTP API;
  LLM-initiated stop must use the same `monitor.cancel()` pattern to avoid
  races with the `finally` block in `_dispatch_real`.

### Ready for Proposal

Yes. Key facts for the orchestrator:

- Generation monitoring today = regex heuristics in `CampaignMonitor`
  (stall/error detection, stop-only action). `MonitoringAgent` is a
  live-trading monitor, not a generation monitor.
- Rich observability exists but is under-used: live status text + databank
  counts during the run; `global_log` rejection breakdown at task end.
- Real campaigns are producing **0 accepted strategies** — the exact failure an
  LLM monitor is meant to catch early.
- Recommended: standalone `LLMGenerationMonitor` (Approach 1), wired into
  `cli_wrapper.dispatch_campaign` like `on_watcher_event`, LLM verdicts
  constrained to `continue|stop` in Phase 1, `adjust|regenerate|abort` in
  Phase 2, `CampaignMonitor` heuristics retained as the always-on fallback.
