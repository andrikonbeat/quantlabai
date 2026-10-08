# Design: Phase 5b-5e — QuantLab AI Advanced Features

## Technical Approach

This design covers four interdependent features that complete QuantLab AI's analytical stack: **Reporting Module** (5b), **Knowledge Lake Query/Search** (5c), **CLI Pipeline Subcommand** (5d), and **Statistics Aggregation** (5e). The dependency order is 5b → 5c → 5d → 5e, with 5b and 5c independent and parallelizable.

All designs reuse existing patterns: Pydantic models for data, stateless pure-function classes, argparse subparser CLI pattern, and Knowledge Lake's YAML-based filesystem storage. No new required dependencies beyond optional `plotly>=5.18` for reporting.

---

## Architecture Decisions

### Decision: Plotly as Optional Dependency for Reporting

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **plotly (chosen)** | Interactive HTML, self-contained JS bundle, rich chart types; ~15MB install | ✅ Optional extra `quantlab[reporting]` |
| matplotlib | Static PNG/PDF only, verbose API, ~8MB | Fallback for CI/CD (no interactive needed) |
| pygal | SVG, lightweight, limited interactivity | Not chosen — less maintained |

**Rationale**: Single-file HTML with embedded Plotly.js enables interactive reports without external CDN. Optional dependency keeps base install <10MB.

### Decision: Enhanced YAML Index over SQLite for Knowledge Lake

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **Enhanced YAML (chosen)** | Human-readable, no new deps, sufficient for <10k campaigns; query in Python | ✅ Start simple |
| SQLite + FTS5 | Better query perf, full-text search, ACID | Phase 6 if >10k files |
| Hybrid | YAML for humans, SQLite sidecar for queries | Over-engineering for current scale |

**Rationale**: Campaign-level queries filter <1000 index entries. Python in-memory filtering on loaded YAML is <50ms. Migration path to SQLite preserved via `rebuild_index()` interface.

### Decision: Pipeline History in Knowledge Lake (not separate DB)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **Knowledge Lake `pipeline-runs/` (chosen)** | Unified query surface, versioned with Git, reuses `KnowledgeStore` | ✅ Consistent with Feature 5c |
| SQLite `~/.quantlab/pipeline_history.db` | Isolated, faster queries | Breaks "single query surface" goal |
| JSONL log | Simplest, append-only | No queryability |

**Rationale**: Pipeline runs are research artifacts. Storing in Knowledge Lake enables `quantlab knowledge query --pipeline-run "my-pipeline"` cross-query with campaigns.

### Decision: StatisticsAggregator as Stateless Pure Functions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **Stateless class (chosen)** | Testable, composable, no hidden state, `pandas` for rolling ops | ✅ Matches `StatisticsEngine` pattern |
| Stateful accumulator | Incremental updates, memory | Unnecessary complexity |
| Standalone functions | Simplest | Class groups related methods better |

**Rationale**: `StatisticsEngine` already uses this pattern. `StatisticsAggregator` extends it for multi-campaign scenarios. All methods take explicit inputs, return typed outputs.

---

## Data Flow

```
CampaignResult ──► ReportGenerator ──► HTML/JSON Report
       │
       ▼
KnowledgeStore (index) ◄── Indexer (extracts metrics) ◄── Stats YAML
       │
       ▼
QueryBuilder ──► QueryResult (CampaignSummary[])
       │
       ▼
Pipeline History ──► KnowledgeStore (pipeline-runs/) ──► QueryBuilder
       │
       ▼
StatisticsAggregator ──► AggregateStats ──► ReportGenerator (aggregate section)
```

**Cross-Feature Integration Points**:
- `SQXReportStage` → imports `ReportGenerator` from `reporting` (replaces placeholder)
- `PipelineRun` history → stored in Knowledge Lake, queryable via `KnowledgeQuery`
- `StatisticsAggregator` output → feeds into `ReportGenerator` for aggregate reports
- CLI `report generate` → uses `ReportGenerator` directly

---

## File Changes

| File | Action | Feature | Description |
|------|--------|---------|-------------|
| `reporting/__init__.py` | Create | 5b | Exports public API |
| `reporting/models.py` | Create | 5b | `ReportConfig`, `ReportResult`, `ChartConfig`, `ReportFormat`, `ReportTheme` |
| `reporting/generator.py` | Create | 5b | `ReportGenerator.generate(config, campaign_result) → ReportResult`; chart methods |
| `reporting/templates.py` | Create | 5b | HTML template with embedded Plotly.js, Jinja2 placeholders |
| `reporting/cli.py` | Create | 5b | `generate_report(args)` for `quantlab report generate` |
| `knowledge/query.py` | Create | 5c | `QueryBuilder` fluent API: `filter_sharpe()`, `filter_pf()`, `filter_win_rate()`, `filter_tags()`, `filter_date()`, `search_text()`, `execute()` |
| `knowledge/indexer.py` | Create | 5c | `enhance_index()` reads stats YAML, extracts metrics; `tag_campaign()`, `link_campaigns()` |
| `knowledge/models.py` | Create | 5c | `QueryFilter`, `QueryResult`, `CampaignSummary`, `TaggedCampaign` |
| `knowledge/store.py` | Modify | 5c | `rebuild_index()` calls `enhance_index()`; add `tag()`, `link()`, `get_links()`, `get_tags()` |
| `pipeline/registry.py` | Create | 5d | `PipelineRegistry`: discovers built-in (`config/pipelines/*.yaml`) and custom pipelines; `get(name)` → `Pipeline` |
| `cli/pipeline_commands.py` | Create | 5d | `cmd_pipeline_run()`, `cmd_pipeline_list()`, `cmd_pipeline_history()` |
| `cli/main.py` | Modify | 5d | Add `pipeline` subparser with `run`, `list`, `history` subcommands |
| `stats/aggregation.py` | Create | 5e | `StatisticsAggregator`: `aggregate_campaigns()`, `aggregate_wf_cycles()`, `rolling_sharpe()`, `rolling_drawdown()`, `benchmark_compare()`, `monte_carlo_bands()` |
| `stats/models.py` | Modify | 5e | Add `AggregateStats`, `RollingMetrics`, `BenchmarkComparison` |
| `phase4/stages/__init__.py` | Modify | 5b | `SQXReportStage` delegates to `ReportGenerator` |
| `pyproject.toml` | Modify | 5b | Add `plotly>=5.18` to `[project.optional-dependencies]` as `reporting` extra |

---

## Interfaces / Contracts

### 5b: Reporting Module

```python
# reporting/models.py
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Literal
from quantlab.readers.models import Trade, EquityPoint
from quantlab.stats.models import StatsResult

class ReportFormat(str, Enum):
    HTML = "html"
    JSON = "json"
    BOTH = "both"

class ReportTheme(str, Enum):
    LIGHT = "light"
    DARK = "dark"

class ChartConfig(BaseModel):
    include_equity_curve: bool = True
    include_drawdown: bool = True
    include_trade_scatter: bool = True
    include_metrics_table: bool = True
    theme: ReportTheme = ReportTheme.LIGHT
    width: int = 1000
    height: int = 600

class ReportConfig(BaseModel):
    campaign_name: str
    output_dir: Path
    formats: list[ReportFormat] = Field(default_factory=lambda: [ReportFormat.HTML])
    chart_config: ChartConfig = Field(default_factory=ChartConfig)
    include_phase_details: bool = True
    include_trade_list: bool = True
    include_equity_curve_data: bool = True

class ReportResult(BaseModel):
    html_path: Optional[Path] = None
    json_path: Optional[Path] = None
    warnings: list[str] = Field(default_factory=list)
    generation_time_ms: float
    charts_rendered: list[str] = Field(default_factory=list)

# reporting/generator.py
class ReportGenerator:
    def generate(self, config: ReportConfig, campaign_result: CampaignResult) -> ReportResult:
        """Generate HTML and/or JSON report from CampaignResult."""
        ...
    
    def _equity_curve(self, equity: list[EquityPoint], config: ChartConfig) -> str: ...
    def _drawdown_underwater(self, equity: list[EquityPoint], config: ChartConfig) -> str: ...
    def _trade_scatter(self, trades: list[Trade], config: ChartConfig) -> str: ...
    def _metrics_table(self, stats: dict, config: ChartConfig) -> str: ...
    
    def _render_html(self, template_vars: dict, config: ReportConfig) -> str: ...
    def _render_json(self, campaign_result: CampaignResult, config: ReportConfig) -> dict: ...

# reporting/cli.py
def generate_report(args: argparse.Namespace) -> int:
    """quantlab report generate <campaign> [--html] [--json] [--output-dir]"""
    ...
```

### 5c: Knowledge Lake Query/Search

```python
# knowledge/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from pathlib import Path

@dataclass
class CampaignSummary:
    campaign_id: str
    name: str
    campaign_type: str  # backtest, optimizer, retester, portfolio
    created_at: datetime
    metrics: dict[str, float]  # sharpe, pf, win_rate, mdd, etc.
    tags: list[str] = field(default_factory=list)
    linked_campaigns: list[str] = field(default_factory=list)
    stats_path: Path
    cfx_path: Optional[Path] = None

@dataclass
class QueryFilter:
    sharpe_min: Optional[float] = None
    sharpe_max: Optional[float] = None
    pf_min: Optional[float] = None
    pf_max: Optional[float] = None
    win_rate_min: Optional[float] = None
    win_rate_max: Optional[float] = None
    max_drawdown_max: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    text_search: Optional[str] = None
    campaign_type: Optional[str] = None

@dataclass
class QueryResult:
    campaigns: list[CampaignSummary]
    total_count: int
    filtered_count: int

@dataclass
class TaggedCampaign:
    campaign_id: str
    tags: list[str]

# knowledge/query.py
class QueryBuilder:
    def __init__(self, store: KnowledgeStore):
        self.store = store
        self._filters = QueryFilter()
    
    def filter_sharpe(self, min_: float = None, max_: float = None) -> "QueryBuilder": ...
    def filter_pf(self, min_: float = None, max_: float = None) -> "QueryBuilder": ...
    def filter_win_rate(self, min_: float = None) -> "QueryBuilder": ...
    def filter_tags(self, tags: list[str], match_all: bool = True) -> "QueryBuilder": ...
    def filter_date(self, from_: datetime = None, to: datetime = None) -> "QueryBuilder": ...
    def filter_type(self, campaign_type: str) -> "QueryBuilder": ...
    def search_text(self, query: str) -> "QueryBuilder": ...
    def limit(self, n: int) -> "QueryBuilder": ...
    def offset(self, n: int) -> "QueryBuilder": ...
    def execute(self) -> QueryResult: ...

# knowledge/indexer.py
class Indexer:
    @staticmethod
    def enhance_index(store: KnowledgeStore) -> dict:
        """Read stats YAML from knowledge/stats/, extract metrics, enrich index entries."""
        ...
    
    @staticmethod
    def tag_campaign(store: KnowledgeStore, campaign_id: str, tags: list[str]) -> None: ...
    @staticmethod
    def link_campaigns(store: KnowledgeStore, parent: str, children: list[str]) -> None: ...
```

### 5d: Pipeline CLI

```python
# pipeline/registry.py
from dataclasses import dataclass
from pathlib import Path
from quantlab.pipeline import Pipeline, PipelineContext

@dataclass
class Pipeline:
    name: str
    description: str
    config_template: dict  # YAML template with placeholders
    pipeline_builder: callable  # (config) -> Pipeline

class PipelineRegistry:
    def __init__(self, config_dir: Path = Path("config/pipelines")):
        self.config_dir = config_dir
        self._pipelines: dict[str, Pipeline] = {}
    
    def discover(self) -> None:
        """Scan config_dir for *.yaml, load each as Pipeline."""
        ...
    
    def get(self, name: str) -> Pipeline:
        """Return Pipeline instance for name, or raise KeyError."""
        ...
    
    def list(self) -> list[Pipeline]:
        """Return all registered pipelines."""
        ...

# cli/pipeline_commands.py
def cmd_pipeline_run(args: argparse.Namespace) -> int:
    """quantlab pipeline run <name> [--config file.yaml] [--dry-run] [--json]"""
    registry = PipelineRegistry()
    pipeline = registry.get(args.name)
    ctx = PipelineContext(config=load_config(args.config) if args.config else {})
    if args.dry_run:
        # Return CFX base64 without executing
        return dry_run_output(pipeline, ctx)
    runner = PipelineRunner()
    result = await runner.run(pipeline, ctx)
    # Store history in Knowledge Lake
    store_history(result, args.name)
    return output_result(result, args.json)

def cmd_pipeline_list(args: argparse.Namespace) -> int:
    """quantlab pipeline list [--json]"""
    ...

def cmd_pipeline_history(args: argparse.Namespace) -> int:
    """quantlab pipeline history [--limit 10] [--status failed] [--json]"""
    ...
```

### 5e: Statistics Aggregation

```python
# stats/models.py (extended)
from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

class AggregateStats(BaseModel):
    """Per-metric aggregate statistics across multiple campaigns/cycles."""
    metric: str  # sharpe, pf, mdd, win_rate, expectancy
    count: int
    mean: float
    median: float
    std: float
    min: float
    max: float
    p25: float
    p75: float

class RollingMetrics(BaseModel):
    """Rolling window metrics over time."""
    timestamps: list[datetime]
    values: list[float]
    window: int
    metric: str  # sharpe, drawdown

class BenchmarkComparison(BaseModel):
    """Strategy vs benchmark comparison."""
    alpha: float
    beta: float
    information_ratio: float
    correlation: float
    tracking_error: float
    strategy_cagr: float
    benchmark_cagr: float

# stats/aggregation.py
import pandas as pd
import numpy as np
from quantlab.readers.models import Trade, EquityPoint
from quantlab.phase4.optimizer import OptimizationCycle, WalkForwardCycle

class StatisticsAggregator:
    """Stateless aggregator for cross-campaign and walk-forward statistics."""
    
    def aggregate_campaigns(self, results: list[CampaignResult]) -> dict[str, AggregateStats]:
        """Aggregate metrics across multiple CampaignResults.
        
        Returns dict keyed by metric name (sharpe, pf, mdd, win_rate, expectancy).
        """
        ...
    
    def aggregate_wf_cycles(self, cycles: list[WalkForwardCycle]) -> dict[str, AggregateStats]:
        """Aggregate metrics across walk-forward optimization cycles."""
        ...
    
    def rolling_sharpe(self, equity: list[EquityPoint], window: int = 252) -> RollingMetrics:
        """Rolling Sharpe ratio using pandas rolling().apply()."""
        returns = self._equity_to_returns(equity)
        rolling = pd.Series(returns).rolling(window).apply(
            lambda x: StatisticsEngine.sharpe_ratio(x.tolist()) if len(x) >= 2 else np.nan
        )
        return RollingMetrics(...)
    
    def rolling_drawdown(self, equity: list[EquityPoint], window: int = 252) -> RollingMetrics:
        """Rolling max drawdown."""
        ...
    
    def benchmark_compare(self, strategy_returns: list[float], benchmark_returns: list[float]) -> BenchmarkComparison:
        """Alpha, beta, information ratio, correlation, tracking error."""
        ...
    
    def monte_carlo_bands(self, trades: list[Trade], n: int = 1000, percentiles: list[float] = [10, 50, 90]) -> dict[float, float]:
        """Bootstrap resample trades N times, return percentile bands of net profit."""
        ...
```

---

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| **Unit** | `ReportGenerator` chart methods, `QueryBuilder` filters, `StatisticsAggregator` methods, `PipelineRegistry` discovery | Pure function tests with fixture data; mock `CampaignResult` |
| **Integration** | CLI commands end-to-end, Knowledge Lake index → query → CLI, Pipeline run → history → query | Temp Knowledge Lake dir; real `PipelineRunner` with dry-run |
| **E2E** | `quantlab report generate` → HTML opens in browser; `quantlab pipeline run` → history queryable | Manual smoke test in CI with `--dry-run` |

**Test Fixtures**: Reuse existing `CampaignResult` factory from Phase 4 tests. Add `CampaignResult` fixtures with known trades/equity for deterministic aggregation results.

**Coverage Target**: 80%+ on new modules; 100% on pure computation methods (`StatisticsAggregator`, chart data prep).

---

## Migration / Rollout

| Feature | Migration Required? | Plan |
|---------|---------------------|------|
| 5b Reporting | No | New module; `SQXReportStage` delegates to it (backward compatible) |
| 5c Knowledge Query | **Yes** | `store.rebuild_index()` now calls `enhance_index()`; existing indexes auto-upgraded on next rebuild |
| 5d Pipeline CLI | No | New subcommand; no existing commands affected |
| 5e Stats Aggregation | No | New class; `StatisticsEngine` unchanged |

**Rollback**: Per-feature git revert (see Proposal § Rollback Plan). Each feature is independently removable.

---

## Open Questions

- [ ] **Plotly version pinning**: `plotly>=5.18` or exact `plotly==5.24.1`? Exact pin avoids surprise breaking changes.
- [ ] **Indexer performance**: Should `enhance_index()` run lazily (on first query) or eagerly (on `rebuild_index()`)? Eager keeps query fast; lazy defers work.
- [ ] **Pipeline config templating**: Jinja2 vs string replace? Proposal assumes simple dict merge; may need Jinja2 for complex pipelines.
- [ ] **Monte Carlo seed**: Deterministic seed for reproducibility? Accept `seed` param in `monte_carlo_bands()`.
- [ ] **Report theme CSS variables**: Light/dark via CSS custom properties or dual templates? CSS variables simpler.

---

## Next Step

Ready for **sdd-tasks** to break into implementation tasks per PR split (4 PRs, ~400 lines each).

---

*Design document created for Phase 5b-5e (4 features combined).*