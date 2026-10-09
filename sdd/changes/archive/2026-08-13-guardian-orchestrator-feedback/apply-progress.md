# Apply Progress — Guardian Orchestrator Feedback (PR 1 + PR 2 slices)

**Change**: guardian-orchestrator-feedback
**Phase**: sdd-apply — PR 1 (SDK envelope + agent glue) then PR 2 (orchestration surface), stacked-to-main, `delivery_strategy=auto-chain`
**Mode**: Standard (`strict_tdd: false` per `openspec/config.yaml`) — RED-first per tasks within the slice
**Date**: 2026-08-13
**Branch**: `feat/guardian-orchestrator-feedback-pr1` (off `main` a79c5a9) · `feat/guardian-orchestrator-feedback-pr2` (off pr1 `d0a6b16`)

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

---

# PR 2 slice — Orchestration Surface (tasks 3.1–3.2, 4.1–4.4)

**Slice scope**: work unit 2 from sdd-tasks — `quantlab-guardian` agent config
+ guardian prompt, orchestrator GUARDIAN routing, campaign phase-14
delegation. The SDK layer (PR 1) is untouched. The orchestration files live
OUTSIDE the repo (`~/.config/opencode/…`): `~/.config/opencode` is not a git
repo and this repo does not track those paths — they are updated on disk and
recorded here as version-controlled intent per the change constraints. Only
the RED test file and SDD artifacts are committed.

## Completed Tasks

### Phase 3 — RED Tests (threat matrix)

- [x] 3.1 Routing authority (REQ-642) — `TestGuardianRouting` in `tests/test_orchestrator_prompt.py`: GUARDIAN intent-table row dispatches via `task` to `quantlab-guardian`; guardian keywords (guardian/evaluate/live-ops/feedback) classify as GUARDIAN; non-guardian intents MUST NOT dispatch and stay with the orchestrator; neighboring routes not hijacked
- [x] 3.2 Delegation ownership — `TestGuardianAgentRegistration`: `opencode.json` registers `quantlab-guardian` (subagent, `{file:…/guardian.md}`); agent task allowlist is `"*":"deny"` first; orchestrator task has explicit `"quantlab-guardian":"allow"`

### Phase 4 — GREEN Production

- [x] 4.1 Created `~/.config/opencode/prompts/quantlab/guardian.md` — directive intake (`evaluate | live_ops_status | escalation_ack`, REQ-643; unknown kind `ValueError` pre-execution), `GuardianReport` envelope (REQ-644 — `guardian_state` always, `feedback` via `next_cycle_inputs()`), ack via ops_surface w/ unknown id surfaced (REQ-36), explicit NO-phase rule (REQ-37, gates in force REQ-34), Result Contract close
- [x] 4.2 Modified `~/.config/opencode/opencode.json` — added `agent.quantlab-guardian` (quantlab-campaign pattern: hidden subagent, `permission.task {"*":"deny","quantlab-*":"allow"}`, `{file:…/guardian.md}`); orchestrator `permission.task` gains explicit `"quantlab-guardian": "allow"` (between compare and monitor)
- [x] 4.3 Modified `~/.config/opencode/prompts/quantlab/orchestrator.md` — GUARDIAN intent-table row; `### Guardian Routing` section (dispatch via `task`; non-guardian intents "MUST NOT" dispatch, "stays with the orchestrator", REQ-642); `#### quantlab-guardian` allowed-task subsection; header binding line mentions the guardian delegation
- [x] 4.4 Modified `~/.config/opencode/prompts/quantlab/campaign.md` — phase 14 delegates the Guardian live flow to `quantlab-guardian` via `task` (REQ-641) and folds the `GuardianReport` envelope (REQ-644) into the phase Result Contract; human gates remain in force (REQ-34); `PHASES`/gates sections untouched

## RED → GREEN Evidence (standard mode, RED-first per tasks)

| Task | RED (test run before production) | GREEN (production in place) |
|---|---|---|
| 3.1/3.2 + 4.1–4.4 | `python3 -m pytest -q tests/test_orchestrator_prompt.py -k Guardian -p no:cacheprovider` → **6 failed** (no GUARDIAN row, no agent registration, no explicit allow) | same command → **6 passed**; full file → 18 passed (only the pre-existing unrelated failure remains) |

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command + result | `python3 -m pytest -q tests/test_orchestrator_prompt.py -k Guardian -p no:cacheprovider` → RED: 6 failed · GREEN: 6 passed |
| Runtime harness command/scenario + result | `python3 -m json.tool ~/.config/opencode/opencode.json` → parses clean; guardian agent registered deny-first with explicit orchestrator allow. Prompt-route scenario: live `orchestrator.md` renders the GUARDIAN intent-table row + Guardian Routing section; `guardian.md` resolves via the `{file:}` reference. |
| Regression sweep | full `tests/test_orchestrator_prompt.py` → 18 passed + 1 PRE-EXISTING failure (below, not from this slice); `tests/test_campaign_docs.py tests/campaign/test_flow_segments.py` → 23 passed (flow integrity intact); `sdk/tests/test_guardian/test_guardian_agent.py` → 9 passed (PR 1 agent glue intact) |
| Rollback boundary | Revert commit `f188040` (test file only). Disk surface: delete `guardian.md`; remove the `quantlab-guardian` agent block + orchestrator allow entry from `opencode.json`; remove GUARDIAN row/section/subsection from `orchestrator.md`; restore campaign.md phase 14 text → inline flow restored. Additive — no `PHASES`, no SDK file touched. |

## Commits (PR 2)

| SHA | Message |
|---|---|
| `f188040` | `test(orchestrator): add guardian routing and config RED tests (PR2)` — tests/test_orchestrator_prompt.py (68 lines: 67 insertions, 1 deletion) |
| (HEAD) | `chore(sdd): mark guardian-orchestrator-feedback PR2 tasks complete (PR2)` — tasks.md + apply-progress.md (exact SHA at branch tip via `git log`) |

## Design Open Questions — resolved in this slice

- **OQ "campaign wildcard already permits guardian — explicit entry needed?"** → **YES, explicit entry required**: tasks 3.2/4.2 and the delegation-ownership threat-matrix row mandate an explicit `"quantlab-guardian": "allow"` on the orchestrator task, not wildcard reliance. Added explicitly (kept the wildcard as-is).
- **OQ "ops_surface instance source"** → resolved in PR 1: inject per-directive, `None` → graceful no-op (`escalations_acked=()`).

## Deviations from Design

1. Task 4.2 text says "follow the EXACT existing `quantlab-monitor`/`quantlab-deploy` pattern incl. task allowlist" — but those two agents have NO task allowlist. `design.md` is explicit ("quantlab-campaign pattern incl. `task: {"*":"deny","quantlab-*":"allow"}`"); implemented the **quantlab-campaign pattern** (design authoritative — it is the only pattern carrying the deny-first allowlist the RED test asserts).
2. `orchestrator.md` also gained a header binding-line mention and a `#### quantlab-guardian` allowed-task subsection — small additive coherence beyond the design's "intent table + GUARDIAN section", matching the doc's existing QuantLab Task Routing shape.
3. All other design contracts followed exactly (agent pattern, explicit allow, prompt content requirements).

## Issues Found

- **PRE-EXISTING test failure (NOT from this slice)**: `TestOpencodeJsonRegistration::test_opencode_json_registers_campaign_subagent` asserts prompt `AI/opencode/agents/campaign.md` but the live `opencode.json` references `{file:~/.config/opencode/prompts/quantlab/campaign.md}` — drifted from a previous campaign-harness change; failing at baseline (verified before this slice's edits: 12 passed + this 1 failed). Flagged for the verify phase; do NOT attribute to PR 2.
- Live config (`~/.config/opencode/…`) updated on disk only — not committable (outside repo); recorded here per constraints.
- Repo seed `AI/opencode/agents/campaign.md` (13.2K) still differs from the live campaign prompt (10.5K) — pre-existing divergence, out of slice, untouched.

## Verification Gate (PR 2, run at end of apply)

```bash
python3 -m json.tool ~/.config/opencode/opencode.json             # parses clean
python3 -m pytest -q tests/test_orchestrator_prompt.py -k Guardian # 6 passed
git diff --quiet HEAD -- sdk/quantlab/campaign/flow.py             # exit 0 = untouched
```
→ all pass; REQ-37 held (no `flow.py` change).

## Remaining Tasks (sdd-verify phase)

- [ ] 5.1 Flow-integrity assertion after full agent run
- [ ] 5.2 Full suite regression
- [ ] 5.3 Validate `opencode.json` parses; confirm prompts unchanged except intended rows