# Proposal: Reconfiguration Loop

## Intent

Add strategic reconfiguration to the campaign loop: after each iteration, ReviewerAgent ITERATE decisions trigger BuildConfig changes and a fresh SQX build, instead of only generating new hypotheses.

## Scope

### In Scope
- `ResearchDirector.apply_iteration_proposal()` — maps ReviewerAgent `parameter_changes` to `BuildConfig`
- `execute_campaign()` — branch on review decision: ITERATE → apply + rebuild; REJECT → abort; APPROVE → portfolio
- Versioned campaign IDs: `{campaign_id}_iter{02d}`
- Best-result tracking; abort on consecutive degradation
- Wire `IterationConfig.auto_iterate` into loop control
- Tests for proposal application, loop decisions, degradation abort

### Out of Scope
- Patch-and-reload (v2), LLM reconfiguration suggestions, cross-iteration strategy carryover, hypothesis generation changes

## Capabilities

> This section is the CONTRACT between proposal and specs phases.

### New Capabilities
- `campaign-reconfiguration`: reconfiguration loop with proposal application, versioned IDs, degradation tracking

### Modified Capabilities
- `campaign-orchestrator`: `execute_campaign()` branches on review_decision
- `research-dsl`: `IterationConfig.auto_iterate` becomes active loop-control flag

## Approach

Use existing `max_iterations` loop. After each iteration, invoke ReviewerAgent. ITERATE → `apply_iteration_proposal()` → fresh versioned build. Track best fitness; abort on consecutive degradation. REJECT aborts. APPROVE exits loop.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/agents/research_director.py` | Modified | execute_campaign branching; apply_iteration_proposal() |
| `sdk/quantlab/dsl/models.py` | Modified | auto_iterate wiring |
| `sdk/quantlab/agents/builder_agent.py` | Modified | versioned project dir support |
| `sdk/quantlab/cfx/patcher.py` | Used | BuildConfig mutation |
| `tests/phase5/test_reconfiguration_loop.py` | New | loop behavior and degradation tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Infinite loops | Low | max_iterations already enforced |
| Degrading results | Medium | Track best result; abort on consecutive degradation |
| Non-actionable changes | Medium | parameter_changes must map to valid BuildConfig fields |
| Gate bypass | Low | auto_iterate respects gate policies |

## Rollback Plan

Disable `auto_iterate` and revert `execute_campaign()` to current behavior. Versioned directories are additive.

## Dependencies

- ReviewerAgent returns structured `parameter_changes`
- BuildConfig mapping aligns with SQX `.cfx` schema

## Success Criteria

- [ ] ITERATE applies changes and launches versioned rebuild
- [ ] REJECT aborts cleanly
- [ ] APPROVE exits to portfolio
- [ ] Consecutive degradation triggers abort
- [ ] auto_iterate enables/disables loop
- [ ] All new tests pass

## Proposal question round

1. **Degradation threshold**: Abort after 2 or 3 consecutive bad iterations? Vary by strategy type?
2. **High-impact fields**: Should population/generations changes require confirmation when degradation is detected?
3. **Cleanup**: Retain or auto-delete old `_iterNN` directories after completion?
