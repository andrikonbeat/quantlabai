# Design: Phase 5f-5i — QuantLab AI Production Readiness (E2E Tests, Report Completo, Pipeline Execution, Docs)

## Technical Approach

This design implements the four "finisher" items (5f-5i) that make the platform production-ready. The approach follows the dependency order from the proposal: **5g (Reporting Completo) → 5h (Pipeline Execution Real) → 5f (E2E Smoke Test) → 5i (Documentation)**.

**Core strategy**: Extend existing modules (reporting, pipeline, knowledge) with backward-compatible additions. No breaking changes to public APIs. Each item is independently reversible via git revert.

---

## Architecture Decisions

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| **Smoke test isolation** | `pytest tmp_path` fixture vs `tempfile.TemporaryDirectory()` | `tempfile.TemporaryDirectory()` | Fixture leaks across tests in CI; explicit context manager guarantees cleanup even on crash. Sets `QUANTLAB_KNOWLEDGE_ROOT` via `monkeypatch`. |
| **Report theming** | Dual Jinja2 templates vs CSS variables + Plotly template | CSS variables + `plotly_dark`/`plotly_white` | Single template, zero duplication. CSS vars cascade to all elements. Plotly natively supports dark template. |
| **Plotly fallback** | `kaleido` (static) vs `matplotlib` (optional extra) vs static SVG | `matplotlib` as optional extra `quantlab[reporting-matplotlib]` | `kaleido` adds 50MB binary; matplotlib is pure Python + widely available. Optional extra avoids forcing heavy dep on base install. |
| **Pipeline stage wiring** | Direct imports in registry vs registry pattern | Registry with stage type map | Existing `PipelineRegistry.build_pipeline()` already uses inline map; extending it to SQX stages keeps pattern consistent. Avoids circular imports. |
| **PipelineRun storage** | Separate `pipeline_runs/` dir vs Knowledge Lake | `knowledge/pipeline-runs/` (inside Knowledge Lake) | Existing `KnowledgeStore._pipeline_runs_dir()` already uses this path. Keeps all history under single root for `QUANTLAB_KNOWLEDGE_ROOT` isolation. |
| **Template customization** | Embedded template string vs file path vs template name | File path (`template_path: Path`) in `ReportConfig` | Jinja2 `FileSystemLoader` is simple. Embedded template stays as fallback. CLI `--template` passes path directly. |
| **Benchmark data input** | JSON array vs CSV file | CSV file via CLI `--benchmark` | CSV is standard for equity curves (timestamp,equity). Parsed in CLI, converted to `EquityPoint` list for `ReportConfig`. |
| **Stage timeout** | Global timeout vs per-stage | Per-stage `timeout` in YAML (default 300s) | Matches existing `PipelineRunner` pattern. SQX stages can take variable time. |

---

## Component Designs

### 5g: Reporting Completo (`sdk/quantlab/reporting/`)

#### `models.py` — Extended Models

```python
# Additions to ReportConfig
template_path: Optional[Path] = None

# ChartConfig extended for theme-aware colors
class ChartColors(BaseModel):
    equity: str = "#1f77b4"
    drawdown: str = "#d62728"
    long_trade: str = "#2ca02c"
    short_trade: str = "#ff7f0e"
    benchmark: str = "#9467bd"

class ChartConfig(BaseModel):
    height: int = 500
    width: Optional[int] = None
    colors: ChartColors = Field(default_factory=ChartColors)
    show_range_slider: bool = True
    show_legend: bool = True
```

#### `generator.py` — Enhanced Generator

**New methods:**
- `_try_matplotlib()` → bool: checks `matplotlib` import
- `_render_chart_matplotlib(chart_type, data)` → str: returns base64 PNG data URI
- `_create_charts()`: dispatches to Plotly or matplotlib based on availability
- `_inject_css_variables(theme)` → dict: returns CSS custom properties for light/dark
- `_render_executive_summary(stats)` → dict: computes assessment + indicator
- `_render_phase_timing(phase_results)` → list[dict]: formats durations
- `_render_benchmark_comparison(equity, benchmark_equity)` → list[dict] | None

**HTML template changes:**
- `<html class="theme-{light|dark}">` for CSS variable scoping
- CSS `:root` + `.theme-dark` variables (11 colors)
- New sections: executive summary, phase timing table, benchmark comparison table
- Chart rendering: Plotly JSON → `Plotly.newPlot()` OR `<img src="data:image/png;base64,...">`

**JSON output:** adds `benchmark_equity` array when provided.

#### `cli.py` — Extended CLI

```python
# New argument
parser.add_argument("--template", type=Path, help="Custom Jinja2 template path")
parser.add_argument("--benchmark", type=Path, help="Benchmark equity CSV (timestamp,equity)")
```

#### `pyproject.toml` — Optional Extras

```toml
[project.optional-dependencies]
reporting = ["plotly>=5.18"]
reporting-matplotlib = ["matplotlib>=3.7"]
```

---

### 5h: Pipeline Execution Real (`sdk/quantlab/cli/pipeline_commands.py`, `sdk/quantlab/pipeline/registry.py`)

#### `pipeline/registry.py` — Stage Registry Extension

```python
class PipelineRegistry:
    # ... existing methods ...

    def get_stage_class(self, stage_name: str) -> type[PipelineStage] | None:
        """Resolve stage name to concrete SQX stage class."""
        stage_map = {
            "validate": SQXValidateStage,
            "translate": SQXTranslateStage,
            "optimize": SQXOptimizeStage,
            "walkforward": SQXWalkForwardStage,
            "montecarlo": SQXMonteCarloStage,
            "portfolio": SQXPortfolioStage,
            "risk": SQRiskStage,
            "report": SQXReportStage,
            "knowledge_store": SQXKnowledgeStoreStage,
            "history": SQXHistoryStage,
            "finalize": SQXFinalizeStage,
        }
        return stage_map.get(stage_name)

    def create_pipeline(self, config: PipelineConfig) -> Pipeline:
        """Instantiate Pipeline with concrete SQX stages."""
        pipeline = Pipeline(config.name)
        for stage_config in config.stages:
            if stage_config.type != "builtin":
                raise ValueError(f"Unknown stage type '{stage_config.type}'")
            stage_class = self.get_stage_class(stage_config.name)
            if not stage_class:
                raise ValueError(f"Unknown builtin stage '{stage_config.name}'")
            pipeline.then(stage_class())
        return pipeline
```

#### `pipeline_commands.py` — Real Execution Path

**`cmd_pipeline_run()` modifications:**
- Load pipeline config from registry (or direct YAML via `--config`)
- Build pipeline via `registry.create_pipeline()`
- Create `PipelineContext` with: `sqx_path`, `campaign_name`, `output_dir`, `knowledge_root`, `poll_interval`, `timeout`, `dry_run=False`
- Persist initial `PipelineRun(status="running")` to `KnowledgeStore`
- Call `await PipelineRunner.run(pipeline, ctx)`
- On success: update `PipelineRun(status="completed")`, persist
- On failure: update `PipelineRun(status="failed", error=...)`, persist
- Exit codes: 0=success, 1=not found, 2=config error, 3=execution error/timeout, 4=dry-run output

**New `PipelineContext` fields** (from spec FR-102):
- `sqx_path: Path`
- `campaign_name: str` (pattern: `campaign-pipe-run-{timestamp}-{uuid}`)
- `output_dir: Path` (`knowledge/results/pipeline-{run_id}/`)
- `pipeline_config: PipelineConfig`
- `knowledge_root: Path`
- `timeout_seconds: int` (default 300)
- `dry_run: bool`

#### `phase4/stages/__init__.py` — Export All 11 SQX Stages

```python
from .validate import SQXValidateStage
from .translate import SQXTranslateStage
from .optimize import SQXOptimizeStage
from .walkforward import SQXWalkForwardStage
from .montecarlo import SQXMonteCarloStage
from .portfolio import SQXPortfolioStage
from .risk import SQRiskStage
from .report import SQXReportStage
from .knowledge_store import SQXKnowledgeStoreStage
from .history import SQXHistoryStage
from .finalize import SQXFinalizeStage

__all__ = [
    "SQXValidateStage", "SQXTranslateStage", "SQXOptimizeStage",
    "SQXWalkForwardStage", "SQXMonteCarloStage", "SQXPortfolioStage",
    "SQRiskStage", "SQXReportStage", "SQXKnowledgeStoreStage",
    "SQXHistoryStage", "SQXFinalizeStage",
]
```

---

### 5f: E2E Smoke Test (`tests/test_phase5b_e_smoke.py`)

```python
# tests/test_phase5b_e_smoke.py
import pytest
import tempfile
import os
import subprocess
import yaml
from pathlib import Path

@pytest.fixture
def temp_knowledge_lake(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        kl_root = Path(tmpdir) / "knowledge"
        kl_root.mkdir(parents=True)
        for d in ["structured", "results", "pipeline-runs"]:
            (kl_root / d).mkdir(parents=True)
        # Write initial index.yaml v2
        (kl_root / "index.yaml").write_text(yaml.dump({
            "version": 2, "structured": {}, "results": {}
        }))
        monkeypatch.setenv("QUANTLAB_KNOWLEDGE_ROOT", str(kl_root))
        yield kl_root
        # Auto-cleanup via TemporaryDirectory context manager

def create_mock_campaign(kl_root: Path, campaign_id: str = "smoke-test-campaign"):
    camp_dir = kl_root / "structured" / campaign_id
    camp_dir.mkdir(parents=True)
    # metadata.yaml, statistics.yaml (sharpe=1.5), equity_curve.yaml, trades.yaml
    # Rebuild index via KnowledgeStore().rebuild_index()

def run_cli(args: list[str], env: dict | None = None):
    cmd = ["quantlab"] + args
    return subprocess.run(cmd, capture_output=True, text=True, env=env or os.environ)

def test_phase5b_e_smoke_full_pipeline(temp_knowledge_lake):
    # 1. Create mock campaign
    create_mock_campaign(temp_knowledge_lake)
    
    # 2. Pipeline dry-run (11 stages)
    result = run_cli(["pipeline", "run", "wf_opt", "--dry-run"])
    assert result.returncode == 0
    
    # 3. Verify history in Knowledge Lake
    result = run_cli(["pipeline", "history", "--json"])
    assert result.returncode == 0
    runs = json.loads(result.stdout)
    assert len(runs) == 1
    assert len(runs[0]["stages"]) == 11
    assert all(s["status"] == "completed" for s in runs[0]["stages"])
    
    # 4. Report generation
    result = run_cli(["report", "generate", "smoke-test-campaign", "--output-dir", "/tmp/reports"])
    assert result.returncode == 0
    assert Path("/tmp/reports/smoke-test-campaign_report.html").exists()
    assert Path("/tmp/reports/smoke-test-campaign_report.json").exists()
    
    # 5. Knowledge query --sharpe ">1.0"
    result = run_cli(["knowledge", "query", "--sharpe", ">1.0", "--json"])
    assert result.returncode == 0
    campaigns = json.loads(result.stdout)
    assert len(campaigns) >= 1
    assert campaigns[0]["sharpe"] >= 1.0
```

**Key patterns:**
- `tempfile.TemporaryDirectory()` for isolation (not `pytest.tmp_path`)
- `monkeypatch.setenv("QUANTLAB_KNOWLEDGE_ROOT", ...)` for env isolation
- Subprocess CLI calls (not direct API) to test real command wiring
- No external SQX — uses `--dry-run` and mock data
- Target: < 30s CI execution

---

### 5i: Documentation (`docs/`, `README.md`)

| File | Content |
|------|---------|
| `docs/pipeline-yaml.md` | Complete schema with all 11 stage types, config options, full YAML example |
| `docs/reporting.md` | Installation extras, CLI options, themes, benchmark CSV format, custom template variables, CSS variables, matplotlib fallback, JSON schema |
| `docs/knowledge-query.md` | Filter syntax (`>1.5`, `1.0..2.0`), tag/link commands, JSON/CSV/Parquet export, programmatic API, index schema |
| `README.md` | Updated with 3 new sections: Pipeline Commands, Report Commands, Knowledge Commands (with cross-links to docs/) |

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/reporting/generator.py` | Modify | Dark theme CSS vars, benchmark overlay, matplotlib fallback, custom template, executive summary, phase timing, benchmark comparison |
| `sdk/quantlab/reporting/models.py` | Modify | Add `template_path`, `ChartColors`, extend `ChartConfig`, `ReportConfig` |
| `sdk/quantlab/reporting/cli.py` | Modify | Add `--template`, `--benchmark` arguments |
| `sdk/quantlab/reporting/__init__.py` | No change | |
| `sdk/quantlab/cli/pipeline_commands.py` | Modify | Real execution path in `cmd_pipeline_run()`, `PipelineContext` construction, `KnowledgeStore.save_pipeline_run()`, exit codes |
| `sdk/quantlab/pipeline/registry.py` | Modify | `get_stage_class()`, `create_pipeline()` with 11 SQX stage mappings |
| `sdk/quantlab/pipeline/config.py` | Modify | Stage config schema (if needed for timeout/params) |
| `sdk/quantlab/knowledge/store.py` | Modify | `save_pipeline_run()`, `load_pipeline_runs()` (already exist, verify) |
| `sdk/quantlab/phase4/stages/__init__.py` | Modify | Export all 11 `SQX*Stage` classes |
| `tests/test_phase5b_e_smoke.py` | Create | E2E smoke test with temp Knowledge Lake |
| `docs/pipeline-yaml.md` | Create | Complete pipeline YAML schema reference |
| `docs/reporting.md` | Create | Reporting module documentation |
| `docs/knowledge-query.md` | Create | Knowledge query syntax and CLI docs |
| `README.md` | Modify | Add Pipeline/Report/Knowledge command sections with links |
| `pyproject.toml` | Modify | Add `reporting-matplotlib` optional dependency |

---

## Data Flow

```
Pipeline YAML (config/pipelines/*.yaml)
       │
       ▼
PipelineRegistry.discover() → PipelineConfig (11 stages with type: builtin)
       │
       ▼
PipelineRegistry.create_pipeline() → Pipeline(SQXValidateStage → SQXTranslateStage → ... → SQXFinalizeStage)
       │
       ▼
PipelineContext(sqx_path, campaign_name, output_dir, knowledge_root, timeout, dry_run=False)
       │
       ▼
PipelineRunner.run(pipeline, ctx)  ──►  SQX stages execute sequentially via HTTP API
       │                                    (validate → translate → optimize → walkforward → montecarlo
       │                                     → portfolio → risk → report → knowledge_store → history → finalize)
       ▼
PipelineRun(run_id, pipeline_name, status, stages[], config_snapshot, campaign_id, error?)
       │
       ▼
KnowledgeStore.save_pipeline_run() → knowledge/pipeline-runs/pipe-run-{timestamp}-{uuid}.yaml
       │
       ▼
CLI: pipeline history  /  report generate  /  knowledge query
```

---

## Interfaces / Contracts

### `ReportConfig` (Extended)
```python
class ReportConfig(BaseModel):
    campaign_id: str
    output_dir: Path = Path("reports")
    formats: list[ReportFormat] = [HTML, JSON]
    include_charts: bool = True
    theme: ReportTheme = LIGHT
    title: Optional[str] = None
    benchmark_equity: Optional[list[EquityPoint]] = None
    chart_config: ChartConfig = Field(default_factory=ChartConfig)
    template_path: Optional[Path] = None          # NEW
```

### `PipelineContext` (New Fields)
```python
class PipelineContext:
    def __init__(
        self,
        sqx_path: Path,
        campaign_name: str,
        output_dir: Path,
        pipeline_config: PipelineConfig,
        knowledge_root: Path,
        timeout_seconds: int = 300,
        dry_run: bool = False,
        config: dict | None = None,  # existing
    ): ...
```

### `PipelineRun` (Persisted to Knowledge Lake)
```yaml
run_id: "pipe-run-20240718-120000-abc123"
pipeline_name: "wf_opt"
status: "completed"  # running, completed, failed
started_at: "2024-07-18T12:00:00Z"
completed_at: "2024-07-18T12:05:30Z"
duration_seconds: 330.5
campaign_id: "campaign-pipe-run-20240718-120000-abc123"
stages:
  - name: validate
    status: completed
    duration_seconds: 2.1
    output: "validation_passed"
    error: null
  - name: translate
    status: completed
    duration_seconds: 15.3
    output: "cfx_base64..."
    error: null
  # ... all 11 stages
config_snapshot: {...}
error: null
```

### Custom Template Variables (Jinja2 Context)
```python
{
    "campaign_id": str,
    "campaign_name": str,
    "generated_at": str,           # ISO8601
    "theme": "light" | "dark",
    "css_variables": dict,         # 11 CSS custom properties
    "title": str,
    "executive_summary": {
        "net_profit": float,
        "sharpe": float,
        "max_drawdown": float,
        "win_rate": float,
        "profit_factor": float,
        "assessment": str,
        "indicator": "green" | "amber" | "red"
    },
    "equity_curve_data": list[dict],      # {timestamp, equity}
    "benchmark_equity_data": list[dict] | None,
    "drawdown_data": list[dict],
    "trades_data": list[dict],
    "metrics_table": list[dict],          # [{metric, value, formatted}]
    "phase_timing": list[dict],           # [{phase, status, duration_ms, start, end}]
    "benchmark_comparison": list[dict] | None,  # [{metric, strategy, benchmark}]
    "charts": dict,                       # {equity_curve, drawdown_underwater, trade_scatter, metrics_table}
    "warnings": list[str],
}
```

---

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| **Unit** | ReportGenerator new methods | Mock `CampaignResult`, test `_render_executive_summary`, `_render_chart_matplotlib`, CSS variable injection, template fallback |
| **Unit** | PipelineRegistry stage resolution | `registry.get_stage_class("optimize")` → `SQXOptimizeStage`; unknown stage → `ValueError` |
| **Unit** | KnowledgeStore pipeline run CRUD | `save_pipeline_run()`, `load_pipeline_runs(limit=5, status="failed")`, `get_pipeline_run(id)` |
| **Integration** | Pipeline dry-run → history → report → query | `pytest tests/test_phase5b_e_smoke.py -v` — full E2E in temp Knowledge Lake |
| **Integration** | Real pipeline execution (local) | Mock SQX daemon, verify 11 stages called, history persisted, exit codes |
| **E2E** | Smoke test | Single test file, < 30s CI, no external deps, `QUANTLAB_KNOWLEDGE_ROOT` isolation |
| **Performance** | Dry-run < 10s, real pipeline mocked < 30s | CI timing assertions |

---

## Migration / Rollout

**No migration required.** All changes are backward-compatible additions:
- New `ReportConfig` fields are optional with defaults
- `--dry-run` behavior unchanged (exit codes 0/4)
- Existing pipeline YAMLs work (stage `type: builtin` maps to SQX stages)
- Knowledge Lake schema unchanged (`pipeline-runs/` already exists)

**Rollback per item:**
- 5g: `git revert` reporting changes; remove `reporting-matplotlib` extra
- 5h: `git revert` pipeline commands; unregister SQX stages from registry
- 5f: Delete `tests/test_phase5b_e_smoke.py`
- 5i: `git revert` README/docs changes

---

## Open Questions

- [ ] **SQX daemon startup in CI**: Smoke test uses `--dry-run` so no SQX needed. Real pipeline tests need SQX or mock — confirm local-only for now.
- [ ] **Matplotlib color parity**: Static PNG colors may differ from Plotly. Acceptable? Document in `docs/reporting.md`.
- [ ] **Template variable stability**: Custom templates depend on context dict. Consider versioning or schema validation in future.
- [ ] **Benchmark CSV schema**: Currently `timestamp,equity`. Need to support date-only? Spec says ISO8601 timestamps.

---

## Next Step

Ready for tasks (sdd-tasks).