# Archive Report: Phase 5f-5i — Production Readiness

## Archive Status

**COMPLETE (with 2 documented follow-ups)**

## Summary

Reporting-completo and real pipeline execution shipped and verified end-to-end
via the E2E smoke test (1 passed, 1.24s under mock). Checkboxes realigned to
verified code during the audit-driven close; two task-named test files (1.6,
2.4) were never created and are recorded as follow-ups instead of being marked
done.

## Artifacts

| Artifact | Status | Notes |
|----------|--------|-------|
| `proposal.md` | ✅ | Pre-existing |
| `design.md` | ✅ | Pre-existing |
| `specs/{knowledge-query,pipeline-execution,reporting}/spec.md` | ✅ | Pre-existing deltas (unchanged) |
| `tasks.md` | ✅ | Realigned: verified tasks marked with evidence; 1.6/2.4 left open honestly; path drift corrected |
| `apply-progress.md` | ✅ | Re-verification findings + test evidence |
| `verify-report.md` | ✅ | `verdict: pass_with_warnings`; smoke 1/1 |
| `archive-report.md` | ✅ | This report |

## Verification Evidence

- `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/integration/test_smoke.py -x` → **1 passed** in 1.24s
- `python3 -m py_compile` on reporting + pipeline modules → clean

## Follow-ups (not blockers)

1. Create `tests/test_reporting.py` (task 1.6) — dark theme, benchmark overlay,
   matplotlib fallback, custom template, expanded sections unit coverage.
2. Create `tests/test_pipeline_execution.py` (task 2.4) — registry resolution,
   `create_pipeline()` build, dry-run regression, persist-on-success/failure.
3. Live-SQX acceptance items (real-stage persistence to `knowledge/pipeline-runs/`)
   remain demo-phase items pending a real daemon environment.

## Scope Note

Naming drift corrected (smoke test at `tests/integration/test_smoke.py`, docs
under `configuration/` + `guides/`). The change is archived as delivered, with
the two test-file gaps tracked explicitly rather than silently assumed.