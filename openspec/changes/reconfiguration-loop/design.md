# Design: Reconfiguration Loop

## Technical Approach

Extend `ResearchDirector.execute_campaign()` to branch on `review_decision` after each iteration. When `auto_iterate=True` and the decision is `ITERATE`, invoke `apply_iteration_proposal()` to map the ReviewerAgent's semantic `parameter_changes` to a new `BuildConfig`, then run a fresh versioned build in a sub-directory. Track the best result across iterations; abort on consecutive degradation (threshold: 2). `REJECT` aborts immediately. `APPROVE` exits the loop to portfolio. The existing `max_iterations` loop, `propose_next_cycle()`, and `check_convergence()` remain untouched.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Versioned ID generation in ResearchDirector | Centralizes loop state; builder receives ID via context. Alternative: builder generates its own ID → loses traceability to parent iteration. | **ResearchDirector** generates `f"{base_id}_iter{iteration:02d}"` and injects it into `PipelineContext.config["campaign_id"]`. |
| parameter_changes mapping location | Direct mapping in ResearchDirector vs patcher-based mutation of archived CFX. Direct mapping is deterministic and testable; patcher requires archive round-trip. | **Direct mapping in `apply_iteration_proposal()`** on `BuildConfig` fields. Patcher is out of scope for v1. |
| Best-result metric | `selected_strategies` count vs aggregate score vs custom fitness. Count is already in context; aggregate score requires additional computation. | **`selected_strategies` count** (len of list in context artifacts). Fallback to `aggregate_stats` mean when count is empty. |
| Degradation threshold | 2 or 3 consecutive worse iterations. Higher threshold risks wasted compute; 2 is enough signal. | **2 consecutive worse** iterations trigger abort, per spec. |
| auto_iterate default | True (loop enabled) vs False (preserve legacy). Default True matches proposal; users can opt out. | **`auto_iterate=True`** in `IterationConfig` (already modeled). |

## Data Flow

```
execute_campaign(base_id)
  │
  ├─ cid = base_id (iter 0) or f"{base_id}_iter{iteration:02d}"
  ├─ inject cid into PipelineContext.config["campaign_id"]
  │
  └─ for iteration in range(max_iterations):
       ├─ build_pipeline(current_config)
       ├─ run pipeline [research → builder → monitor → statistics → analysis → review]
       │
       ├─ read review_decision from ctx.artifacts["review_decision"]
       │
       ├─ ITERATE + auto_iterate:
       │   ├─ extract parameter_changes from iteration_proposal
       │   ├─ apply_iteration_proposal(parameter_changes, build_config) → new BuildConfig
       │   ├─ inject new BuildConfig into current_config (hypotheses + build overrides)
       │   ├─ track best result (selected_strategies count)
       │   ├─ check consecutive degradation: 2+ worse → state=CONVERGED, return best
       │   └─ continue (next iteration)
       │
       ├─ REJECT → state=FAILED, return record
       │
       ├─ APPROVE → break loop, proceed to portfolio
       │
       └─ max_iterations reached → state=COMPLETED, return best
```

```
ResearchDirector ──► PipelineContext ──► BuilderAgent
     │                       │                    │
     │                campaign_id           dispatches with
     │                (versioned)           versioned project dir
     │                       │                    │
     │                       │               create_project(
     │                       │                 campaign_id=versioned_id,
     │                       │                 build_config=mutated)
     │                       │                    │
     └───────────────────────┴────────────────────┘
                     SQX user/projects/{versioned_id}/
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/research_director.py` | Modify | Add `apply_iteration_proposal()`; branch `execute_campaign()` on `review_decision`; versioned ID injection; best-result tracking; degradation abort |
| `sdk/quantlab/agents/builder_agent.py` | Modify | Read versioned `campaign_id` from `context.config` before generating UUID; use it for project directory and dispatch |
| `sdk/quantlab/dsl/models.py` | No change | `IterationConfig.auto_iterate` already exists (line 234) |
| `sdk/quantlab/sqx/project_builder.py` | Modify (minor) | `BuildConfig` gained `generations`/`population` fields + 2 `_BUILD_CONFIG_MAP` entries (+12 lines) — spec-required for `position_size`→`population` & `generations` mapping. `create_project()` signature unchanged. Corrected at archive per verify-report warning #1 (design originally claimed "No change"). |
| `tests/phase5/test_reconfiguration_loop.py` | New | Loop behavior, degradation abort, proposal application, versioned IDs |

## Interfaces / Contracts

### `apply_iteration_proposal(parameter_changes: dict, build_config: BuildConfig) -> BuildConfig`

Maps ReviewerAgent semantic keys to `BuildConfig` fields. Returns a new `BuildConfig` instance (immutable operation on the input).

**Known mappings** (others → warning + skip):

| Semantic key | Value pattern | Maps to BuildConfig field(s) | Transformation |
|--------------|---------------|------------------------------|----------------|
| `position_size` | `"0.5x"` / `"2.0x"` | `population` | Multiply current by factor |
| `generations` | `"increase"` / `"decrease"` / int | `generations` | +20 / -20 or direct int |
| `ranking_type` | `"ReturnDDRatio"` / `"Fitness"` | `ranking_type` | Direct string |
| `ranking_conditions_type` | int string | `ranking_conditions_type` | Direct int |
| `min_conditions` | int | `min_conditions` | Direct int |
| `max_conditions` | int | `max_conditions` | Direct int |
| `sl_required` | `"tighter"` | `sl_required=True`, `sl_fixed_pips=True`, `min_sl_pips=10`, `max_sl_pips=30` | Composite |
| `pt_required` | `"2.0x"` | `pt_required=True`, `pt_fixed_pips=True`, `min_pt_pips=20` | Composite |
| `parameter_space` | `"reduce"` | `islands=1`, `decimation_coef=2` | Composite |
| `wf_optimization` | `"increase"` / `"decrease"` | `wf_optimization` | +2 / -2 (clamped to ≥1) |

**Error handling within the function**:
- `parameter_changes` is empty → return input `build_config` unchanged (caller logs warning)
- Unknown key → `logger.warning("Unknown parameter_change key: %s", key)`; skip
- Invalid value type for known key → warning + skip that key
- All keys skipped → return input `build_config` unchanged

### Loop State Tracking

Stored in `CampaignRecord`:

```python
@dataclass
class CampaignRecord:
    # ... existing fields ...
    best_result_score: float = 0.0          # selected_strategies count or aggregate score
    best_result_iteration: int = 0          # which iteration achieved best
    best_result_config: Any = None          # BuildConfig snapshot of best iteration
    consecutive_worse_count: int = 0        # resets on improvement
```

## Error Handling Chain

| Failure | Handling |
|---------|----------|
| `parameter_changes` empty | Warning log; continue with previous `BuildConfig` (no rebuild params changed) |
| Unknown parameter key | Warning per key; skip; continue with remaining keys |
| `BuildConfig` validation failure | `apply_iteration_proposal()` never raises — all failures are warnings + skip. Caller always gets a valid `BuildConfig`. |
| BuildConfig → CFX translation failure | Propagates up from builder; `execute_campaign()` catches as iteration failure → `record.state=FAILED` → return |
| Max iterations reached | `state=COMPLETED`; return `CampaignRecord` with `best_result_*` populated |
| Degradation abort | `state=CONVERGED`; log degradation details; return best result |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `apply_iteration_proposal()` known mappings | Parametrized: input dict → expected BuildConfig fields; assert exact values |
| Unit | `apply_iteration_proposal()` unknown keys | Unknown key → warning logged; known keys still applied |
| Unit | `apply_iteration_proposal()` empty input | Empty dict → return input unchanged |
| Integration | ITERATE branch | Mock reviewer returns `ITERATE` + `parameter_changes`; assert versioned build launched with mutated BuildConfig |
| Integration | REJECT branch | Mock reviewer returns `REJECT`; assert `state=FAILED`, loop aborts |
| Integration | APPROVE branch | Mock reviewer returns `APPROVE`; assert loop exits, `state=COMPLETED` |
| Integration | Degradation abort | Run loop with alternating worse/better results; assert abort after 2 consecutive worse |
| Integration | auto_iterate=False | Single iteration; no reconfiguration regardless of review_decision |
| E2E | Full loop with mock SQX | Spin up mock SQX server; execute 2-iteration loop; assert versioned project dirs exist at `user/projects/{base_id}_iter00`, `{base_id}_iter01` |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary introduced. The reconfiguration loop operates within the existing `execute_campaign()` async flow and reuses the builder's established dispatch mechanism.

## Migration / Rollout

No migration required. Versioned directories are additive. Rollback: set `auto_iterate=False` in `IterationConfig`; `execute_campaign()` reverts to single-iteration behavior. Existing versioned `_iterNN` directories can be removed manually or via the existing `remove_project()` utility.

## Open Questions

- [ ] Should `position_size: "0.5x"` map to `population` (genetic algorithm size) or to a `mm_lot_size` change (money management)? Current design maps to `population` as the primary knob for search breadth.
- [ ] Should degradation metric use `selected_strategies` count (discrete) or a composite score from `aggregate_stats`? Current design uses count with aggregate fallback; can be swapped without interface change.
- [ ] Do we need a `cleanup_old_iterations` flag in `IterationConfig` for auto-deletion? Current design retains all directories.
