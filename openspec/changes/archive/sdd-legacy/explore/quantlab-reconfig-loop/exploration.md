# Exploration: Reconfiguration Loop for QuantLab AI Pipeline

## Current State

### Existing Iteration Loop (Research-Only)
`ResearchDirector.execute_campaign()` **already has an iteration loop** (`research_director.py:312-418`):
- Loops up to `max_iterations` (default 5, max 50)
- Checks convergence via Sharpe improvement threshold + patience
- Calls `propose_next_cycle()` to add new hypotheses between iterations
- **BUT this is a RESEARCH loop** (hypotheses → building blocks → strategies), NOT a build reconfiguration loop

### Builder Retry Logic (Transient Failures Only)
`BuilderAgent._dispatch_with_retry()` (`builder_agent.py:335-399`) retries on:
- `timeout` status
- `failed` status
- `asyncio.TimeoutError`
- Uses exponential backoff (2^attempt * 10s, max 120s)
- **This is NOT strategic reconfiguration** — it's blind retry on transient SQX failures

### LLM Monitor Stop Logic
`LLMGenerationMonitor` (`llm_generation_monitor.py:359-544`) can stop a campaign early based on LLM verdict, but:
- Does NOT trigger reconfiguration
- Does NOT feed back into the build loop
- Only executes stop action via `ActionExecutor`

---

## Affected Areas

| File | Why Affected |
|------|--------------|
| `sdk/quantlab/agents/research_director.py` | Has the outer iteration loop, but only modifies hypotheses. Needs to also modify SQX build config. |
| `sdk/quantlab/agents/builder_agent.py` | Dispatches to SQX but has no reconfiguration logic. Needs to support patch-and-reload or configurable rebuild. |
| `sdk/quantlab/sqx/project_builder.py` | `create_project()` always recreates from template (deletes existing dir). Needs patch-existing-project path or versioned project dirs. |
| `sdk/quantlab/cfx/patcher.py` | `CfxPatcher` can modify existing CFX projects but is NOT wired into the pipeline loop. Key capability for reconfiguration. |
| `sdk/quantlab/dsl/models.py` | `IterationConfig` has `auto_iterate` field (unused). `BuildConfig` has 100+ reconfigurable fields. |
| `sdk/quantlab/agents/reviewer_agent.py` | `evaluate()` returns ITERATE/REJECT. `generate_iteration_proposal()` creates `parameter_changes` + `new_hypotheses`. Decision logic exists but doesn't trigger build reconfiguration. |
| `sdk/quantlab/agents/analysis_agent.py` | Produces `selected_strategies`, `strategy_verdicts`, `wf_cycles`. These feed into review decisions but don't trigger reconfiguration. |
| `sdk/quantlab/sqx/cli_wrapper.py` | `_dispatch_real()` always calls `create_project()` fresh. Would need to support loading existing project CFX. |

---

## What Can Be Reconfigured in SQX

### Via `create_project()` params (full rebuild)
- **Genetic**: `generations`, `population`, `crossover`, `mutation`
- **Rankings**: `rankings_min_profit_factor`, `rankings_min_return_dd`, `rankings_min_avg_trades`
- **Walk-forward/MC**: `walk_forward`, `monte_carlo`
- **BuildConfig** (100+ fields via `_BUILD_CONFIG_MAP`):
  - Trading session (EOD exit, time ranges, max trades)
  - Rules complexity (min/max conditions, periods, shifts)
  - Market sides (long/short/both, symmetry)
  - SL/PT options (fixed pips, ATR, percent, RRR limits)
  - BuildMode genetic (islands, migration, decimation, fresh blood, restart)
  - Rankings (max strategies, ranking type, conditions)
  - Money management (method, lot size, capital, risk %, max drawdown)
  - ATMs (enable, scale out, size decimals)
  - PartsToImprove (entry/exit symmetry, long/short improvement)
  - CrossChecks internals (WF period/optimization, acceptance thresholds, RC settings)

### Via `CfxPatcher` (patch existing project)
Supported instruction types:
- `set_market`, `add_timeframe`
- `enable_block`, `disable_block`
- `set_genetic`, `set_date_range`
- `add_ranking_condition`
- `enable_crosscheck`
- `set_automatic_portfolio_builder`, `set_portfolio_settings`
- `set_optimization`, `set_optimization_parameters`
- `set_walkforward`, `set_databanks`, `set_rankings`, `set_crosschecks`
- `set_retester_data`

**Limitation**: Patcher modifies `SettingsSection` objects and some raw XML. Complex sections like `blocks`, `atms`, `resources` are stored as `raw_xml` and would need XML parsing for full modification.

### What CANNOT be reconfigured
- Changing the engine (always MetaTrader4)
- Fundamental data source changes without recreating project
- Some complex XML sections without full CFX rewrite

---

## Approaches

### 1. Full Rebuild Every Iteration (Simple, Safe)
**Description**: Each iteration calls `create_project()` with modified config. Deletes and recreates project dir.

| Pros | Cons | Effort |
|------|------|--------|
| Simple — no patching complexity | Loses SQX internal state (databanks, last gen) | Low |
| Always starts from clean template | Slower — full project creation each time | |
| No patcher bugs to debug | Cannot carry over accepted strategies as "existing portfolio" | |
| Easy to reason about | | |

### 2. Patch-and-Reload (Faster, Complex)
**Description**: Use `CfxPatcher` to modify existing project CFX, then reload via `loadconfig` instead of recreating.

| Pros | Cons | Effort |
|------|------|--------|
| Faster — no full project recreation | Patcher coverage is incomplete (raw_xml sections) | High |
| Preserves some SQX state | More failure modes (patch errors, stale state) | |
| Can carry over "existing portfolio" strategies | Need to validate patched CFX before dispatch | |

### 3. Versioned Project Dirs (Hybrid)
**Description**: Create versioned project dirs (`campaign_v1`, `campaign_v2`, ...). Each iteration creates a new dir with modified config, but can reference previous dir's databanks/exports.

| Pros | Cons | Effort |
|------|------|--------|
| Clean separation between iterations | Uses more disk space | Medium |
| Can reference previous results | Need to manage multiple project dirs | |
| No patching complexity | | |

---

## Recommendation

**Approach 1 (Full Rebuild)** for the first implementation, with **Approach 3** as the directory naming strategy.

**Rationale**:
1. `create_project()` already handles all reconfiguration via params and `BuildConfig`
2. The patcher is incomplete for complex sections (blocks, ATMs, resources)
3. Full rebuild is deterministic and easy to debug
4. The 5-50 iteration limit means disk usage is bounded
5. We can add versioned dirs (`campaign_iter01`, `campaign_iter02`) to preserve previous results for comparison

---

## Proposed Architecture: Reconfiguration Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    ResearchDirector                             │
│                                                                 │
│  execute_campaign(config)                                       │
│    │                                                             │
│    ├─ for iteration in max_iterations:                          │
│    │   ├─ build_pipeline(current_config)                        │
│    │   ├─ run pipeline                                          │
│    │   │   ┌──────────────────────────────────────┐             │
│    │   │   │ Pipeline:                             │             │
│    │   │   │ research → builder → statistics       │             │
│    │   │   │     → analysis → review               │             │
│    │   │   │     → portfolio → deploy → monitor    │             │
│    │   │   └──────────────────────────────────────┘             │
│    │   │                                                         │
│    │   ├─ IF review_decision == ITERATE:                        │
│    │   │   ├─ Extract parameter_changes from iteration_proposal  │
│    │   │   ├─ Apply changes to current_config:                   │
│    │   │   │   ├─ generations, population, crossover, mutation   │
│    │   │   │   ├─ rankings thresholds                            │
│    │   │   │   ├─ BuildConfig fields (SL/PT, WF, MC, etc.)      │
│    │   │   │   └─ Add new_hypotheses from proposal               │
│    │   │   └─ continue to next iteration                         │
│    │   │                                                         │
│    │   ├─ IF review_decision == REJECT:                         │
│    │   │   └─ abort campaign                                     │
│    │   │                                                         │
│    │   ├─ IF review_decision == APPROVE:                        │
│    │   │   └─ continue to portfolio/deploy                       │
│    │   │                                                         │
│    │   └─ check_convergence()                                    │
│    │       └─ IF converged: return CONVERGED                     │
│    └─────────────────────────────────────────────────────────────│
```

### Key Changes Needed

1. **New method: `ResearchDirector.apply_iteration_proposal()`**
   - Takes `iteration_proposal` dict + `current_config`
   - Maps `parameter_changes` to `ResearchConfig` fields
   - Applies changes to generations, population, rankings, BuildConfig
   - Appends `new_hypotheses` to config

2. **Modify `execute_campaign()` loop** (`research_director.py:403-412`)
   - After pipeline run, check `review_decision` from context
   - If ITERATE and `auto_iterate=True`, call `apply_iteration_proposal()`
   - If REJECT, abort with `CampaignState.REJECTED`
   - If APPROVE, break loop and proceed to portfolio/deploy

3. **Versioned project dirs in `cli_wrapper.py`**
   - Change `campaign_id` to include iteration suffix: `{campaign_id}_iter{02d}`
   - Each iteration gets a fresh project dir but can reference previous exports

4. **New `ReconfigurationLoop` class** (optional, for testability)
   - Encapsulates the decision → reconfigure → rebuild logic
   - Can be tested independently of the full pipeline

---

## File Paths That Would Need to Change

| File | Change |
|------|--------|
| `sdk/quantlab/agents/research_director.py` | Add `apply_iteration_proposal()`, modify `execute_campaign()` to branch on review_decision |
| `sdk/quantlab/agents/reviewer_agent.py` | Add `should_iterate()` helper, ensure `parameter_changes` maps to SQX config fields |
| `sdk/quantlab/dsl/models.py` | Add `reconfiguration_policy` to `IterationConfig` (optional) |
| `sdk/quantlab/sqx/cli_wrapper.py` | Support versioned campaign IDs, optionally load existing project instead of creating fresh |
| `sdk/quantlab/sqx/project_builder.py` | Add `patch_project()` path (future) or support loading existing project CFX |
| `sdk/quantlab/cfx/patcher.py` | Extend patcher coverage for remaining raw_xml sections (blocks, ATMs, resources) |

---

## Risks and Edge Cases

1. **Infinite Loops**
   - Risk: ITERATE decision triggers loop that never converges
   - Mitigation: `max_iterations` hard limit (already exists, max 50). Add `rejection_threshold` — if selected_strategies count < N for M consecutive iterations, abort.

2. **Degrading Results**
   - Risk: Reconfiguration makes results worse
   - Mitigation: Track best result across iterations. If current < best - threshold, revert to best config.

3. **Stale SQX State**
   - Risk: Full rebuild loses SQX internal state (databanks, caches)
   - Mitigation: Acceptable for first implementation. Future: patch-and-reload.

4. **Non-actionable Parameter Changes**
   - Risk: `generate_iteration_proposal()` returns changes that don't map to SQX config
   - Mitigation: Create explicit mapping dict between proposal changes and `ResearchConfig`/`BuildConfig` fields.

5. **Reviewer Gate Bypass**
   - Risk: `HUMAN_APPROVE_ITERATION` gate auto-approves in test mode, causing uncontrolled loops
   - Mitigation: In `auto_iterate=True` mode, respect `auto_approve_on_timeout` policy. Require explicit human approval when `required=True`.

6. **Project Dir Collisions**
   - Risk: Two campaigns with same ID overwrite each other
   - Mitigation: Versioned dirs (`{campaign_id}_iter{02d}`) + timestamp suffix for parallel runs.

---

## Suggested First Implementation Scope

### Phase 1: Core Reconfiguration Loop (Minimal)
1. Add `ResearchDirector.apply_iteration_proposal()` that maps reviewer's `parameter_changes` to `BuildConfig` fields
2. Modify `execute_campaign()` to check `review_decision` after each iteration:
   - ITERATE → apply proposal → next iteration
   - REJECT → abort
   - APPROVE → proceed
3. Use versioned campaign IDs in `cli_wrapper.py` (`{base_id}_iter{02d}`)
4. Add unit tests for `apply_iteration_proposal()` with common parameter changes

### Phase 2: Carry-over State
1. Pass `selected_strategies` from previous iteration as `existing_portfolio` input to next build
2. In `project_builder.py`, support populating `Existing portfolio` databank from previous results

### Phase 3: Adaptive Thresholds
1. Track best result across iterations
2. If 2+ consecutive iterations degrade, abort early
3. Adjust `BuildConfig` based on overfit flags (reduce parameter space when WF degradation detected)

### Phase 4: Patch-and-Reload (Optional)
1. Extend `CfxPatcher` coverage for remaining raw_xml sections
2. Add `patch_project()` path in `project_builder.py`
3. Support in `cli_wrapper.py` for faster iteration

---

## Ready for Proposal

**Yes** — the architecture is clear. The core loop already exists in `ResearchDirector.execute_campaign()`. We need to:
1. Wire the review decision into the loop (currently it just runs all iterations blindly)
2. Map `iteration_proposal.parameter_changes` to SQX config fields
3. Use versioned project dirs to avoid collisions

The first implementation scope is small (~2-3 files, ~200 lines) and builds on existing, tested infrastructure.
