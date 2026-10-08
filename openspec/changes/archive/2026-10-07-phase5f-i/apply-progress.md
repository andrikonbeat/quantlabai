# Apply Progress: Phase 5f-5i — Production Readiness

## State

**IMPLEMENTED (with 2 documented gaps)** — all code tasks verified against source; 2 task-named
test files absent (1.6, 2.4); live-SQX acceptance items require a real daemon. Change archived
with honest scope notes.

## Progress

| Task | Status | Evidence |
|------|--------|----------|
| 1.1 dark theme | ✅ | `cli.py:44,231` ReportTheme + `--theme`; generator applies templates |
| 1.2 benchmark overlay | ✅ | `generator.py:166-175` |
| 1.3 matplotlib fallback | ✅ | `generator.py:31,42,132-142`; `pyproject.toml:112` |
| 1.4 custom template | ✅ | `generator.py:68-69` FileSystemLoader |
| 1.5 expanded sections | ✅ | Rendered via smoke (>10KB HTML) |
| 1.6 reporting tests | ❌ absent | `tests/test_reporting.py` does not exist — indirect via 3.1 |
| 2.1 stage registry | ✅ | `registry.py:410,513` |
| 2.2 real run + persist | ✅ | Smoke dry-run + history flow |
| 2.3 knowledge store persistence | ✅ | Via smoke run/history |
| 2.4 pipeline integration tests | ❌ absent | `tests/test_pipeline_execution.py` does not exist |
| 3.1 E2E smoke | ✅ | `tests/integration/test_smoke.py` — 1 passed (1.24s) |
| 4.1–4.4 docs | ✅ | Real paths: `configuration/pipeline-yaml.md`, `guides/{reporting,knowledge-query}.md`, README sections |

## Re-verification Findings (2026-10-07)

1. **Task 3.1 implemented under a different file/name.** `tests/test_phase5b_e_smoke.py` does not
   exist; the smoke test lives at `tests/integration/test_smoke.py::test_phase5f_i_smoke_full_pipeline`
   (auto-approve gates + temp Knowledge Lake + dry-run 11 stages + history + report + query). Same
   deliverable, different naming — updated in tasks.md. Also satisfies phase5b-e task 5.4.
2. **Doc path drift.** Tasks named `docs/{pipeline-yaml,reporting,knowledge-query}.md`; real files
   are `docs/configuration/pipeline-yaml.md`, `docs/guides/reporting.md`,
   `docs/guides/knowledge-query.md`, all indexed in `docs/index.md`. Content exists — paths updated.
3. **Two task-named test files never created** (1.6 `tests/test_reporting.py`, 2.4
   `tests/test_pipeline_execution.py`). Neither blocks the shipped behavior (smoke covers the
   flows), but they are real missing deliverables — recorded as follow-ups, not marked done.
4. **`reporting-matplotlib` extra confirmed** at `sdk/pyproject.toml:112`. Earlier audit
   uncertainty about matplotlib extras resolved.

## Test Evidence

- `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/integration/test_smoke.py -x` → **1 passed** in 1.24s
- Companion suites green during the close audit: `tests/phase4/` 657 passed; `sdk/tests/test_health_score.py` 89 passed

## Next Action

Archived as `archive/2026-10-07-phase5f-i/` (with follow-up section for 1.6/2.4).