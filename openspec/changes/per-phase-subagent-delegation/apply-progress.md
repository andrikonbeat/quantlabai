---
status: success
executive_summary: PR 1+2+3+4+5 applied and verified; stacked-to-main auto-chain slice.
artifacts: commits 2fcb68d 0fb2b86 63c7f4f ed16281 1c46079 6578ecc cfe3f5b 7da41b6 <PR5-SHA>
next_recommended: verify
risks: None blocking
---
# Apply Progress — Per-Phase Sub-Agent Delegation (PR 1 + PR 2 + PR 3 + PR 4 + PR 5 merged)

**Change**: per-phase-subagent-delegation
**Phase**: sdd-apply — PR 1 of 5 + PR 2 of 5 + PR 3 of 5 + PR 4 of 5 + PR 5 of 5 (prompts + sync + parity + registry 14 + routing + delegation glue + gates + loop + integrity), stacked-to-main, `delivery_strategy=auto-chain`, `chain_strategy=stacked-to-main`
**Mode**: Standard (`strict_tdd: false` per `openspec/config.yaml`)
**Date**: 2026-08-13
**Branch**: `feat/per-phase-subagent-delegation-pr5` (off PR 4 tip `7da41b6`)

## Slice Scope

PR 1 = repo-canonical prompt source + sync + parity (tasks 1.1–1.3).
PR 2 = first 7 phase agent registry + 7 phase prompt files + test extension (tasks 2a.1–2a.3).
PR 3 = remaining 7 phase agent registry + 7 phase prompt files + routing + test extension (tasks 2b.1–2b.5).
PR 4 = delegation glue + envelope + re-export (tasks 3a.1–3a.3).
PR 5 = gates + loop + integrity (tasks 3b.1–3b.4).
`flow.py` untouched (verified empty diff `d0a6b16..HEAD`).

## Completed Tasks (PR 1)

- [x] 1.1 Merge live guardian delegation into `AI/opencode/agents/campaign.md`; preserve REQ-104/203-205 + `PHASES = (...)` (parsed by `_doc_phases`). REQ-806/804.
  - Phase-14 (live-ops) rewritten to delegate to `quantlab-guardian` via `task` (REQ-641/644/34).
  - Preserved: `PHASES` tuple block (byte-identical), REQ-104 Prior Context Injection, REQ-203/204/205 KB teaching table, `assert_flow_segments` preflight, memory-capture section.
  - `git diff --stat`: 8 insertions / 3 deletions — merge only.
- [x] 1.2 Create `AI/opencode/sync_prompts.py`: sorted allowlist `campaign.md`+`phase-*.md`, byte copy, idempotent, `--dry-run`/`--check`, non-managed live files untouched. REQ-806.
  - CLI verified: `--check` → `parity ok` exit 0; second sync → `already in sync` (idempotent).
- [x] 1.3 Create `tests/campaign/test_prompt_sync.py`: idempotency, parity, non-managed ignored, drift names file — RED on drift; sync → green. REQ-807/810.

## Completed Tasks (PR 2)

- [x] 2a.1 Register first 7 phase agents (`research`, `hypothesis`, `config`, `review`, `dispatch`, `monitor`, `retest`) in `~/.config/opencode/opencode.json`: subagent mode; deny-first task `{"*":"deny","quantlab-*":"allow"}`; `question: allow`; bash deny-first allowlist `sdk/quantlab/pipeline/*` + `sdk/quantlab/campaign/*`; prompt refs `phase-<phase>.md`. Names derived verbatim from `PHASES` tuple ids. REQ-805/808/812/813.
- [x] 2a.2 Create 4 full judgment prompts (`phase-research.md`, `phase-hypothesis.md`, `phase-review.md`, `phase-retest.md`) + 3 thin mechanical prompts (`phase-config.md`, `phase-dispatch.md`, `phase-monitor.md`) in `AI/opencode/agents/`. Each includes role, bounded authority (no flow.py mutation, no gate skip, no long-op wait), Result Contract envelope, fail-closed human-gate rules, and SDK examples for judgment phases. REQ-805/809.
- [x] 2a.3 Extend `tests/test_orchestrator_prompt.py` (never replace): added `TestPhaseAgentRegistration` with 7 registrations, mode, deny-first task permissions, question allow, prompt refs, and scoped bash allowlist asserts. REQ-805/808/810.

## Completed Tasks (PR 3)

- [x] 2b.1 Register remaining 7 phase agents (`optimize`, `portfolio`, `compile`, `deploy`, `demo`, `archive`, `live-ops`) in `~/.config/opencode/opencode.json`: subagent mode; deny-first task `{"*":"deny","quantlab-*":"allow"}`; `question: allow`; bash deny-first allowlist `sdk/quantlab/pipeline/*` + `sdk/quantlab/campaign/*`; prompt refs `phase-<phase>.md`. Names derived verbatim from `PHASES` tuple ids. REQ-805/808.
- [x] 2b.2 Create 7 thin prompts (`phase-optimize.md`, `phase-portfolio.md`, `phase-compile.md`, `phase-deploy.md`, `phase-demo.md`, `phase-archive.md`, `phase-live-ops.md`) in `AI/opencode/agents/`. Each includes role, bounded authority (no flow.py mutation, no gate skip, no long-op wait), Result Contract envelope, fail-closed human-gate rules. Only `phase-live-ops.md` delegates to `quantlab-guardian`. REQ-805/809.
- [x] 2b.3 Add REQ-814 routing note to live `~/.config/opencode/prompts/quantlab/orchestrator.md`: CAMPAIGN → quantlab-campaign; no direct phase routing; long ops on orchestrator shell. REQ-814/809.
- [x] 2b.4 Update `AI/opencode/agents/campaign.md` with per-phase dispatch table mapping each of the 14 phases to its `quantlab-phase-<phase>` subagent in `PHASES` order, instructing the campaign agent to dispatch via `task` and fold `PhaseResult` envelopes. No inline fallback. REQ-811.
- [x] 2b.5 Extend `tests/test_orchestrator_prompt.py` (never replace): added `TestRequir814RoutingNote`, `TestCampaignDispatchMap`, and expanded `TestPhaseAgentRegistration` to cover all 14 phase agents with deny-first asserts. REQ-814/811/810.

## Completed Tasks (PR 4)

- [x] 3a.1 RED `tests/campaign/test_delegation.py`: envelope; unknown phase rejected; `status!=success` halts; authority violation; long-op script no-wait; `PHASE_AGENTS==PHASES`; `validate_phase_result()`. REQ-801-804/809.
  - 24 tests covering: `PhaseDirective` frozen envelope, `PhaseResult` schema, `PHASE_AGENTS` registry completeness, `execute_phase()` validation/authority/long-op/mock paths, `validate_phase_result()` helpers, `LongOpSpec` timeout guard.
- [x] 3a.2 Create `sdk/quantlab/campaign/delegation.py` (NEW): dispatch per phase in PHASES order (REQ-811), define `PhaseResult` envelope (REQ-802) with fields `status`, `executive_summary`, `artifacts`, `next_recommended`, `risks`, `phase_id`, `evidence`, `handoff_payload`; handle the name collision with `substrate/executor.py` and `phase4/models.py` via alias-on-import (do NOT rename existing types). Implement long-op handoff: phase agent returns a runnable script spec; the orchestrator shell executes it via nohup/poll/cancel, never the subagent (REQ-803/809). Include validation helpers (e.g. `validate_phase_result()`).
  - Name-collision guard: `SubstratePhaseResult` and `Phase4PhaseResult` aliases imported with `# noqa: F401` to document the three distinct envelope types without renaming existing types.
  - `PHASE_AGENTS` derived from `PHASES` wrap-only; no mutation to `flow.py`.
  - `execute_phase()`: validate → scope-check → executor → envelope validation → long-op handoff log. Mock executor used when `SQX_FORCE_MOCK=1`.
- [x] 3a.3 Re-export in `sdk/quantlab/campaign/__init__.py`. Non-goal: no flow.py/agents/ changes.
  - Re-exported `PhaseDirective`, `PhaseResult`, `PHASE_AGENTS`, `execute_phase`, `validate_phase_result`, `PhaseNotFoundError`, `AuthorityViolationError`, `LongOpSpec`.

## Completed Tasks (PR 5)

- [x] 3b.1 Wire `HUMAN_APPROVE_ARCHIVE` interceptor in `sdk/quantlab/agents/research_director.py` (MOD REQ-38). Added `GateConfig(HUMAN_APPROVE_ARCHIVE, after_stage="archive", timeout_hours=12, fallback="HOLD")` to the orchestrated branch. `HUMAN_APPROVE_DEMO` stays fail-closed. To avoid double-gating, `sdk/quantlab/pipeline/stages/archive_stage.py` now passes `skip_gate=True` to `ArchivePhase`, and `sdk/quantlab/phase4/campaign_archive.py` supports `skip_gate` so the pipeline gate is the single source of truth. REQ-38/REQ-11.
  - `ArchivePhase` returns `status="PENDING_GATE"` when `skip_gate=True`; pipeline `GateInterceptorStage` resolves the human decision.
- [x] 3b.2 Rewrite `AI/opencode/agents/campaign.md` loop to consume the delegation layer: added explicit loop algorithm (construct `PhaseDirective`, `task()` dispatch, `validate_phase_result()`, fold into state, halt on non-success, handoff_payload to orchestrator shell). Human gates remain primary and fail-closed; long-running ops belong to the orchestrator shell. REQ-01/811/802.
- [x] 3b.3 Extend `tests/campaign/test_flow_integrity.py` with `TestDelegationIntegrity`: `PHASE_AGENTS.keys() == PHASES`; agent names are `quantlab-phase-<phase>`; `flow.py` constants unchanged. `test_flow_segments.py` retains its segment-preserving asserts. REQ-804/810.
- [x] 3b.4 Extend `tests/test_orchestrator_prompt.py` with `TestE2eDispatchAndMockIntegrity`: dispatch table order matches `PHASES` exactly; orchestrator routing note mandates long-running ops on orchestrator shell; `SQX_FORCE_MOCK=1 PYTHONPATH=sdk` test command documented and intact. REQ-810/811.

## RED → GREEN Evidence (standard mode, PR 1 + PR 2 + PR 3 + PR 4 + PR 5)

| Task | RED (before) | GREEN (after) |
|---|---|---|
| 1.1 merge | drift pre-existing | `_doc_phases() == PHASES`; all sections present |
| 1.2 sync script | `--check` → `DRIFT (1): campaign.md` exit 1 | `parity ok` exit 0; second sync → no-op |
| 1.3 parity tests | `TestLiveParity` 2 failed (live stale) | 11 passed; live `cmp` byte-identical |
| 2a.1 registry | `TestPhaseAgentRegistration` absent | 7 new tests pass; all deny-first asserts hold |
| 2a.2 prompts | `phase-*.md` absent in repo/live | 7 files synced; `--check` → `parity ok` |
| 2a.3 test extension | `TestPhaseAgentRegistration` absent | 7 new tests pass; existing 18 tests unchanged (25 total) |
| 2b.1 registry | 7 phase agents missing from opencode.json | 7 new entries registered; all deny-first asserts hold |
| 2b.2 prompts | `phase-optimize.md` etc. absent | 7 new files created; `sync_prompts.py` updated (8 files total) |
| 2b.3 orchestrator note | REQ-814 routing note absent | `TestRequir814RoutingNote` 3 tests pass |
| 2b.4 campaign dispatch | No dispatch table in campaign.md | `TestCampaignDispatchMap` 2 tests pass |
| 2b.5 test extension | `TestPhaseAgentRegistration` covered only 7 | Expanded to 14; routing + map asserts added; 59 tests total pass |
| 3a.1 delegation tests | `test_delegation.py` absent | 24 new tests pass (envelope, registry, glue, validation, long-op) |
| 3a.2 delegation module | `delegation.py` absent | Module created; all imports resolve; mock executor green |
| 3a.3 re-export | delegation symbols absent from `campaign/__init__.py` | Symbols re-exported; import from `quantlab.campaign` succeeds |
| 3b.1 archive gate wiring | `HUMAN_APPROVE_ARCHIVE` absent from pipeline gates | Pipeline gate present after archive stage; `ArchivePhase` uses `skip_gate=True`; no double-fire |
| 3b.2 campaign loop | Loop described only in prose | Explicit algorithm added; PhaseDirective/PhaseResult consumption; halt-on-failure; orchestrator-shell long-op handoff |
| 3b.3 delegation integrity | No `PHASE_AGENTS` integrity test | `PHASE_AGENTS.keys() == PHASES`; flow.py unchanged; 3 new tests pass |
| 3b.4 e2e dispatch | No dispatch-order e2e test | Dispatch order == PHASES; orchestrator routing note intact; SQX_FORCE_MOCK documented |

## Work Unit Evidence (PR 5)

| Evidence | Value |
|---|---|
| Focused test command + result | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/campaign/test_delegation.py tests/campaign/test_prompt_sync.py tests/campaign/test_flow_integrity.py tests/campaign/test_flow_segments.py tests/test_orchestrator_prompt.py tests/gates/test_demo_archive_gates.py tests/campaign_archive/test_campaign_archive.py --tb=short` → **129 passed** |
| Runtime harness command/scenario + result | Same focused gate → **129 passed**; full e2e dispatch order asserted; `flow.py` diff empty (`d0a6b16..HEAD`); live `campaign.md` synced byte-identical. |
| Rollback boundary | Revert PR 5 commit; delete `sdk/quantlab/phase4/campaign_archive.py` `skip_gate` param and `PENDING_GATE` branch; restore `sdk/quantlab/pipeline/stages/archive_stage.py` to inject `gate_fn`; restore `research_director.py` to remove `HUMAN_APPROVE_ARCHIVE` gate; revert `campaign.md` loop section to PR 4 prose; restore tests to pre-PR5 state. Additive: no `flow.py` edit. |

## Commits (PR 1 + PR 2 + PR 3 + PR 4 + PR 5)

| SHA | Message | Work unit |
|---|---|---|
| `2fcb68d` | `feat(delegation): merge guardian phase-14 delegation into canonical campaign prompt (PR1)` | 1a drift merge (campaign.md only) |
| `0fb2b86` | `feat(delegation): add deterministic idempotent prompt sync script (PR1)` | 1b sync script (sync_prompts.py only) |
| `63c7f4f` | `test(delegation): add prompt parity and sync idempotency tests (PR1)` | 1c parity tests (test_prompt_sync.py only) |
| `ed16281` | `chore(sdd): mark per-phase-subagent-delegation PR1 tasks complete (PR1)` | PR1 task marks |
| `1c46079` | `feat(delegation): register first 7 phase agents and create judgment/mechanical prompts (PR2)` | PR2 registry 7 + 7 prompts + tests |
| `6578ecc` | `feat(delegation): create 7 thin phase prompts for optimize portfolio compile deploy demo archive live-ops (PR3)` | 2b.2 seven thin prompts |
| `cfe3f5b` | `feat(delegation): add per-phase dispatch table and REQ-814 routing note to campaign prompt (PR3)` | 2b.3 + 2b.4 + 2b.5 (orchestrator note + campaign dispatch + tests) |
| `7da41b6` | `feat(delegation): add delegation glue layer and PhaseResult envelope (PR4)` | 3a.1 + 3a.2 + 3a.3 (delegation.py + test_delegation.py + __init__.py re-export) |
| `<PR5-SHA>` | `feat(delegation): wire archive gate interceptor, rewrite campaign loop, add integrity tests (PR5)` | 3b.1 + 3b.2 + 3b.3 + 3b.4 |

Each commit verified via `git show --stat HEAD` to contain exactly the intended files (repo index holds ~277 files staged from other sessions; never `git add .`).

## Deviations from Design

None — implementation matches design.md PR 5 slice exactly (`HUMAN_APPROVE_ARCHIVE` pipeline gate wired in `research_director.py`, `ArchivePhase(skip_gate=True)` avoids double-fire, `campaign.md` loop rewrite with explicit PhaseDirective/PhaseResult algorithm, `PHASE_AGENTS.keys() == PHASES` integrity tests, e2e dispatch order asserts).

## Issues Found

- None blocking.
- `campaign.md` live copy required `sync_prompts.py` to restore byte-identity after the loop rewrite; parity tests now green.

## Remaining Tasks (verify)

- [ ] Verify phase (post-PR 5)

## PR Boundary

- Mode: **stacked PR slice** (auto-chain, stacked-to-main) — PR 5 stacks on PR 4 tip `7da41b6`.
- Scope: `sdk/quantlab/agents/research_director.py` (HUMAN_APPROVE_ARCHIVE gate); `sdk/quantlab/pipeline/stages/archive_stage.py` (skip_gate=True); `sdk/quantlab/phase4/campaign_archive.py` (skip_gate param + PENDING_GATE); `AI/opencode/agents/campaign.md` (loop rewrite); `tests/campaign/test_flow_integrity.py` (delegation integrity); `tests/test_orchestrator_prompt.py` (e2e dispatch); `tests/gates/test_demo_archive_gates.py` (pipeline wiring asserts).
- Estimated review budget impact: ~250 lines across 7 files — within the PR 5 forecast.

## Verification Gate (run at end of apply)

```
SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/campaign/test_delegation.py tests/campaign/test_prompt_sync.py tests/campaign/test_flow_integrity.py tests/campaign/test_flow_segments.py tests/test_orchestrator_prompt.py tests/gates/test_demo_archive_gates.py tests/campaign_archive/test_campaign_archive.py --tb=short
git diff d0a6b16..HEAD -- sdk/quantlab/campaign/flow.py   # empty (untouched)
```
→ **129 passed** on the gate command; flow.py diff empty; live copy byte-identical.
