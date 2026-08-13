# Apply Progress — Guardian Orchestrator Feedback (PR 1 slice)

**Change**: guardian-orchestrator-feedback
**Phase**: sdd-apply — PR 1 (stacked-to-main, `delivery_strategy=auto-chain`)
**Mode**: Standard (`strict_tdd: false` per `openspec/config.yaml`) — RED-first per tasks within the slice
**Date**: 2026-08-13
**Branch**: `feat/guardian-orchestrator-feedback-pr1` (off `main` a79c5a9)

## Slice Scope

PR 1 = work unit 1 (sdd-tasks split): SDK envelope + agent glue + RED tests.
PR 2 (work unit 2: orchestration surface — `guardian.md`, `opencode.json`, routing, phase 14) is **NOT** touched.

## Completed Tasks

### Phase 1 — RED Tests (threat matrix)

- [x] 1.1 `GuardianDirective` unknown kind raises `ValueError` pre-execution; report has no gate/flow fields (boundedness, REQ-643) — `TestGuardianDirective` + `TestGuardianReportBoundedness` in `tests/guardian/test_feedback.py`
- [x] 1.2 `build_report()` reuses `next_cycle_inputs()` — degradation/drawdown/regime/cost/param deltas (REQ-34) — `TestBuildReport`
- [x] 1.3 ack round-trip `ops_surface.ack()`; unknown id → `None` surfaced, never fabricated (REQ-36) — `TestEscalationAck` in `sdk/tests/test_guardian/test_guardian_agent.py`
- [x] 1.4 evaluate → report carries `guardian_state` + `FeedbackRecord`; empty points → `feedback=None`, state still carried (REQ-644 s1/s2) — `TestEvaluateDirective` incl. no-transition case + hold fail-closed `live_ops_status`
- [x] 1.5 post-run `len(PHASES)==14`, `STAGE_FOR_PHASE`/registry unchanged, no gate import (REQ-37) — `TestFlowIntegrityAfterRun` + `TestAgentRunFlowIntegrity` in `tests/campaign/test_flow_segments.py`

### Phase 2 — GREEN Production

- [x] 2.1 `sdk/quantlab/guardian/feedback.py`: frozen `GuardianDirective` (`evaluate|live_ops_status|escalation_ack` + `__post_init__` `ValueError`), `GuardianReport`, `build_report()` — additive pure, no gate machinery
- [x] 2.2 `sdk/quantlab/guardian/agent.py` (new): `execute_guardian_directive()` wrapping `GuardianEvaluationAgentStage.execute(ctx)` and `LiveOpsStage.execute(ctx)` (hold fail-closed without `archive_bundle`), `ops_surface.ack()` round-trip; `ValueError` guard pre-execution
- [x] 2.3 `sdk/tests/test_pipeline_agent_stages.py`: behavior test — `GuardianEvaluationAgentStage.execute()` produces `guardian_state`

## RED → GREEN Evidence (standard mode, RED-first per tasks)

| Task | RED (test run before production) | GREEN (production in place) |
|---|---|---|
| 1.1/1.2/2.1 | `ImportError: cannot import name 'GuardianDirective'` — collection error (1 error) | `22 passed` (module incl. 8 new envelope tests) |
| 1.3/1.4/2.2 | collection error — `quantlab.guardian.agent` missing; then 8 failed (async not natively supported before marker fix) | `9 passed` in `test_guardian_agent.py` |
| 1.5/2.3 | agent run integrity tests collected with agent file (RED via import) | full focused suite `71 passed` |

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command + result | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q sdk/tests/test_guardian/test_guardian_agent.py tests/guardian/test_feedback.py sdk/tests/test_pipeline_agent_stages.py tests/campaign/test_flow_segments.py --tb=short` → **71 passed** (1.89s) |
| Runtime harness command/scenario + result | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -c "import asyncio; from quantlab.guardian.agent import execute_guardian_directive; from quantlab.guardian.feedback import GuardianDirective; print(asyncio.run(execute_guardian_directive(GuardianDirective(kind='evaluate', campaign_id='x'))))"` → real evaluate directive over mock stream returns `GuardianReport(guardian_state={'portfolio_state': 'QUARANTINE', 'state_history': [...], 'strategy_states': {}}, feedback=None, live_ops_status=None, escalations_acked=())` |
| Regression sweep | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q sdk/tests/test_guardian/ tests/pipeline/test_live_ops_stage.py` → **66 passed** (no collateral damage; guardian dir + live-ops stage intact) |
| Rollback boundary | Revert `5d45dcb` + `5309d3b` (or revert `feedback.py` + delete `agent.py` + revert the 4 test files). Additive: no migration, no `PHASES`/`flow.py`/`live.py`/`ops_surface.py` edit. Unrelated working-tree changes untouched (only 6 slice files staged). |

## Commits (PR 1)

| SHA | Message |
|---|---|
| `5d45dcb` | `feat(guardian): add GuardianDirective/GuardianReport envelope + build_report (PR1)` — feedback.py + tests/guardian/test_feedback.py (220 insertions) |
| `5309d3b` | `feat(guardian): add execute_guardian_directive agent glue (PR1)` — agent.py + test_guardian_agent.py + test_pipeline_agent_stages.py + test_flow_segments.py (417 insertions) |
| (next) | `chore(sdd): mark guardian-orchestrator-feedback PR1 tasks complete (PR1)` — tasks.md + apply-progress.md |

## Deviations from Design

1. **`asyncio_mode = auto` ineffective in this environment**: `pytest.ini` sets `asyncio_mode = auto`, but with pytest 9.1.1 + pytest-asyncio 1.4.0 bare `async def` tests error ("not natively supported"), while `@pytest.mark.asyncio` works. Repo convention is already explicit markers (205/205 async tests marked) — all new async tests use `@pytest.mark.asyncio` to match. No production deviation.
2. **`live_ops_status` without `archive_bundle` always holds** (fail-closed): the agent glue runs `LiveOpsStage.execute(ctx)` with no bundle → status `hold`. This is the design's stated behavior (design.md "hold fail-closed w/o archive_bundle"); feeding a real `archive_bundle` into the directive is left to the orchestration surface (PR 2) / design open question.
3. All other design contracts followed exactly (directive kinds, `GuardianReport` fields, `build_report` single-arg-keyword signature, `ValueError` pre-execution, no gate/flow fields).

## Issues Found

- **pytest plugin quirk (environment, not code)**: pytest 9.1.1 + pytest-asyncio 1.4.0 — auto mode not applied; explicit markers required (matches existing repo tests).
- Design OQ "ack ops_surface instance source": resolved as **inject per-directive** (`ops_surface=None` → graceful no-op, `escalations_acked=()`) — aligns with the design default `None`.
- `GuardianEvaluationAgentStage` uses real `MetaGuardianOrchestrator` with `_NullDataProvider` fallbacks; no test seam needed — empty context works and returns `guardian_state` (verified via 2.3 + runtime harness).

## Remaining Tasks (PR 2 + verify)

- [ ] 3.1 RED routing-table test (REQ-642)
- [ ] 3.2 RED config-parse test (delegation ownership)
- [ ] 4.1–4.4 `guardian.md`, `opencode.json`, `orchestrator.md`, `campaign.md`
- [ ] 5.1–5.3 verification / cleanup (verify phase)

## PR Boundary

- Mode: **stacked PR slice** (auto-chain, stacked-to-main) — PR 1 targets `main`.
- Scope: SDK envelope + agent glue + RED tests only. Orchestration config/prompts are PR 2.
- Estimated review budget impact: 637 authored lines across the two feat commits (additions only, no deletions) — within the pre-split PR 1 work unit; PR 2 carries the config/prompt surface.

## Verification Gate (run at end of apply)

```
SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q sdk/tests/test_guardian/test_guardian_agent.py tests/guardian/test_feedback.py sdk/tests/test_pipeline_agent_stages.py tests/campaign/test_flow_segments.py --tb=short
```
→ **71 passed**