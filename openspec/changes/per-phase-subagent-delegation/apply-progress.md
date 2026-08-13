# Apply Progress — Per-Phase Sub-Agent Delegation (PR 1 slice)

**Change**: per-phase-subagent-delegation
**Phase**: sdd-apply — PR 1 of 5 (prompts + sync + parity), stacked-to-main, `delivery_strategy=auto-chain`, `chain_strategy=stacked-to-main`
**Mode**: Standard (`strict_tdd: false` per `openspec/config.yaml`)
**Date**: 2026-08-13
**Branch**: `feat/per-phase-subagent-delegation-pr1` (off `feat/guardian-orchestrator-feedback-pr2` tip `30c2f2d`)

## Slice Scope

PR 1 = repo-canonical prompt source + sync + parity (tasks 1.1–1.3). PR 2
(registry 7 + judgment prompts) is NOT touched. `sdk/quantlab/campaign/flow.py`
untouched (verified empty diff `d0a6b16..HEAD`).

## Completed Tasks

- [x] 1.1 Merge live guardian delegation into `AI/opencode/agents/campaign.md`; preserve REQ-104/203-205 + `PHASES = (...)` (parsed by `_doc_phases`). REQ-806/804.
  - Phase-14 (live-ops) rewritten to delegate to `quantlab-guardian` via `task` (REQ-641/644/34) — content taken from the live SDD-5 copy.
  - Preserved: `PHASES` tuple block (byte-identical — `_doc_phases == PHASES`), REQ-104 Prior Context Injection, REQ-203/204/205 KB teaching table, `assert_flow_segments` preflight, memory-capture section.
  - `git diff --stat`: 8 insertions / 3 deletions — merge only.
- [x] 1.2 Create `AI/opencode/sync_prompts.py`: sorted allowlist `campaign.md`+`phase-*.md`, byte copy, idempotent, `--dry-run`/`--check`, non-managed files untouched. REQ-806.
  - CLI verified: `--check` on real live dir → `DRIFT (1): campaign.md` (exit 1) before sync; `parity ok` (exit 0) after.
  - Non-managed live files (`guardian.md`, `orchestrator.md`, `deploy.md`, `monitor.md`) untouched (sentinel test).
- [x] 1.3 Create `tests/campaign/test_prompt_sync.py`: idempotency, parity, non-managed ignored, drift names file — RED on drift; sync → green. REQ-807/810.

## RED → GREEN Evidence (standard mode)

| Task | RED (before sync) | GREEN (after sync) |
|---|---|---|
| 1.1 merge | — (drift was pre-existing; repo lacked guardian delegation, live lacked REQ-104/203-205) | `_doc_phases() == PHASES` passes; REQ-104/203-205 strings present; guardian delegation present |
| 1.2 sync script | `--check` → `DRIFT (1): campaign.md` exit 1 (real live dir) | `--check` → `parity ok` exit 0; second sync → `already in sync` (idempotent) |
| 1.3 parity tests | `TestLiveParity` 2 failed — `parity drift in campaign.md` (live stale) | 11 passed in `test_prompt_sync.py`; real live `cmp` byte-identical |

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command + result | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/campaign/test_prompt_sync.py --tb=short` → RED: 2 failed (live parity) → after sync: **11 passed** |
| Regression sweep | `SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/campaign/test_flow_integrity.py tests/campaign/test_flow_segments.py tests/test_orchestrator_prompt.py tests/test_campaign_docs.py tests/campaign/test_prompt_sync.py --tb=short` → **64 passed** (35.84s) |
| Runtime harness command/scenario + result | `python3 AI/opencode/sync_prompts.py` (real sync) → `updated (1): campaign.md`; then `cmp AI/opencode/agents/campaign.md ~/.config/opencode/prompts/quantlab/campaign.md` → **byte-identical**; `python3 AI/opencode/sync_prompts.py --check` → `parity ok` exit 0 (idempotent — tree clean, live matches repo) |
| Rollback boundary | Revert `2fcb68d` (campaign.md merge) + delete `sync_prompts.py` (`0fb2b86`) + delete `tests/campaign/test_prompt_sync.py` (`63c7f4f`). Restore live `~/.config/opencode/prompts/quantlab/campaign.md` from the prior SDD-5 copy. Additive: no `flow.py`, no SDK edit, no registry change. |

## Commits (PR 1)

| SHA | Message | Work unit |
|---|---|---|
| `2fcb68d` | `feat(delegation): merge guardian phase-14 delegation into canonical campaign prompt (PR1)` | 1a drift merge (campaign.md only) |
| `0fb2b86` | `feat(delegation): add deterministic idempotent prompt sync script (PR1)` | 1b sync script (sync_prompts.py only) |
| `63c7f4f` | `test(delegation): add prompt parity and sync idempotency tests (PR1)` | 1c parity tests (test_prompt_sync.py only) |

Each commit verified via `git show --name-only HEAD` to contain exactly one file
(the repo index holds ~271 files staged from other sessions; never `git add .`).

## Deviations from Design

None — implementation matches design.md slice 1 exactly (allowlist, byte copy,
idempotency, dry-run/check, non-managed untouched, parity test in
`tests/campaign/test_prompt_sync.py`).

## Issues Found

- None blocking. Note: `tests/test_prompt_sync.py` in the session-contract
  verify line resolves to `tests/campaign/test_prompt_sync.py` (per
  design.md/tasks.md); the top-level path does not exist.

## Remaining Tasks (PR 2 + verify)

- [ ] 2a.1 Register 7 phase agents in `~/.config/opencode/opencode.json`
- [ ] 2a.2 Create 6 full + 1 thin phase prompts (repo canonical, synced)
- [ ] 2a.3 Extend `tests/test_orchestrator_prompt.py` (7 registrations)
- [ ] 2b.1–2b.5 Registry 7 + routing (PR 3)
- [ ] 3a.1–3a.3 Delegation glue (PR 4)
- [ ] 3b.1–3b.4 Gates + loop + integrity (PR 5)

## PR Boundary

- Mode: **stacked PR slice** (auto-chain, stacked-to-main) — PR 1 is the base
  of the new chain, branched off the previous change's tip (`30c2f2d`).
- Scope: prompts source-of-truth + sync + parity only. Registry/prompts/routing
  are PR 2; glue is PR 4.
- Estimated review budget impact: 125 + 170 + 8 ≈ **303 authored lines** across
  the three commits — within the PR 1 ~220-line forecast (slightly above due to
  test-file verbosity; still well under the 400-line budget).

## Verification Gate (run at end of apply)

```
SQX_FORCE_MOCK=1 PYTHONPATH=sdk python3 -m pytest -q tests/campaign/test_flow_integrity.py tests/test_orchestrator_prompt.py tests/campaign/test_prompt_sync.py --tb=short
git diff d0a6b16..HEAD -- sdk/quantlab/campaign/flow.py   # empty (untouched)
python3 AI/opencode/sync_prompts.py --check               # parity ok, exit 0
```
→ **41 passed** on the gate command; flow.py diff empty; live copy byte-identical.