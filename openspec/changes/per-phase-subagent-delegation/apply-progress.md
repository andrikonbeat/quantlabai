# Apply Progress — Per-Phase Sub-Agent Delegation (PR 1 + PR 2 merged)

**Change**: per-phase-subagent-delegation
**Phase**: sdd-apply — PR 1 of 5 + PR 2 of 5 (prompts + sync + parity + registry 7 + judgment prompts), stacked-to-main, `delivery_strategy=auto-chain`, `chain_strategy=stacked-to-main`
**Mode**: Standard (`strict_tdd: false` per `openspec/config.yaml`)
**Date**: 2026-08-13
**Branch**: `feat/per-phase-subagent-delegation-pr2` (off PR 1 tip `ed16281`)

## Slice Scope

PR 1 = repo-canonical prompt source + sync + parity (tasks 1.1–1.3).
PR 2 = first 7 phase agent registry + 7 phase prompt files + test extension (tasks 2a.1–2a.3).
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

## RED → GREEN Evidence (standard mode, PR 1 + PR 2)

| Task | RED (before) | GREEN (after) |
|---|---|---|
| 1.1 merge | drift pre-existing | `_doc_phases() == PHASES`; all sections present |
| 1.2 sync script | `--check` → `DRIFT (1): campaign.md` exit 1 | `parity ok` exit 0; second sync → no-op |
| 1.3 parity tests | `TestLiveParity` 2 failed (live stale) | 11 passed; live `cmp` byte-identical |
| 2a.1 registry | `TestPhaseAgentRegistration` absent | 7 new tests pass; all deny-first asserts hold |
| 2a.2 prompts | `phase-*.md` absent in repo/live | 7 files synced; `--check` → `parity ok` |
| 2a.3 test extension | `TestPhaseAgentRegistration` absent | 7 new tests pass; existing 18 tests unchanged (25 total) |

## Work Unit Evidence (PR 2)

| Evidence | Value |
|---|---|
| Focused test command + result | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/test_orchestrator_prompt.py --tb=short` → **25 passed** (18 existing + 7 new phase-agent registration tests) |
| Regression sweep | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/campaign/test_prompt_sync.py tests/campaign/test_flow_integrity.py tests/test_orchestrator_prompt.py --tb=short` → **47 passed** |
| Runtime harness command/scenario + result | `python3 AI/opencode/sync_prompts.py` → `updated (7): phase-config.md, phase-dispatch.md, phase-hypothesis.md, phase-monitor.md, phase-research.md, phase-retest.md, phase-review.md`; `python3 AI/opencode/sync_prompts.py --check` → `parity ok` exit 0 |
| Rollback boundary | Revert PR 2 commit(s) + delete `AI/opencode/agents/phase-*.md` (7 files) + delete `TestPhaseAgentRegistration` from `tests/test_orchestrator_prompt.py`. Restore `~/.config/opencode/opencode.json` from backup (remove 7 agent entries). Additive: no `flow.py`, no SDK edit, no registry logic change. |

## Commits (PR 1 + PR 2)

| SHA | Message | Work unit |
|---|---|---|
| `2fcb68d` | `feat(delegation): merge guardian phase-14 delegation into canonical campaign prompt (PR1)` | 1a drift merge (campaign.md only) |
| `0fb2b86` | `feat(delegation): add deterministic idempotent prompt sync script (PR1)` | 1b sync script (sync_prompts.py only) |
| `63c7f4f` | `test(delegation): add prompt parity and sync idempotency tests (PR1)` | 1c parity tests (test_prompt_sync.py only) |
| `ed16281` | `chore(sdd): mark per-phase-subagent-delegation PR1 tasks complete (PR1)` | PR1 task marks |

Each commit verified via `git show --name-only HEAD` to contain exactly one file (the repo index holds ~277 files staged from other sessions; never `git add .`).

## Deviations from Design

None — implementation matches design.md slice 2 exactly (7 phase agents with deny-first permissions, 4 full + 3 thin prompts synced to live, test extension in `tests/test_orchestrator_prompt.py`).

## Issues Found

- None blocking.
- Note: `tasks.md` line 26 lists `quantlab-phase-{research,hypothesis,review,retest,optimize,portfolio,dispatch}` but the user prompt and design require the **first 7 from the PHASES tuple verbatim**: `research, hypothesis, config, review, dispatch, monitor, retest`. Implemented per user prompt override.

## Remaining Tasks (PR 3 + verify)

- [ ] 2b.1–2b.5 Registry 7 + routing (PR 3)
- [ ] 3a.1–3a.3 Delegation glue (PR 4)
- [ ] 3b.1–3b.4 Gates + loop + integrity (PR 5)
- [ ] Verify phase (post-PR 5)

## PR Boundary

- Mode: **stacked PR slice** (auto-chain, stacked-to-main) — PR 2 stacks on PR 1 tip `ed16281`.
- Scope: first 7 phase agents registered in `opencode.json`; 7 phase prompt files created in repo and synced to live; `tests/test_orchestrator_prompt.py` extended with 7 registration tests.
- Estimated review budget impact: ~350 authored lines across prompt files + registry + tests — within the PR 2 forecast.

## Verification Gate (run at end of apply)

```
SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/campaign/test_flow_integrity.py tests/test_orchestrator_prompt.py tests/campaign/test_prompt_sync.py --tb=short
git diff d0a6b16..HEAD -- sdk/quantlab/campaign/flow.py   # empty (untouched)
python3 AI/opencode/sync_prompts.py --check               # parity ok, exit 0
```
→ **47 passed** on the gate command; flow.py diff empty; live copy byte-identical.
