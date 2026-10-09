# Proposal: Phase 5b-5e — QuantLab AI Advanced Features (4 Features Combined)

## Intent

Deliver four high-value features that unlock QuantLab AI's full potential as a quantitative research platform: interactive HTML/JSON reporting, Knowledge Lake query/search, CLI pipeline execution with run history, and cross-campaign statistics aggregation. These features are interdependent (5d needs 5c, 5e benefits from 5b/5c/5d) and complete the SDK's analytical stack.

**Business Value**: Researchers can generate publication-ready reports, query historical campaigns by metrics/tags, run reusable pipelines from CLI, and compute portfolio-level statistics — enabling production-grade quant workflows.

## Scope

### In Scope (by Feature)

| Feature | Deliverables |
|---------|-------------|
| **5b: Reporting Module** (`sdk/quantlab/reporting/`) | `ReportConfig`, `ReportResult` models; HTML generator with Plotly charts (equity curve, drawdown underwater, trade scatter, stats table); JSON report for CI/CD; `quantlab report generate` CLI; optional `plotly>=5.18` extra |
| **5c: Knowledge Lake Query/Search** (`sdk/quantlab/knowledge/`) | Enhanced YAML index with campaign metrics (sharpe, pf, win_rate, tags); `QueryBuilder` API: `query(filters)`, `search(text)`, `tag()`, `link()`; `quantlab knowledge query` CLI; stdlib only |
| **5d: CLI Pipeline Subcommand** (`sdk/quantlab/cli/`) | `quantlab pipeline run <name> [--config] [--dry-run]`; `pipeline list`; `pipeline history`; run history stored in `knowledge/pipeline-runs/`; `PipelineRegistry` for discovery |
| **5e: Statistics Aggregation** (`sdk/quantlab/stats/`) | `StatisticsAggregator`: `aggregate_campaigns()`, `aggregate_wf_cycles()`, `rolling_sharpe()`, `rolling_drawdown()`, `benchmark_compare()`, `monte_carlo_bands()`; new models: `AggregateStats`, `RollingMetrics`, `BenchmarkComparison`; integrates with reporting |

### Out of Scope
- SQLite migration for Knowledge Lake index (deferred to Phase 6 if >10k files)
- Real-time dashboard/streaming (separate web UI project)
- Multi-user/tenant Knowledge Lake (single-user local store)
- Advanced Monte Carlo (bootstrap, parameter uncertainty) — percentile bands only
- Web-based report viewer (static HTML only)

## Architecture Approach

**Dependency Order**: 5b → 5c → 5d → 5e (5b and 5c independent; parallel OK)
- **5b**: New module, optional `plotly` dep; reuses `StatisticsEngine`, `CampaignResult`, `Trade`/`EquityPoint` models
- **5c**: Extends `KnowledgeStore` index; adds `query.py`, `indexer.py`, `models.py`; no new deps
- **5d**: Adds `pipeline/registry.py`, `cli/pipeline_commands.py`; stores history in Knowledge Lake via `KnowledgeStore` (needs 5c index for queryability)
- **5e**: New `stats/aggregation.py`; extends `models.py`; consumes `CampaignResult` from Knowledge Lake (5c), outputs to Reporting (5b), CLI exposed via 5d pattern

**Key Design Decisions**:
- Plotly as optional extra (`quantlab[reporting]`) — keeps base install light
- YAML index extension over SQLite — simpler, human-readable, sufficient for <10k campaigns
- Pipeline run history in Knowledge Lake — unified query surface with campaigns
- Statistics aggregation reuses `pandas` (already in deps) for rolling computations

## Capabilities

### New Capabilities
- `reporting`: HTML/JSON report generation from `CampaignResult` with interactive Plotly charts
- `knowledge-query`: QueryBuilder API and CLI for filtering campaigns by metrics, tags, date, text
- `pipeline-cli`: Pipeline registration, execution, dry-run, and run history via CLI
- `statistics-aggregation`: Cross-campaign/WF-cycle aggregation, rolling metrics, benchmark comparison, Monte Carlo percentile bands

### Modified Capabilities
- `knowledge-storage`: Extended index schema with metric fields, tag support, campaign summaries
- `statistics-engine`: Extended `StatsResult` model; `StatisticsEngine` gains no new methods (aggregation is separate class)
- `campaign-orchestrator`: `SQXReportStage` delegates to `reporting.generator` (removes placeholder)

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/reporting/` | New | Full reporting module (5 files, ~600 LOC) |
| `sdk/quantlab/knowledge/` | Modified | `store.py` extended; +3 new files (`query.py`, `indexer.py`, `models.py`) |
| `sdk/quantlab/stats/` | Modified | `models.py` extended; +1 new file `aggregation.py` |
| `sdk/quantlab/pipeline/` | Modified | +1 new file `registry.py` |
| `sdk/quantlab/cli/` | Modified | `main.py` extended; +1 new file `pipeline_commands.py` |
| `sdk/quantlab/phase4/stages/` | Modified | `SQXReportStage` refactored to use reporting module |
| `pyproject.toml` | Modified | Add `plotly` optional extra `[reporting]` |
| `tests/` | New | 4 test files (~80 tests total) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Plotly adds ~15MB install size | High | Optional dependency `pip install quantlab[reporting]`; matplotlib fallback documented for later |
| Knowledge query perf on large lakes | Medium | Start with YAML index; benchmark at 10k files; migrate to SQLite/FTS5 if needed |
| Pipeline history storage conflicts with campaign artifacts | Low | Separate `pipeline-runs/` directory; distinct naming convention |
| Statistics aggregation complexity explosion | Medium | Keep `StatisticsAggregator` stateless; pure functions over data lists; test each method independently |
| CLI command namespace collision | Low | Follow existing `argparse` subparser pattern; `pipeline` is new top-level group |

## Rollback Plan

Per-feature rollback (each feature independent for rollback):
1. **5b**: Remove `reporting/` dir; revert `pyproject.toml` extra; revert `SQXReportStage` to placeholder
2. **5c**: Revert `knowledge/` to pre-5c state (git checkout `store.py`, delete new files)
3. **5d**: Remove `pipeline/registry.py`, `cli/pipeline_commands.py`; revert `cli/main.py` pipeline subparser
4. **5e**: Remove `stats/aggregation.py`; revert `stats/models.py`; delete test file

Full rollback: `git revert` the feature branch merge commit.

## Dependencies

| Feature | New Dependencies | Existing Dependencies Used |
|---------|------------------|----------------------------|
| 5b Reporting | `plotly>=5.18` (optional) | `pydantic`, `pandas`, `stats.engine`, `readers.models`, `phase4.campaign_orchestrator` |
| 5c Knowledge Query | None | `yaml`, `pathlib`, `dataclasses`, `knowledge.store` |
| 5d Pipeline CLI | None | `argparse`, `pipeline.runner`, `pipeline.base`, `knowledge.store` |
| 5e Stats Aggregation | None | `statistics`, `math`, `pandas`, `stats.engine`, `phase4.optimizer` |

## Effort Estimate

| Feature | Files | Est. LOC | Unit Tests | Integration Tests |
|---------|-------|----------|------------|-------------------|
| 5b Reporting | 5 new + 1 modified | ~600 | ~15 | ~5 |
| 5c Knowledge Query | 3 new + 1 modified | ~550 | ~15 | ~5 |
| 5d Pipeline CLI | 2 new + 1 modified | ~380 | ~10 | ~5 |
| 5e Stats Aggregation | 1 new + 1 modified | ~445 | ~20 | ~5 |
| **Total** | **11 new, 4 modified** | **~1,975** | **~60** | **~20** |

## PR Split Strategy (Chained PRs, 400-line budget)

| PR | Features | Est. Lines | Notes |
|----|----------|------------|-------|
| **PR 1** | 5b Reporting (core) | ~350 | `reporting/` module minus CLI; tests |
| **PR 2** | 5b Reporting CLI + 5c Knowledge Query | ~380 | `reporting/cli.py` + `knowledge/query.py`, `indexer.py`, `models.py` |
| **PR 3** | 5d Pipeline CLI | ~380 | `pipeline/registry.py`, `cli/pipeline_commands.py`, tests |
| **PR 4** | 5e Statistics Aggregation | ~445 | `stats/aggregation.py`, extended models, tests |

**Total: 4 PRs, ~1,555 new lines + tests** (each under 400-line diff budget excluding tests).

## Success Criteria

- [ ] `quantlab report generate campaign-123 --html --json` produces interactive HTML + JSON
- [ ] `quantlab knowledge query --sharpe ">1.5" --tag "trend"` returns matching campaigns
- [ ] `quantlab pipeline run my-pipeline --dry-run` outputs CFX base64 without running SQX
- [ ] `quantlab pipeline history` shows last 10 runs with status/duration
- [ ] `StatisticsAggregator.aggregate_campaigns([...])` returns `AggregateStats` with mean/median/std Sharpe
- [ ] All 507 existing tests pass + ~80 new tests pass
- [ ] Optional `plotly` dep installs cleanly: `pip install quantlab[reporting]`
- [ ] No new required dependencies in base install