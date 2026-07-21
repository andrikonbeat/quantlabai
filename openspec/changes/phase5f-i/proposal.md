# Proposal: Phase 5f-5i — QuantLab AI Production Readiness (E2E Tests, Report Completo, Pipeline Execution, Docs)

## Intent

Complete Phase 5 by delivering the "finisher" items that make the platform production-ready: an end-to-end smoke test validating the full pipeline, a publication-grade reporting module with dark theme/benchmark overlay/matplotlib fallback/custom templates, real SQX pipeline execution (not dry-run), and comprehensive documentation. Phase 5b-5e are complete (593 tests passing).

## Scope

### In Scope

| Item | Deliverable |
|------|-------------|
| **5f: E2E Smoke Test** | `tests/test_phase5b_e_smoke.py` — single integration test: temp Knowledge Lake → `pipeline run --dry-run` → `pipeline history` → `report generate` → `knowledge query --sharpe ">1.0"`; no external SQX needed |
| **5g: Report Completo** | Enhance `sdk/quantlab/reporting/generator.py`: dark theme (CSS variables), benchmark equity curve overlay, matplotlib fallback for Plotly (optional `quantlab[reporting-matplotlib]` extra), custom Jinja2 template (`--template`), full report sections (executive summary, equity curve, drawdown underwater, trade scatter, metrics table, phase timing, benchmark comparison) |
| **5h: Pipeline Execution Real** | `sdk/quantlab/cli/pipeline_commands.py` `cmd_pipeline_run`: load pipeline config from registry, build `Pipeline` from stage configs using SQX concrete stages from `phase4.stages`, create `PipelineContext` (sqx_path, campaign_name, output_dir), run `PipelineRunner.run()`, persist `PipelineRun` to `knowledge/pipeline-runs/`, proper error handling/exit codes |
| **5i: Documentation** | `README.md` updates (new CLI, pipeline YAML schema, reporting install); `docs/pipeline-yaml.md` (complete schema with all stage types/config); `docs/reporting.md` (extras, custom templates, benchmark overlay); `docs/knowledge-query.md` (query syntax, tag/link usage) |

### Out of Scope

- SQLite migration for Knowledge Lake index (Phase 6)
- Real-time dashboard/streaming (separate web UI project)
- Advanced Monte Carlo (bootstrap, parameter uncertainty) — percentile bands only
- Web-based report viewer (static HTML only)
- Multi-user/tenant Knowledge Lake

## Capabilities

### New Capabilities
- `e2e-smoke-test`: Single integration test validating full Phase 5b-5e flow end-to-end
- `reporting-completo`: Enhanced HTML reports with dark theme, benchmark overlay, matplotlib fallback, custom templates
- `pipeline-execution-real`: Actual SQX pipeline execution via `PipelineRunner` with Knowledge Lake persistence
- `documentation`: User-facing docs for CLI, pipeline YAML, reporting, knowledge query

### Modified Capabilities
- `reporting`: Extended `ReportConfig` with `theme`, `benchmark_equity`, `template_path`; `ReportGenerator` gains matplotlib fallback and custom template rendering
- `pipeline-cli`: `cmd_pipeline_run` now executes real pipelines (not just dry-run); SQX stages from `phase4.stages` wired into registry
- `knowledge-query`: Used by smoke test for `--sharpe ">1.0"` filter validation

## Approach

**Dependency Order**: 5g → 5h → 5f → 5i (reporting enhancements needed for smoke test; real pipeline execution needed for smoke test; docs last)

**5g Reporting Enhancements**:
- Dark theme: CSS variables in template, Plotly `plotly_dark` template
- Benchmark overlay: add second trace to equity curve chart when `config.benchmark_equity` provided
- Matplotlib fallback: try `import plotly`, on `ImportError` use matplotlib to generate static PNG charts; optional extra `quantlab[reporting-matplotlib]` adds `matplotlib>=3.7`
- Custom templates: `--template <path>` loads Jinja2 template; falls back to embedded default

**5h Pipeline Execution**:
- Wire `phase4.stages` (SQXTranslateStage, SQXOptimizeStage, etc.) into `PipelineRegistry`
- `cmd_pipeline_run`: instantiate `Pipeline` from config, create `PipelineContext`, call `PipelineRunner.run()`, save `PipelineRun` to Knowledge Lake
- Error handling: catch SQX CLI errors, timeout, persist `status: failed` with error message, return exit code 3

**5f Smoke Test**:
- Use `tempfile.TemporaryDirectory()` for isolated Knowledge Lake
- Run full sequence in single test function; assert each step succeeds
- No external SQX — uses `--dry-run` for pipeline, mock campaign data for report/query

**5i Documentation**:
- Follow existing docs style; include CLI examples, YAML schema tables, query syntax reference

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/reporting/generator.py` | Modified | Dark theme, benchmark overlay, matplotlib fallback, custom template |
| `sdk/quantlab/reporting/models.py` | Modified | `ReportConfig` adds `theme`, `benchmark_equity`, `template_path` |
| `sdk/quantlab/reporting/templates.py` | Modified | Jinja2 template with CSS variables, dark/light palettes |
| `sdk/quantlab/cli/pipeline_commands.py` | Modified | `cmd_pipeline_run` real execution path |
| `sdk/quantlab/pipeline/registry.py` | Modified | Register SQX concrete stages from `phase4.stages` |
| `sdk/quantlab/phase4/stages/__init__.py` | Modified | Export SQX stages for registry |
| `tests/test_phase5b_e_smoke.py` | New | E2E smoke test |
| `README.md` | Modified | CLI commands, pipeline schema, reporting install |
| `docs/pipeline-yaml.md` | New | Complete pipeline YAML schema |
| `docs/reporting.md` | New | Reporting docs |
| `docs/knowledge-query.md` | New | Knowledge query docs |
| `pyproject.toml` | Modified | Optional extras: `reporting`, `reporting-matplotlib` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Matplotlib fallback produces different visual output | Medium | Accept static PNG; document differences; Plotly remains primary |
| SQX execution timeouts in CI | Low | Use `--dry-run` in smoke test; real execution tested locally |
| Custom template API breaking changes | Low | Keep Jinja2 context stable; document required variables |
| Pipeline history conflicts with campaign artifacts | Low | Separate `pipeline-runs/` directory in Knowledge Lake |

## Rollback Plan

Per-item rollback (each feature independently revertible):
1. **5g**: Revert `reporting/` to pre-5g state (git checkout); remove matplotlib extra from `pyproject.toml`
2. **5h**: Revert `pipeline_commands.py` `cmd_pipeline_run` to dry-run only; unregister SQX stages from registry
3. **5f**: Delete `tests/test_phase5b_e_smoke.py`
4. **5i**: Revert `README.md`; delete `docs/pipeline-yaml.md`, `docs/reporting.md`, `docs/knowledge-query.md`

Full rollback: `git revert` the feature branch merge commit.

## Dependencies

| Item | New Dependencies | Existing Dependencies |
|------|------------------|----------------------|
| 5g Reporting | `matplotlib>=3.7` (optional, `reporting-matplotlib` extra) | `plotly`, `jinja2`, `pydantic`, `pandas` |
| 5h Pipeline | None | `phase4.stages`, `pipeline.runner`, `knowledge.store` |
| 5f Smoke Test | None | `pytest`, `tempfile`, all Phase 5b-5e modules |
| 5i Docs | None | Markdown only |

## Success Criteria

- [ ] `tests/test_phase5b_e_smoke.py` passes in CI (single integration test, < 30s)
- [ ] `quantlab report generate --theme dark` produces dark-themed HTML
- [ ] `quantlab report generate --benchmark benchmark.csv` overlays benchmark on equity curve
- [ ] `pip install quantlab[reporting-matplotlib]` enables matplotlib fallback when Plotly missing
- [ ] `quantlab report generate --template custom.html.j2` uses custom template
- [ ] `quantlab pipeline run my-pipeline` executes real SQX stages, persists to `knowledge/pipeline-runs/`
- [ ] `README.md` documents new CLI commands and pipeline YAML schema
- [ ] `docs/pipeline-yaml.md`, `docs/reporting.md`, `docs/knowledge-query.md` exist and are accurate
- [ ] All 593 existing tests + new tests pass

## PR Split Strategy (Chained PRs, 400-line budget)

| PR | Features | Est. Lines | Branch |
|----|----------|------------|--------|
| **PR 1** | 5g Reporting Completo (core) | ~350 | `feature/phase5g-reporting-completo` |
| **PR 2** | 5h Pipeline Execution Real | ~380 | `feature/phase5h-pipeline-execution` |
| **PR 3** | 5f E2E Smoke Test | ~120 | `feature/phase5f-e2e-smoke` |
| **PR 4** | 5i Documentation | ~200 | `feature/phase5i-docs` |

Each PR under 400 lines (excluding tests). Chained: PR 2 depends on PR 1 (reporting used by pipeline), PR 3 depends on PR 1+2, PR 4 independent.