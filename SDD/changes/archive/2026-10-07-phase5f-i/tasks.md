# Tasks: Phase 5f-5i — QuantLab AI Production Readiness (E2E Tests, Report Completo, Pipeline Execution, Docs)

> 2026-10-07 closure sync: checkboxes realigned to verified code/tests during the audit-driven
> close. Evidence path:line inline. Two test-file tasks (1.6, 2.4) are NOT implemented — flagged,
> not silently marked. 3.1 exists under a different name too — see task.

## Phase 1: 5g Reporting Completo

- [x] 1.1 `report-dark-theme` — `ReportTheme` + `--theme` wired (`sdk/quantlab/reporting/cli.py:44,231`; `sdk/quantlab/cli/report_commands.py:47,81`); generator applies plotly/matplotlib templates
- [x] 1.2 `report-benchmark-overlay` — `generator.py:166-175` builds `benchmark_equity_json` from `config.benchmark_equity`; equity-chart overlay trace + legend
- [x] 1.3 `report-matplotlib-fallback` — `generator.py:31,42` `PLOTLY_AVAILABLE`/`MATPLOTLIB_AVAILABLE` module flags; `:54-55` attach; `:132-142` matplotlib fallback; `sdk/pyproject.toml:112` `reporting-matplotlib` extra exists
- [x] 1.4 `report-custom-template` — `template_path` (`generator.py:68`) + `FileSystemLoader` (`:69`) with embedded-template fallback
- [x] 1.5 `report-expanded-sections` — executive summary / phase timing / benchmark comparison sections rendered; smoke generates HTML >10KB (see 3.1)
- [ ] 1.6 `report-tests` — `tests/test_reporting.py` does **NOT exist**. Coverage is indirect via `tests/integration/test_smoke.py`. Follow-up.

## Phase 2: 5h Pipeline Execution Real

- [x] 2.1 `pipeline-stage-registry` — `registry.py:410` `get_stage_class()`, `:513` `create_pipeline()`
- [x] 2.2 `pipeline-real-run` — `cmd_pipeline_run()` persists PipelineRun via KnowledgeStore; dry-run path exercised by smoke (3.1); history command returns persisted runs
- [x] 2.3 `pipeline-knowledge-store` — `save_pipeline_run`/`load_pipeline_runs` verified via smoke run + history flow
- [ ] 2.4 `pipeline-integration-tests` — `tests/test_pipeline_execution.py` does **NOT exist**. Follow-up (dry-run regression covered by smoke).

## Phase 3: 5f E2E Smoke Test

- [x] 3.1 `smoke-test` — implemented as `tests/integration/test_smoke.py` → `test_phase5f_i_smoke_full_pipeline` (not `tests/test_phase5b_e_smoke.py`; naming drift). Temp Knowledge Lake → mock campaign → `pipeline run wf_opt --dry-run` (11 stages) → `pipeline history` → `report generate` (HTML+JSON >10KB) → `knowledge query --sharpe ">1.0"`. Auto-approve gates mocked. **1 passed in 1.24s** (SQX_FORCE_MOCK=1). Also satisfies phase5b-e task 5.4.

## Phase 4: 5i Documentation

- [x] 4.1 `docs-pipeline-yaml` — exists as `docs/configuration/pipeline-yaml.md` (9.0K; task named `docs/pipeline-yaml.md` — path drift)
- [x] 4.2 `docs-reporting` — exists as `docs/guides/reporting.md` (10.2K; task named `docs/reporting.md` — path drift)
- [x] 4.3 `docs-knowledge-query` — exists as `docs/guides/knowledge-query.md` (7.8K; task named `docs/knowledge-query.md` — path drift)
- [x] 4.4 `docs-readme-update` — README contains Pipeline/Report/Knowledge Commands sections (grep: 3 hits); docs indexed in `docs/index.md`

## Acceptance Checklist

- [x] Smoke test passes <30s (`tests/integration/test_smoke.py`, 1.24s)
- [x] `report generate --theme dark` produces dark-themed HTML (theme wired in CLI)
- [x] `report generate --benchmark` overlays benchmark (generator.py:166-175)
- [x] `quantlab[reporting-matplotlib]` extra enables matplotlib fallback (pyproject:112)
- [x] `report generate --template custom.j2` uses custom template (FileSystemLoader path)
- [ ] `pipeline run wf_opt` real SQX stages persist to `knowledge/pipeline-runs/` — requires live SQX daemon; dry-run persistence verified
- [x] README documents new CLI commands with cross-links (3 sections present)
- [x] `pipeline-yaml.md`, `reporting.md`, `knowledge-query.md` exist and accurate (under configuration/ and guides/)
- [ ] Full 593-test suite re-run — superseded by per-suite green runs; full-suite regression tracked in phase5b-e 5.6