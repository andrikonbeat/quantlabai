# Archive: Reconfiguration Loop

**Status**: archived — intentional-with-warnings (non-blocking warnings only)
**Date**: 2026-07-31
**Mode**: SDD (hybrid: openspec + engram) — explore → propose → spec → design → tasks → apply → verify → archive

## Change Overview

Added strategic reconfiguration to the campaign loop: after each iteration, ReviewerAgent ITERATE decisions trigger BuildConfig changes and a fresh SQX build in a versioned project directory, instead of only generating new hypotheses.

**Capabilities**: new `campaign-reconfiguration`; modified `campaign-orchestrator` (`execute_campaign()` branches on review_decision) and `research-dsl` (`IterationConfig.auto_iterate` becomes the active loop-control flag).

**What was built**:
- `apply_iteration_proposal()` in `ResearchDirector` — maps semantic `parameter_changes` to `BuildConfig` fields (position_size→population, generations, ranking_type, ranking_conditions_type, min/max_conditions, SL/PT composites, parameter_space, wf_optimization); unknown keys/invalid values warn + skip; never raises
- `execute_campaign()` branching — ITERATE → apply + versioned rebuild; REJECT → `state=FAILED` abort; APPROVE → exit to portfolio; `auto_iterate=False` → single iteration
- Versioned campaign IDs `{base_id}_iter{iteration:02d}` injected into `PipelineContext.config["campaign_id"]`
- Best-result tracking (`selected_strategies` count with `aggregate_stats` mean fallback) and degradation abort (2 consecutive worse → `CONVERGED`, best config restored)
- BuilderAgent reads versioned `campaign_id` from context before UUID generation (legacy fallback preserved)
- `project_builder.py`: +12 spec-required lines (`BuildConfig.generations`/`population` + 2 map entries)

## Verdict

**PASS WITH WARNINGS** — 16/16 tests pass (8 unit + 7 integration + 1 E2E), compileall exit 0, 5/5 requirements implemented, 13/14 scenarios fully runtime-verified (1 structurally-guaranteed partial). CRITICAL: none.

- Verify report: `sdd/reconfiguration-loop/verify-report` (Engram #685) | `openspec/changes/reconfiguration-loop/verify-report.md`

### Warnings (non-blocking)

1. Design/task 3.2 claimed `project_builder.py` unchanged — actually +12 spec-required lines. **Corrected at archive** in `design.md` and `tasks.md` 3.2.
2. Task 2.7 E2E asserts context campaign_id propagation, not on-disk project dirs (no mock SQX server spin-up). Recommended follow-up.
3. "Fails at translation — no monitor spawned" has no dedicated test (structurally guaranteed).
4. `tasks.md` checkboxes were never marked by `sdd-apply` (0/14 at verify time). **Reconciled at archive** — verify-report proves 14/14 implemented; exact reason recorded in `tasks.md` header note.
5. Repo hygiene: working tree mixes uncommitted changes from archived `results-analysis-stage` with this change; reconfiguration-loop itself fully uncommitted. PR/commit attribution needs care before merge.

## Gate Verification

| Gate | Status | Detail |
|------|--------|--------|
| Review Gate | ✅ Skip (no native review ledger exists in this project's SDD workflow for this change; orchestrator confirmed full completion via final state + verify verdict) | Verify verdict PASS WITH WARNINGS, 0 CRITICAL |
| Task Completion Gate | ✅ Pass (exceptional mechanical reconciliation) | 14/14 tasks proven complete by verify report; checkboxes updated at archive with recorded reason |
| CRITICAL Issues | ✅ None | Verify report: CRITICAL: None |
| Action Context | ✅ OK | repo-local; no workspace-planning mode; no restricted edit roots |

## Specs Synced (Delta → Main)

| Domain | Action | Details |
|--------|--------|---------|
| campaign-reconfiguration | Baseline already in sync | ADDED "Reconfiguration Loop Control", "Proposal Application", "Iteration State Management" — already present in main spec (created during spec phase); verified against delta, no further change |
| campaign-orchestrator | Modified | MODIFIED "Campaign Lifecycle" — reconfiguration-aware flow (auto_iterate/ITERATE/REJECT/APPROVE branching) replacing sequential-execution text; monitor scenarios preserved |
| research-dsl | Added | ADDED "IterationConfig auto_iterate Flag" — loop-control flag requirement with enable/disable scenarios |

## Source of Truth Updated

The following main specs now reflect the new behavior:
- `openspec/specs/campaign-reconfiguration/spec.md`
- `openspec/specs/campaign-orchestrator/spec.md`
- `openspec/specs/research-dsl/spec.md`

## Archive Contents

- proposal.md ✅
- spec.md (delta) ✅
- design.md ✅ (corrected: project_builder.py row)
- tasks.md ✅ (14/14 reconciled + 3.2 corrected)
- verify-report.md ✅ (persisted from Engram for audit-trail completeness)
- archive.md ✅ (this file)

## Next Steps

- Address repo hygiene before merge: separate `results-analysis-stage` leftovers from this change; commit reconfiguration-loop files as one PR
- Optional follow-ups: strengthen E2E (task 2.7 — mock SQX server + on-disk dir asserts), add translation-failure monitor test, warn on `position_size` no-op when population is None
