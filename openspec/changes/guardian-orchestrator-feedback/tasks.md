# Tasks: Guardian as First-Class Orchestration Agent with Bidirectional Feedback

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~450–550 (additions + deletions) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (SDK envelope + agent glue) → PR 2 (orchestration surface) |
| Delivery strategy | auto-chain |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | SDK envelope: `feedback.py` dataclasses, `agent.py` glue, stage behavior tests | PR 1 | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q sdk/tests/test_guardian/test_guardian_agent.py tests/guardian/test_feedback.py sdk/tests/test_pipeline_agent_stages.py --tb=short` | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -c "import asyncio; from quantlab.guardian.agent import execute_guardian_directive; from quantlab.guardian.feedback import GuardianDirective; print(asyncio.run(execute_guardian_directive(GuardianDirective(kind='evaluate', campaign_id='x'))))"` — real evaluate directive over mock stream | Revert `feedback.py`, delete `agent.py`, revert tests — additive, no migration, no `PHASES` touch |
| 2 | Orchestration surface: `quantlab-guardian` agent, GUARDIAN route, phase 14 delegation | PR 2 | `python3 -m json.tool ~/.config/opencode/opencode.json` + routing/config static asserts | Real orchestrator dispatch: opencode chat intent routes to `quantlab-guardian` via `task`; GUARDIAN row rendered | `git revert` of `opencode.json`, `guardian.md`, `orchestrator.md`, `campaign.md` restores inline phase 14 |

## Phase 1: Envelope + Agent RED Tests (threat matrix)

- [x] 1.1 RED `tests/guardian/test_feedback.py`: `GuardianDirective` unknown kind raises `ValueError` pre-execution; report has no gate/flow fields (boundedness, REQ-643)
- [x] 1.2 RED `tests/guardian/test_feedback.py`: `build_report()` reuses `next_cycle_inputs()` — degradation/drawdown/regime/cost/param deltas (REQ-34)
- [x] 1.3 RED `sdk/tests/test_guardian/test_guardian_agent.py`: ack round-trip `ops_surface.ack()`; unknown id → `None` surfaced, never fabricated (ack integrity, REQ-36)
- [x] 1.4 RED `sdk/tests/test_guardian/test_guardian_agent.py`: evaluate → report carries `guardian_state` + `FeedbackRecord`; empty points → `feedback=None`, state still carried (REQ-644 s1/s2)
- [x] 1.5 RED `sdk/tests/test_guardian/test_guardian_agent.py` + `tests/campaign/test_flow_segments.py`: post-run `len(PHASES)==14`, `STAGE_FOR_PHASE`/registry unchanged, no gate import (REQ-37)

## Phase 2: SDK Production (GREEN)

- [x] 2.1 `sdk/quantlab/guardian/feedback.py`: add frozen `GuardianDirective` (kind `evaluate|live_ops_status|escalation_ack`), `GuardianReport`, `build_report()` — additive pure
- [x] 2.2 `sdk/quantlab/guardian/agent.py` (new): `execute_guardian_directive()` wrapping `GuardianEvaluationAgentStage.execute(ctx)`, `LiveOpsStage.execute(ctx)` (fail-closed without `archive_bundle`), `ops_surface.ack()`
- [x] 2.3 `sdk/tests/test_pipeline_agent_stages.py`: behavior test — `GuardianEvaluationAgentStage.execute()` produces `guardian_state`

## Phase 3: Routing + Delegation RED Tests (threat matrix)

- [x] 3.1 RED routing-table test: GUARDIAN intents map to `quantlab-guardian`; non-guardian intents do NOT; unknown kind rejected (routing authority, REQ-642)
- [x] 3.2 RED config-parse test: `opencode.json` registers agent; `"*":"deny"` first; explicit `"quantlab-guardian":"allow"` on orchestrator task (delegation ownership)

## Phase 4: Orchestration Surface Production (GREEN)

- [x] 4.1 Create `~/.config/opencode/prompts/quantlab/guardian.md`: directive intake, report envelope, ack via ops_surface, NO-phase rule
- [x] 4.2 Modify `~/.config/opencode/opencode.json`: add `quantlab-guardian` agent (campaign pattern incl. task allowlist); orchestrator task explicit allow
- [x] 4.3 Modify `~/.config/opencode/prompts/quantlab/orchestrator.md`: GUARDIAN route — dispatch via `task`; non-guardian stays with orchestrator
- [x] 4.4 Modify `~/.config/opencode/prompts/quantlab/campaign.md`: phase 14 delegates Guardian flow to agent; folds `GuardianReport`; gates/`PHASES` untouched

## Phase 5: Verification / Cleanup

- [ ] 5.1 Flow-integrity assertion: after full agent run, `assert_flow(PHASES)` passes; `PHASES` still 14; no `campaign/flow.py` edit (REQ-37)
- [ ] 5.2 Full suite: `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q sdk/tests/test_guardian/ sdk/tests/test_pipeline_agent_stages.py tests/guardian/ tests/pipeline/test_live_ops_stage.py tests/campaign/test_flow_segments.py --tb=short`
- [ ] 5.3 Validate `opencode.json` parses; confirm `guardian.md`/`orchestrator.md`/`campaign.md` unchanged except intended rows
