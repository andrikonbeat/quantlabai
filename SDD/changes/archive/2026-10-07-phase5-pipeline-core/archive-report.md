# Archive Report: Phase 5 — Pipeline Core & Campaign Orchestrator Refactor

## Archive Status

**COMPLETE (with follow-ups)**

## Summary

Pipeline core and the orchestrator refactor are implemented and verified. Phases 3-6 were
re-validated at close against the code: delegation to `PipelineRunner`, exception hierarchy,
DaemonContext, CLI subcommand (run/list/history) and 8 of 11 test files all exist. The
`pipeline status` → `pipeline history` naming drift was reconciled via spec amendment AD-pipe-1
(shipped CLI wins). 3 follow-ups recorded, none blockers.

## Artifacts

| Artifact | Status | Notes |
|----------|--------|-------|
| `proposal.md`, `design.md`, `tasks.md` | ✅ | Tasks realigned at close (phases 3-6 verified with path:line) |
| `specs/campaign-orchestrator/spec.md` | ✅ | Unchanged (callbacks/polling scenarios verified in code) |
| `specs/sqx-cli-wrapper/spec.md` | ✅ | **Amended AD-pipe-1**: `pipeline status` → `pipeline history` + scenario rename |
| `apply-progress.md` | ✅ | Findings + full evidence table |
| `verify-report.md` | ✅ | `verdict: pass_with_warnings` |
| `archive-report.md` | ✅ | This report |

## Verification Evidence

- Phase4 backcompat: **657 passed** (supersedes the 436 estimate in tasks.md)
- Smoke (pipeline dry-run → history → report → query): 1 passed in 1.24s
- Full suite: 4100 passed; 51 pre-existing env failures classified (prompt-sync 42,
  live-sqcli cfx/compiler 8, windows-naming 1) — zero overlap with pipeline/orchestrator areas

## Follow-ups (not blockers)

1. `tests/phase5/test_phase4_stages.py` (6.4) — unit coverage for the 13 SQX stage classes.
2. `tests/phase5/test_daemon_context.py` (6.7) — DaemonContext async lifecycle unit test.
3. 4.3 — measure daemon boilerplate before/after to substantiate (or drop) the ≥60% claim.
4. Optionally align task-test names (`contracts`, `pipeline_cli`) — naming, not behavior.

## Scope Note

Spec amendment AD-pipe-1 follows the same reconciliation used for HS-REQ-05 in
health-score-system: registered naming that drifted in implementation is corrected in the
delta spec with an explicit note; the shipped interface is the source of truth.