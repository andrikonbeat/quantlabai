# Archive Report: Phase 5b-5e — Advanced Features

## Archive Status

**COMPLETE (with documented follow-ups)**

## Summary

Advanced Features (reporting completo, knowledge query, pipeline CLI, stats aggregation) are
implemented and verified. The cross-cutting phase was re-checked at close: 5.1 delegate already
implemented, 5.4 smoke exists (shared with phase5f-i), 5.5 docs in place, 5.6 full-suite
regression run with all 51 failures classified as pre-existing environment/config classes.
Two tasks recorded as not-done with honest notes (5.2 missing test file; 5.3 intentionally
deferred to avoid circular imports).

## Artifacts

| Artifact | Status | Notes |
|----------|--------|-------|
| `proposal.md`, `design.md`, `tasks.md` | ✅ | Pre-existing; tasks realigned at close (5.1-5.6 re-verified with evidence) |
| `specs/{reporting,5c-knowledge-query,5d-pipeline,stats}/spec.md` | ✅ | Delta specs unchanged |
| `apply-progress.md` | ✅ | Findings + evidence table |
| `verify-report.md` | ✅ | `verdict: pass_with_warnings`; 4100 passed, failures classified |
| `archive-report.md` | ✅ | This report |

## Verification Evidence

- Full suite: 4100 passed / 51 failed / 29 skipped (343s) — 51 = 42 prompt-sync drift + 8
  live-`sqcli`-dependent + 1 linux/windows naming; **zero** overlap with the change's areas.
- Smoke (5.4): 1 passed in 1.24s covering all four CLI commands end-to-end.
- Close batch commits contain no runtime code (docs/specs only) — regressions impossible by construction.

## Follow-ups (not blockers)

1. Create `tests/phase4/test_stages.py` (task 5.2) — SQXReportStage unit coverage
   (HTML/JSON artifacts, missing `CampaignResult` error path).
2. 5.3 remains intentionally unimplemented; re-open only if a consumer needs
   `from quantlab.cli import pipeline_commands` (would require import-order rework).
3. 4.6 stats integration tests once Phase 4/5 agents (orchestrator link) merge.
4. Prompt-sync tests heal by running `sync_prompts.py` (repo-wins) — tracked as environment
   hygiene, not this change's scope.