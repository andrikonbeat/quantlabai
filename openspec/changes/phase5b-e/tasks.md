# Tasks: Phase 5b-5e — QuantLab AI Advanced Features (4 Features Combined)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,555 new lines + ~80 tests (excl. tests) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | 5b Reporting Core (models, generator, templates, tests) | PR 1 | Base branch; tests/docs included; ~350 lines |
| 2 | 5b Reporting CLI + 5c Knowledge Query (CLI, query, indexer, store ext, tests) | PR 2 | Depends on PR 1 models; ~380 lines |
| 3 | 5d Pipeline CLI (registry, commands, history, tests) | PR 3 | Depends on PR 2 KnowledgeStore; ~380 lines |
| 4 | 5e Statistics Aggregation (models, aggregator, tests) | PR 4 | Depends on PR 2/3 models; ~445 lines (exception budget) |

## Phase 1: Foundation — 5b Reporting Core (PR 1)

- [x] **1.1** `report-models` — Create `sdk/quantlab/reporting/models.py` with `ReportFormat`, `ReportTheme`, `ChartColors`, `ChartConfig`, `ReportConfig`, `ReportResult` Pydantic models per spec §Interface
- [x] **1.2** `report-generator` — Create `sdk/quantlab/reporting/generator.py` with `ReportGenerator` class: `generate()`, `generate_html()`, `generate_json()`, 4 chart methods (`_equity_curve`, `_drawdown_underwater`, `_trade_scatter`, `_metrics_table`), `_render_html()`, `_render_json()`
- [x] **1.3** `report-templates` — Create `sdk/quantlab/reporting/templates.py` with HTML template string containing embedded Plotly.js CDN, Jinja2 placeholders for charts/metrics, CSS variables for light/dark themes
- [x] **1.4** `report-init` — Create `sdk/quantlab/reporting/__init__.py` exporting public API: `ReportGenerator`, `ReportConfig`, `ReportResult`, `ReportFormat`, `ReportTheme`, `ChartConfig`
- [x] **1.5** `report-pyproject` — Modify `pyproject.toml`: add `[project.optional-dependencies]` `reporting = ["plotly>=5.18"]` extra
- [x] **1.6** `report-tests-models` — Covered by `tests/phase5/test_reporting.py` (consolidated)
- [x] **1.7** `report-tests-generator` — Covered by `tests/phase5/test_reporting.py` (consolidated)
- [x] **1.8** `report-tests-templates` — Covered by `tests/phase5/test_reporting.py` (consolidated)
- [x] **1.9** `report-tests-integration` — Covered by `tests/phase5/test_reporting.py` (consolidated)

## Phase 2: Integration — 5b Reporting CLI + 5c Knowledge Query (PR 2)

- [x] **2.1** `report-cli` — Create `sdk/quantlab/reporting/cli.py` with `generate_report(args)` implementing `quantlab report generate` per spec: args for `--html/--no-html`, `--json/--no-json`, `--output-dir`, `--theme`, `--no-charts`, `--benchmark`, exit codes 0/1/2/3
- [x] **2.2** `knowledge-models` — Create `sdk/quantlab/knowledge/models.py` with `CampaignMetrics`, `CampaignSummary`, `QueryFilter`, `QueryResult`, `TaggedCampaign` dataclasses/Pydantic models per spec §Interface
- [x] **2.3** `knowledge-query` — Create `sdk/quantlab/knowledge/query.py` with `QueryBuilder` fluent API: `filter_by_sharpe`, `filter_by_profit_factor`, `filter_by_win_rate`, `filter_by_max_drawdown`, `filter_by_tags`, `filter_by_date`, `search_text`, `sort_by`, `limit`, `offset`, `execute()` returning `QueryResult`
- [x] **2.4** `knowledge-indexer` — Create `sdk/quantlab/knowledge/indexer.py` with `Indexer` class: `extract_campaign_metrics()`, `extract_campaign_tags()`, `build_index()` producing v2 index schema
- [x] **2.5** `knowledge-store-ext` — Modify `sdk/quantlab/knowledge/store.py`: add `tag()`, `get_tags()`, `link()`, `get_links()`, `query()` methods; modify `rebuild_index()` to call `Indexer.build_index()`; update index schema to v2 with metric fields, tags, links
- [x] **2.6** `knowledge-init` — Modify `sdk/quantlab/knowledge/__init__.py` to export new models and `QueryBuilder`, `Indexer`
- [x] **2.7** `report-cli-tests` — Covered by `tests/phase5/test_reporting_cli.py`
- [x] **2.8** `knowledge-query-tests` — Covered by `tests/phase5/test_knowledge_cli.py` (consolidated)
- [x] **2.9** `knowledge-indexer-tests` — Covered by `tests/phase5/test_knowledge_cli.py` (consolidated)
- [x] **2.10** `knowledge-store-tests` — Covered by `tests/phase5/test_knowledge_cli.py` (consolidated)

## Phase 3: Pipeline CLI — 5d Pipeline Commands (PR 3)

- [x] **3.1** `pipeline-registry` — Create `sdk/quantlab/pipeline/registry.py` with `PipelineRegistry`: `__init__(config_dirs)`, `discover()` scanning `config/pipelines/*.yaml` + `~/.quantlab/pipelines/*.yaml`, `get(name)` → `PipelineConfig`, `list()` → `list[PipelineSummary]`
- [x] **3.2** `pipeline-commands` — Create `sdk/quantlab/cli/pipeline_commands.py` with `pipeline_run_command()`, `pipeline_list_command()`, `pipeline_history_command()` per spec: args parsing, `PipelineRegistry` integration, `PipelineRunner` reuse, Knowledge Lake history persistence
- [x] **3.3** `pipeline-history-store` — Already in `sdk/quantlab/knowledge/store.py` from PR2 (`save_pipeline_run`, `load_pipeline_runs`, `delete_pipeline_runs`)
- [x] **3.4** `pipeline-cli-integration` — `sdk/quantlab/cli/main.py` with `add_pipeline_subparser()`, `add_report_subparser()` wired
- [x] **3.5** `report-cli-integration` — `sdk/quantlab/cli/report_commands.py` with `report_generate_command()`; wired in `main.py`
- [x] **3.6** `knowledge-cli-query` — `cmd_knowledge_query` in PR2's `knowledge_commands.py`; wired via `main.py` in PR3
- [x] **3.7** `pipeline-registry-tests` — `tests/phase5/test_pipeline_registry.py`
- [x] **3.8** `pipeline-commands-tests` — `tests/phase5/test_pipeline_cli.py`
- [x] **3.9** `pipeline-history-tests` — Covered by `tests/phase5/test_pipeline_cli.py` (consolidated)

## Phase 4: Statistics Aggregation — 5e Stats Aggregator (PR 4)

- [x] **4.1** `stats-agg-models` — Modify `sdk/quantlab/stats/models.py`: add `AggregateStats`, `RollingMetrics`, `BenchmarkComparison` classes
- [x] **4.2** `stats-aggregation` — Create `sdk/quantlab/stats/aggregation.py` with `StatisticsAggregator` class (all staticmethods): `aggregate_campaigns()`, `aggregate_wf_cycles()`, `rolling_sharpe()`, `rolling_drawdown()`, `rolling_metrics()`, `benchmark_compare()`, `monte_carlo_bands()` using pandas/numpy
- [x] **4.3** `stats-init` — Modify `sdk/quantlab/stats/__init__.py`: export new models and `StatisticsAggregator`
- [x] **4.4** `stats-agg-tests-models` — Covered by `tests/phase5/test_stats_aggregation.py` (consolidated)
- [x] **4.5** `stats-agg-tests-aggregation` — `tests/phase5/test_stats_aggregation.py`
- [ ] **4.6** `stats-agg-tests-integration` — Not created; integration test requires Phase 4/5 modules not yet merged

## Phase 5: Cross-Cutting & Polish (across PRs)

- [ ] **5.1** `orchestrator-report-stage` — Modify `sdk/quantlab/phase4/stages/__init__.py`: rewrite `SQXReportStage` to delegate to `ReportGenerator` per delta spec; update constructor, `execute()`, artifact keys (`report_html`, `report_json`, `report_charts`)
- [ ] **5.2** `orchestrator-tests` — Modify `tests/phase4/test_stages.py`: update tests for new `SQXReportStage` behavior, verify HTML/JSON artifacts, error on missing `CampaignResult`
- [ ] **5.3** `cli-exports` — Modify `sdk/quantlab/cli/__init__.py`: export new command modules (`pipeline_commands`, `report_commands`)
- [ ] **5.4** `e2e-smoke-tests` — Create `tests/test_phase5b_e_smoke.py`: run `quantlab report generate`, `quantlab knowledge query`, `quantlab pipeline run --dry-run`, `quantlab pipeline history` in temp Knowledge Lake; verify exit codes and outputs
- [ ] **5.5** `docs-update` — Update `README.md` or `docs/` with new CLI commands, reporting extra install, knowledge query examples, pipeline YAML schema
- [ ] **5.6** `test-suite-regression` — Run full test suite (507 existing + ~80 new); ensure all pass, no regressions in `StatisticsEngine`, `KnowledgeStore`, `PipelineRunner`, `CampaignOrchestrator`

---

## Task Summary

| Phase | Tasks | Focus | Est. Effort |
|-------|-------|-------|-------------|
| Phase 1 | 9 | 5b Reporting Core (models, generator, templates, tests) | L |
| Phase 2 | 10 | 5b Reporting CLI + 5c Knowledge Query (CLI, query, indexer, store, tests) | L |
| Phase 3 | 9 | 5d Pipeline CLI (registry, commands, history, CLI integration, tests) | L |
| Phase 4 | 6 | 5e Statistics Aggregation (models, aggregator, tests) | L |
| Phase 5 | 6 | Cross-cutting: orchestrator integration, CLI exports, smoke tests, docs, regression | M |
| **Total** | **40** | | |

## Implementation Order Rationale

1. **PR 1 (Phase 1)** — Foundation: reporting models/generator/templates are independent. No dependencies on other features. Tests establish fixtures reused later.
2. **PR 2 (Phase 2)** — Depends on PR 1 models (`ReportConfig` used by CLI). Knowledge Query is stdlib-only, independent of reporting but needed by PR 3.
3. **PR 3 (Phase 3)** — Depends on PR 2 `KnowledgeStore` extensions for pipeline history persistence and `knowledge query` CLI. Pipeline registry is standalone discovery.
4. **PR 4 (Phase 4)** — Depends on PR 2/3 models (`CampaignResult` from Knowledge Lake, `WalkForwardCycle` from optimizer). StatisticsAggregator is stateless pure functions — independently testable. Slightly over 400-line budget; `size:exception` acceptable for computational module.

## Next Step

Ready for `sdd-apply` to implement PR 1 (Phase 1 tasks). Each PR will be applied sequentially as stacked PRs to `main`.