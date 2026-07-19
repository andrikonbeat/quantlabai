# Tasks: Phase 5f-5i — QuantLab AI Production Readiness (E2E Tests, Report Completo, Pipeline Execution, Docs)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 1260 (across 4 chained PRs, each < 400 lines) |
| 400-line budget risk | Low |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (5g) → PR 2 (5h) → PR 3 (5f) → PR 4 (5i) |
| Delivery strategy | feature-branch-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | 5g Reporting Completo (dark theme, benchmark overlay, matplotlib fallback, custom templates, expanded sections) | PR 1 | Base branch; tests/docs included; ~350 lines |
| 2 | 5h Pipeline Execution Real (registry SQX stages, real cmd_pipeline_run, KnowledgeStore persistence) | PR 2 | Depends on PR 1 (reporting used by pipeline); ~380 lines |
| 3 | 5f E2E Smoke Test (temp Knowledge Lake, full pipeline→history→report→query flow) | PR 3 | Depends on PR 1+2; single test file ~120 lines |
| 4 | 5i Documentation (README + 3 new doc files) | PR 4 | Independent; can run parallel; ~200 lines |

## Phase 1: 5g Reporting Completo (PR 1 — feature/phase5g-reporting-completo)

- [ ] 1.1 `report-dark-theme` — Extend `sdk/quantlab/reporting/models.py` with `ReportTheme` enum, `ChartColors` model, updated `ChartConfig` and `ReportConfig` (add `theme`, `template_path` fields); update `generator.py` to inject CSS variables and apply `plotly_dark`/`plotly_white` template based on theme; update default template in `templates.py` with `:root` + `.theme-dark` CSS variables (11 colors) and `<html class="theme-{light|dark}">`
- [ ] 1.2 `report-benchmark-overlay` — In `generator.py`, extend `_create_equity_chart()` to add second trace when `config.benchmark_equity` provided; use `config.chart_config.colors.benchmark` color; add legend labels "Strategy"/"Benchmark"; ensure JSON output includes `benchmark_equity` array in `generate_json()`
- [ ] 1.3 `report-matplotlib-fallback` — In `generator.py`, add module-level `PLOTLY_AVAILABLE`/`MATPLOTLIB_AVAILABLE` flags via try/except imports; implement `_try_plotly()`, `_try_matplotlib()`, `_render_chart_matplotlib(chart_type, data)` returning base64 PNG data URI; in `generate_html()`, dispatch to Plotly if available else matplotlib else warning banner; add `reporting-matplotlib = ["matplotlib>=3.7"]` optional extra to `pyproject.toml`
- [ ] 1.4 `report-custom-template` — In `ReportConfig`, add `template_path: Optional[Path]`; in `generator.py` `generate_html()`, load template via `FileSystemLoader` if `template_path` exists and file found, else fall back to embedded template; add `--template` argument to `cli.py`; validate required template variables present (executive_summary, equity_curve_data, drawdown_data, trades_data, metrics_table, phase_timing, benchmark_comparison, charts, css_variables, warnings)
- [ ] 1.5 `report-expanded-sections` — In `generator.py`, add `_render_executive_summary()` computing assessment/indicator (green/amber/red from Sharpe), `_render_phase_timing()` from `CampaignResult.phases`, `_render_benchmark_comparison()` computing 6 metrics (return, ann_return, volatility, sharpe, max_dd, correlation) when benchmark provided; update template with new sections
- [ ] 1.6 `report-tests` — Create/extend `tests/test_reporting.py`: test dark theme CSS variables + Plotly template; test benchmark overlay adds 2 traces; test matplotlib fallback generates base64 PNGs; test custom template loads and renders; test missing template falls back + warning; test executive summary/phase timing/benchmark comparison rendered; test JSON includes benchmark_equity

## Phase 2: 5h Pipeline Execution Real (PR 2 — feature/phase5h-pipeline-execution)

- [ ] 2.1 `pipeline-stage-registry` — In `sdk/quantlab/pipeline/registry.py`, add `get_stage_class(stage_name: str) -> type[PipelineStage] | None` mapping 11 SQX stage names to classes; add `create_pipeline(config: PipelineConfig) -> Pipeline` that instantiates stages via registry; in `sdk/quantlab/phase4/stages/__init__.py`, export all 11 `SQX*Stage` classes
- [ ] 2.2 `pipeline-real-run` — In `sdk/quantlab/cli/pipeline_commands.py`, modify `cmd_pipeline_run()`: load pipeline config from registry (or `--config`), build `Pipeline` via `registry.create_pipeline()`, construct `PipelineContext(sqx_path, campaign_name, output_dir, pipeline_config, knowledge_root, timeout, dry_run=False)`, persist initial `PipelineRun(status="running")` via `KnowledgeStore`, call `await PipelineRunner.run(pipeline, ctx)`, on success update to `status="completed"`, on failure update to `status="failed"` with error; implement exit codes 0/1/2/3/4
- [ ] 2.3 `pipeline-knowledge-store` — In `sdk/quantlab/knowledge/store.py`, verify `save_pipeline_run(run: PipelineRun)` and `load_pipeline_runs(limit, status)` exist and write to `knowledge/pipeline-runs/pipe-run-{timestamp}-{uuid}.yaml`; ensure `PipelineRun` model in `pipeline/models.py` has all required fields (run_id, pipeline_name, status, timestamps, duration, campaign_id, stages[], config_snapshot, error)
- [ ] 2.4 `pipeline-integration-tests` — Create `tests/test_pipeline_execution.py`: test registry resolves all 11 stage types; test `create_pipeline()` builds Pipeline with SQX stages; test `cmd_pipeline_run` dry-run still works (regression); test real run persists PipelineRun on success; test real run persists PipelineRun on failure with error; test `--params` overrides propagate to stages; test `--timeout` respected

## Phase 3: 5f E2E Smoke Test (PR 3 — feature/phase5f-e2e-smoke)

- [ ] 3.1 `smoke-test` — Create `tests/test_phase5b_e_smoke.py`: pytest fixture `temp_knowledge_lake(monkeypatch)` using `tempfile.TemporaryDirectory()` creating `structured/`, `results/`, `pipeline-runs/`, `index.yaml` v2, setting `QUANTLAB_KNOWLEDGE_ROOT`; helper `create_mock_campaign(kl_root)` writing metadata/statistics/equity_curve/trades YAML with `sharpe: 1.5` and rebuilding index; single test `test_phase5b_e_smoke_full_pipeline` executing sequence: (1) create mock campaign, (2) `quantlab pipeline run wf_opt --dry-run` (assert 11 stages in history), (3) `quantlab pipeline history --json` (assert 1 run, 11 completed stages), (4) `quantlab report generate smoke-test-campaign --output-dir /tmp/reports` (assert HTML+JSON exist, HTML > 10KB), (5) `quantlab knowledge query --sharpe ">1.0" --json` (assert campaign returned, sharpe ≥ 1.0); assert total duration < 30s; assert no `sqx`/`java` subprocess spawned

## Phase 4: 5i Documentation (PR 4 — feature/phase5i-docs)

- [x] 4.1 `docs-pipeline-yaml` — Create `docs/pipeline-yaml.md`: top-level structure, all 11 stage types table, per-stage config schemas with examples, parameter override syntax, complete `wf_opt_v2` example YAML, environment variables table, validation command reference
- [x] 4.2 `docs-reporting` — Create `docs/reporting.md`: installation extras (`reporting`, `reporting-matplotlib`), CLI options table, themes (light/dark), benchmark CSV format, custom template variables table (all required vars), executive summary structure, CSS variables for theming, matplotlib fallback behavior, JSON output schema, report sections detail table, exit codes, programmatic API example
- [x] 4.3 `docs-knowledge-query` — Create `docs/knowledge-query.md`: CLI `query` filter options table, range syntax table (`>1.5`, `1.0..2.0`), tag/link commands, index rebuild, export formats (JSON/CSV/Parquet programmatic), programmatic API examples, index schema v2, troubleshooting table
- [x] 4.4 `docs-readme-update` — Update `README.md`: add "Pipeline Commands" section (list, run dry-run, run real, history, config link), add "Report Commands" section (install extras, generate, dark theme, benchmark, custom template, JSON-only), add "Knowledge Commands" section (query filters, tag, link, cross-links to docs/); ensure all CLI examples tested and working

## Implementation Order & Dependencies

1. **PR 1 (5g)** — Independent. Run `sdd-apply` on tasks 1.1–1.6.
2. **PR 2 (5h)** — Depends on PR 1 (pipeline report stage uses ReportGenerator). Run `sdd-apply` on tasks 2.1–2.4 after PR 1 merged.
3. **PR 3 (5f)** — Depends on PR 1 + PR 2 (smoke test exercises full flow). Run `sdd-apply` on task 3.1 after PR 2 merged.
4. **PR 4 (5i)** — Independent, can run in parallel with any PR. Run `sdd-apply` on tasks 4.1–4.4 anytime.

## Acceptance Checklist (All Phases)

- [ ] `tests/test_phase5b_e_smoke.py` passes in CI (< 30s)
- [ ] `quantlab report generate --theme dark` produces dark-themed HTML
- [ ] `quantlab report generate --benchmark benchmark.csv` overlays benchmark on equity curve
- [ ] `pip install quantlab[reporting-matplotlib]` enables matplotlib fallback when Plotly missing
- [ ] `quantlab report generate --template custom.j2` uses custom template
- [ ] `quantlab pipeline run wf_opt` executes real SQX stages, persists to `knowledge/pipeline-runs/`
- [ ] `README.md` documents new CLI commands with cross-links to `docs/`
- [ ] `docs/pipeline-yaml.md`, `docs/reporting.md`, `docs/knowledge-query.md` exist and accurate
- [ ] All 593 existing tests + new tests pass