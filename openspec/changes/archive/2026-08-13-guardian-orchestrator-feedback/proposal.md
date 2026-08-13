# Proposal: Guardian as First-Class Orchestration Agent with Bidirectional Feedback

## Intent

Guardian is a passive library subsystem (`sdk/quantlab/guardian/`, 6 guardians + `MetaGuardianOrchestrator`) run inline in campaign phase 14; feedback is one-directional data (`FeedbackRecord` → archive → next cycle). Make it a first-class `quantlab-guardian` subagent with bidirectional feedback: orchestrator → guardian directives; guardian → orchestrator reports.

## Scope

### In Scope
- Add `quantlab-guardian` to `~/.config/opencode/opencode.json`; GUARDIAN route in `orchestrator.md`; task permission on `quantlab-orchestrator`.
- Feedback envelope: guardian → orchestrator returns `guardian_state` + `FeedbackRecord` (`next_cycle_inputs()`, REQ-34); orchestrator → guardian directives (evaluate, live-ops status, escalation ack).
- Phase 14 in `campaign.md` delegates the Guardian flow to the agent.
- Tests for `FeedbackRecord`, `GuardianEvaluationAgentStage`, `LiveOpsStage`.

### Out of Scope
- No new pipeline phase — `PHASES` stays 14 (REQ-37).
- No changes to guardian modules, state machine, or thresholds.
- No auto-approval/reorder — human gates untouched (REQ-34).
- No new escalation transport — reuse `ops_surface` (REQ-36).

## Capabilities

### New Capabilities
- `guardian-agent`: `quantlab-guardian` subagent — identity, routing, permissions, directive intake, report envelope (`guardian_state` + `FeedbackRecord`).

### Modified Capabilities
- `guardian-feedback` (REQ-34): extend to a bidirectional agent-boundary envelope — guardian reports via the Result Contract; orchestrator sends directives — staying pure/additive. Canonical; no duplication of REQ-40.

## Approach

Hybrid (exploration approach 3): add agent + GUARDIAN route (dispatch via `task` like campaign/monitor); build directive/report payloads on `FeedbackRecord`/`next_cycle_inputs()`; reuse `ops_surface` for escalation ack. Guardian wraps `guardian_evaluate`/`live-ops`; `flow.py` untouched.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `~/.config/opencode/opencode.json` | Modified | agent + task permission |
| `~/.config/opencode/prompts/quantlab/orchestrator.md` | Modified | GUARDIAN route |
| `~/.config/opencode/prompts/quantlab/campaign.md` | Modified | phase 14 delegates |
| `sdk/quantlab/guardian/feedback.py` | Modified | directive/report envelope (additive) |
| `sdk/quantlab/guardian/live.py` | Modified | agent entry over `evaluate_live` |
| `sdk/quantlab/pipeline/stages/agent_stages.py` | Modified | agent path + tests |
| `sdk/quantlab/pipeline/stages/live_ops_stage.py` | Modified | `live_ops_status` feeds report |
| `sdk/quantlab/campaign/flow.py` | Unchanged | `PHASES` stays 14 (REQ-37) |
| `sdk/quantlab/agents/ops_surface.py` | Unchanged | escalation ack reuse |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| 15th phase → `FlowIntegrityError` | Med | agent wrapper only; integrity test asserts 14 |
| Spec fragmentation (3 specs) | Med | canonical `guardian-feedback`; no REQ-34/40 duplication |
| Directive channel bypasses gates | Med | bounded to evaluate + advice (REQ-34) |
| Untested surface | Med | covering tests for record + both stages |
| Uncommitted `live.py` widening | Low | assume; flag at apply |

## Rollback Plan

Revert agent block, routing table, and campaign.md phase 14 (git revert) restores the inline flow. Envelope additions are additive — removable without migration. No `PHASES`/schema change.

## Dependencies

Existing: `FeedbackRecord` (REQ-34), `ops_surface` (REQ-36), `AutonomousMonitorDaemon` (REQ-41), `MetaGuardianOrchestrator`, plus `task` delegation from `quantlab-orchestrator`.

## Assumptions

Auto mode. Canonical target `guardian-feedback`. Uncommitted `live.py` Iterable widening assumed in scope.

## Success Criteria

- [ ] GUARDIAN intents route to `quantlab-guardian` via `task`
- [ ] Report delivers `guardian_state` + `FeedbackRecord`; directives processed; escalation ack round-trips `ops_surface`
- [ ] `assert_flow_integrity` passes — `PHASES` still 14
- [ ] Tests for `FeedbackRecord`, `GuardianEvaluationAgentStage`, `LiveOpsStage` pass