# SDD Spec: Phase 5f-5i — QuantLab AI Production Readiness

## Change: phase5f-i

### Overview
Complete Phase 5 with 4 finisher items making the platform production-ready:
1. **E2E Smoke Test** — Single integration test validating full pipeline
2. **Reporting Completo** — Enhanced reports: dark theme, benchmark overlay, matplotlib fallback, custom templates
3. **Pipeline Execution Real** — Real SQX stage execution via PipelineRunner with Knowledge Lake persistence
4. **Documentation** — Comprehensive CLI, pipeline YAML, reporting, and knowledge query docs

---

## Spec 1: E2E Smoke Test (NEW — `openspec/specs/e2e-smoke-test/spec.md`)

### Purpose
Single pytest test: temp Knowledge Lake → pipeline dry-run (11 stages) → history → report → knowledge query. No external SQX. < 30s CI execution.

### Functional Requirements (8)

| ID | Requirement | Key Details |
|----|-------------|-------------|
| FR-001 | Temp Knowledge Lake fixture | `tempfile.TemporaryDirectory()`, sets `QUANTLAB_KNOWLEDGE_ROOT`, auto-cleanup |
| FR-002 | Pipeline dry-run executes 11 stages | `quantlab pipeline run wf_opt --dry-run`, verifies all 11 stage names in trace |
| FR-003 | History persisted to Knowledge Lake | `knowledge/pipeline-runs/pipe-run-{ts}-{uuid}.yaml` with 11 stage entries |
| FR-004 | Report generates HTML + JSON | Mock campaign data, validates both files exist and have content |
| FR-005 | Knowledge query filters by Sharpe | `quantlab knowledge query --sharpe ">1.0" --json` returns matching campaigns |
| FR-006 | No external SQX dependency | Dry-run only, mock data, no `sqx`/`java` subprocess |
| FR-007 | Completes in < 30 seconds | CI timeout target |
| FR-008 | Single test file | `tests/test_phase5b_e_smoke.py` with one test function |

### Scenarios (8 Given/When/Then)
- Temp dir lifecycle (create → set env → cleanup)
- 11 stages execute in dry-run
- History YAML created with correct schema
- HTML (>10KB) + JSON (valid schema) generated
- Sharpe filter returns correct campaigns
- Zero SQX subprocess spawned
- Full test < 30s
- Single pytest test passes

### Interfaces
- CLI: `pipeline run --dry-run`, `pipeline history --json`, `report generate --html --json`, `knowledge query --sharpe --json`
- Env: `QUANTLAB_KNOWLEDGE_ROOT`
- Fixture: `temp_knowledge_lake` (pytest + monkeypatch)

### Acceptance Criteria (9)
- File exists, test passes CI, <30s, temp dir cleaned, 11 stages logged, history YAML valid, HTML+JSON generated, query filters correctly, no SQX subprocess

---

## Spec 2: Reporting Completo (NEW — `openspec/specs/reporting-completo/spec.md`)

### Purpose
Enhanced reporting: dark theme (CSS vars), benchmark overlay, matplotlib static fallback, custom Jinja2 templates, executive summary, phase timing, benchmark comparison.

### Functional Requirements (7)

| ID | Requirement | Key Details |
|----|-------------|-------------|
| FR-001 | Dark theme via CSS variables | `--theme dark` → CSS vars + `plotly_dark` template |
| FR-002 | Benchmark equity overlay | Second trace on equity curve when `benchmark_equity` provided |
| FR-003 | Matplotlib fallback (optional extra) | `quantlab[reporting-matplotlib]` → base64 PNG charts if Plotly missing |
| FR-004 | Custom Jinja2 templates | `--template PATH` / `template_path` config, falls back to embedded |
| FR-005 | Executive summary section | 5 key metrics + assessment (green/amber/red by Sharpe) |
| FR-006 | Phase timing table | Phase | Status | Duration | Start | End from `CampaignResult.phases` |
| FR-007 | Benchmark comparison table | Strategy vs Benchmark: Return, Vol, Sharpe, MaxDD, Correlation |

### Scenarios (12 Given/When/Then)
- Dark theme applied, light theme default
- Benchmark overlay renders 2 traces
- Matplotlib fallback generates base64 PNGs
- Missing deps shows warning banner
- Custom template loads, missing falls back
- Executive summary with 5 metrics + badge
- Phase timing table columns correct
- Benchmark comparison when provided
- JSON includes benchmark_equity array

### Interface Changes
```python
# ReportConfig additions
template_path: Path | None = None

# Generator additions
_try_plotly() -> bool
_try_matplotlib() -> bool
_render_chart_matplotlib(chart_type, data) -> str  # base64 PNG

# CLI additions
--template PATH
```

### Extras (pyproject.toml)
- `[project.optional-dependencies] reporting = ["plotly>=5.18"]`
- `[project.optional-dependencies] reporting-matplotlib = ["matplotlib>=3.7"]`

### Acceptance Criteria (11)
- Dark theme CSS vars + Plotly dark, benchmark 2 traces, matplotlib base64 PNG, warning banner, custom template loads, missing template fallback + warning, executive summary 5 metrics, phase timing table, benchmark comparison table, JSON has benchmark_equity, both extras in pyproject.toml

---

## Spec 3: Pipeline Execution Real (DELTA — `openspec/changes/phase5f-i/specs/pipeline-execution/spec.md`)

### Purpose
Modify `pipeline-cli` to execute real SQX stages via `PipelineRunner.run()`, wire `phase4.stages` into registry, persist `PipelineRun` to Knowledge Lake, proper error handling/exit codes.

### ADDED Requirements (6)

| ID | Requirement | Key Details |
|----|-------------|-------------|
| FR-101 | SQX stage registration | Registry maps 11 types → `phase4.stages` classes |
| FR-102 | PipelineContext with full config | `sqx_path`, `campaign_name`, `output_dir`, `timeout_seconds`, `dry_run=False` |
| FR-103 | PipelineRunner executes real stages | Sequential 11 stages, stops on failure, returns `PipelineResult` |
| FR-104 | PipelineRun persistence | `knowledge/pipeline-runs/pipe-run-{ts}-{uuid}.yaml` with all stages |
| FR-105 | CLI real execution path | `--dry-run` unchanged; default runs `PipelineRunner.run()` |
| FR-106 | Error handling + exit codes | 1=not found, 2=config, 3=execution/timeout, 4=dry-run |

### MODIFIED Requirements (3 — full blocks copied from existing spec)

1. **Pipeline Registry** — Added `get_stage_class()`, `create_pipeline()`, auto-registers SQX stages
2. **CLI Pipeline Subcommands** — `run` now has real execution path, `--timeout` option
3. **Pipeline Runner Integration** — `run()` now executes concrete SQX stages

### Interfaces
```python
# Registry
get_stage_class(stage_type) -> type[PipelineStage]
create_pipeline(config) -> Pipeline

# Context
PipelineContext(sqx_path, campaign_name, output_dir, pipeline_config, knowledge_root, timeout_seconds, dry_run)

# Runner
run(pipeline, context) -> PipelineResult

# Result
PipelineResult(run_id, pipeline_name, status, started_at, completed_at, duration_seconds, campaign_id, stages[], config_snapshot, error)

# Phase4 exports
SQXValidateStage, SQXTranslateStage, SQXOptimizeStage, SQXWalkForwardStage, SQXMonteCarloStage, SQXPortfolioStage, SQRiskStage, SQXReportStage, SQXKnowledgeStoreStage, SQXHistoryStage, SQXFinalizeStage
```

### Acceptance Criteria (11)
- Registry resolves all 11 types, pipeline runs 11 stages sequentially, PipelineRun YAML on success/failure, exit code 3 on SQX error/timeout, dry-run unchanged, params override works, timeout respected, campaign_id links to results, phase4.stages exports all classes

---

## Spec 4: Documentation (NEW — `openspec/specs/documentation/spec.md`)

### Purpose
Four new docs + README updates for CLI, pipeline YAML, reporting, knowledge query.

### Functional Requirements (4)

| ID | Document | Content |
|----|----------|---------|
| FR-001 | README.md updates | Pipeline commands, Report commands (extras, themes, benchmark, template), Knowledge commands (query, tag, link) |
| FR-002 | docs/pipeline-yaml.md | Complete schema: top-level, 11 stage types with configs, param overrides, full example, env vars, validation |
| FR-003 | docs/reporting.md | Install extras, CLI options, themes, benchmark CSV format, custom template variables, fallback behavior |
| FR-004 | docs/knowledge-query.md | Query syntax (ranges, tags, dates, text), tag/link CLI, JSON output, query builder API reference |

### Acceptance Criteria (4)
- All 4 files exist and render correctly
- README has 3 new sections with working examples
- pipeline-yaml.md has complete stage config tables
- reporting.md documents both extras and template vars
- knowledge-query.md has syntax reference + examples

---

## Delta Specs (Modified Existing Capabilities)

### Reporting Delta (`openspec/changes/phase5f-i/specs/reporting/spec.md`)
- ADDED: Dark theme impl, benchmark overlay, matplotlib fallback, custom templates, 3 new sections
- MODIFIED: `ReportConfig` (+template_path), `generate_html()` (dispatch), CLI (+template), extras (2 now)
- REMOVED: None

### Pipeline-CLI Delta (covered by Pipeline Execution Real above)
- Full delta at `openspec/changes/phase5f-i/specs/pipeline-execution/spec.md`

### Knowledge-Query Delta (`openspec/changes/phase5f-i/specs/knowledge-query/spec.md`)
- Only validates existing `--sharpe` query works in smoke test temp env
- No code changes required

---

## Dependency Order
5g (Reporting Completo) → 5h (Pipeline Execution) → 5f (E2E Smoke) → 5i (Documentation)

---

## Success Criteria (from Proposal)
- [ ] `tests/test_phase5b_e_smoke.py` passes CI (<30s)
- [ ] `quantlab report generate --theme dark` produces dark HTML
- [ ] `quantlab report generate --benchmark benchmark.csv` overlays benchmark
- [ ] `pip install quantlab[reporting-matplotlib]` enables matplotlib fallback
- [ ] `quantlab report generate --template custom.j2` uses custom template
- [ ] `quantlab pipeline run my-pipeline` executes real SQX, persists to `knowledge/pipeline-runs/`
- [ ] README.md documents new CLI commands and pipeline YAML schema
- [ ] `docs/pipeline-yaml.md`, `docs/reporting.md`, `docs/knowledge-query.md` exist and accurate
- [ ] All 593 existing tests + new tests pass

---

## Files Created/Modified

### New Specs (4)
- `openspec/specs/e2e-smoke-test/spec.md`
- `openspec/specs/reporting-completo/spec.md`
- `openspec/specs/documentation/spec.md`
- `openspec/changes/phase5f-i/specs/pipeline-execution/spec.md`

### Delta Specs (2)
- `openspec/changes/phase5f-i/specs/reporting/spec.md`
- `openspec/changes/phase5f-i/specs/knowledge-query/spec.md`

### Implementation Targets (from Affected Areas)
- `sdk/quantlab/reporting/generator.py`, `models.py`, `templates.py`
- `sdk/quantlab/cli/pipeline_commands.py`
- `sdk/quantlab/pipeline/registry.py`
- `sdk/quantlab/phase4/stages/__init__.py`
- `tests/test_phase5b_e_smoke.py`
- `README.md`
- `docs/pipeline-yaml.md`, `docs/reporting.md`, `docs/knowledge-query.md`
- `pyproject.toml` (extras)