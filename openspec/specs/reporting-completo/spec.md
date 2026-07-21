# Reporting Completo Specification

## Purpose

Enhanced HTML/JSON reporting module with dark theme (CSS variables), benchmark equity curve overlay, matplotlib static fallback for Plotly, custom Jinja2 templates, and expanded report sections (executive summary, phase timing table, benchmark comparison table). Extends existing `reporting` capability.

---

## Requirements

### Requirement: FR-001 — Dark Theme via CSS Variables

The system SHALL support dark theme using CSS custom properties (variables) applied to all report elements.

The system SHALL:
- Define CSS variables for all colors in Jinja2 template (`--color-bg`, `--color-text`, `--color-primary`, `--color-secondary`, `--color-equity`, `--color-drawdown`, `--color-long`, `--color-short`, `--color-benchmark`, `--color-grid`, `--color-border`)
- Apply `--theme dark` class to `<html>` when `config.theme == "dark"`
- Use Plotly `plotly_dark` template for all charts when dark theme active
- Ensure all text, backgrounds, charts, and tables adapt automatically

#### Scenario: Dark theme applied to HTML report
- GIVEN `ReportConfig(theme=ReportTheme.dark)`
- WHEN `generate_html()` executes
- THEN output HTML has `<html class="theme-dark">`
- AND CSS variables use dark palette (bg #1a1a2e, text #eaeaea, equity #00d4aa, drawdown #ff6b6b)
- AND Plotly charts use `plotly_dark` template

#### Scenario: Light theme remains default
- GIVEN `ReportConfig()` with no theme specified
- WHEN `generate_html()` executes
- THEN output HTML has `<html class="theme-light">` or no theme class
- AND CSS variables use light palette (bg #ffffff, text #1a1a2e)

---

### Requirement: FR-002 — Benchmark Equity Curve Overlay

The system SHALL overlay a benchmark equity curve on the main equity chart when `config.benchmark_equity` is provided.

The system SHALL:
- Accept `benchmark_equity: list[EquityPoint]` in `ReportConfig` (already in existing spec)
- Add second trace to equity curve chart with benchmark line
- Use distinct color (`--color-benchmark` CSS variable, default purple `#9467bd`)
- Show legend with "Strategy" and "Benchmark" labels
- Align timestamps: interpolate or align on common dates
- Display in both HTML (interactive) and JSON (benchmark array included)

#### Scenario: Benchmark overlay on equity curve
- GIVEN `config.benchmark_equity` with 100 data points
- WHEN equity curve chart renders
- THEN chart has 2 traces: strategy equity (primary color) and benchmark (purple)
- AND legend shows both labels
- AND hover shows both values at same timestamp

#### Scenario: Benchmark data in JSON output
- GIVEN `config.benchmark_equity` provided
- WHEN `generate_json()` executes
- THEN JSON includes `"benchmark_equity": [{ "timestamp": "...", "equity": 100000.0 }, ...]`

---

### Requirement: FR-003 — Matplotlib Static Fallback (Optional Extra)

The system SHALL provide matplotlib-based static PNG chart generation as fallback when Plotly is not installed, exposed via optional extra `quantlab[reporting-matplotlib]`.

The system SHALL:
- Try `import plotly` at module load; if `ImportError`, set `PLOTLY_AVAILABLE = False`
- If `PLOTLY_AVAILABLE` and `config.include_charts`: use Plotly (current behavior)
- If not `PLOTLY_AVAILABLE` and `config.include_charts`:
  - Try `import matplotlib`; if available, generate static PNG charts
  - Embed PNGs as base64 data URIs in HTML
  - If matplotlib also missing, emit warning banner, generate HTML without charts
- Add optional dependency extra in `pyproject.toml`: `[project.optional-dependencies] reporting-matplotlib = ["matplotlib>=3.7"]`
- Document that matplotlib fallback produces static (non-interactive) charts

#### Scenario: Plotly missing, matplotlib available → static PNG charts
- GIVEN `pip install quantlab[reporting-matplotlib]` (no plotly)
- WHEN `generate_html()` with `include_charts=True`
- THEN HTML contains `<img src="data:image/png;base64,...">` for each chart
- AND `ReportResult.warnings` contains "Using matplotlib static fallback; interactive charts unavailable"

#### Scenario: Neither Plotly nor matplotlib → warning banner
- GIVEN `pip install quantlab` (no extras)
- WHEN `generate_html()` with `include_charts=True`
- THEN HTML contains banner: "Interactive charts require `pip install quantlab[reporting]` or `pip install quantlab[reporting-matplotlib]`"
- AND `ReportResult.warnings` contains Plotly missing notice
- AND `charts_generated` is empty list

#### Scenario: Plotly available → interactive charts (unchanged)
- GIVEN `pip install quantlab[reporting]`
- WHEN `generate_html()` with `include_charts=True`
- THEN HTML contains interactive Plotly charts (existing behavior)

---

### Requirement: FR-004 — Custom Jinja2 Template Support

The system SHALL allow custom Jinja2 templates via `--template <path>` CLI option and `template_path` in `ReportConfig`.

The system SHALL:
- Add `template_path: Path | None` to `ReportConfig`
- If `template_path` provided and file exists: load as Jinja2 template
- If not provided or file missing: fall back to embedded default template
- Preserve required template variables (see Interface Specifications)
- Validate template has required blocks: `equity_chart`, `drawdown_chart`, `trade_chart`, `metrics_table`, `executive_summary`, `phase_timing`, `benchmark_comparison`

#### Scenario: Custom template loaded and used
- GIVEN `ReportConfig(template_path=Path("custom_report.html.j2"))` with valid template
- WHEN `generate_html()` executes
- THEN output HTML rendered from custom template
- AND all required variables available in template context

#### Scenario: Missing template falls back to default
- GIVEN `ReportConfig(template_path=Path("nonexistent.j2"))`
- WHEN `generate_html()` executes
- THEN embedded default template used
- AND warning added to `ReportResult.warnings`

#### Scenario: CLI --template option
- GIVEN `quantlab report generate campaign-123 --template ./my_template.html.j2`
- WHEN command runs
- THEN custom template used for HTML generation

---

### Requirement: FR-005 — Executive Summary Section

The system SHALL include an executive summary section at the top of the HTML report.

The executive summary SHALL contain:
- Campaign name/ID and date range
- Key metrics: Net Profit, Sharpe Ratio, Max Drawdown, Win Rate, Profit Factor
- One-sentence performance assessment (e.g., "Strong risk-adjusted returns with controlled drawdown")
- Visual indicator: green/amber/red based on Sharpe > 1.5 / > 1.0 / ≤ 1.0

#### Scenario: Executive summary rendered
- GIVEN campaign with Sharpe 1.8, MDD 8%, Win Rate 55%
- WHEN HTML report generates
- THEN executive summary shows all 5 key metrics
- AND assessment text "Strong risk-adjusted returns with controlled drawdown"
- AND green indicator badge

---

### Requirement: FR-006 — Phase Timing Table

The system SHALL include a phase timing table showing duration of each pipeline phase.

The table SHALL have columns: Phase, Status, Duration (ms), Start Time, End Time.
Data sourced from `CampaignResult.phases` (list of phase dicts).

#### Scenario: Phase timing table rendered
- GIVEN `CampaignResult.phases` with 5 phases
- WHEN HTML report generates
- THEN table with 5 rows, all columns populated
- AND durations formatted as human-readable (e.g., "1.2s", "45ms")

---

### Requirement: FR-007 — Benchmark Comparison Table

The system SHALL include a benchmark comparison table when `config.benchmark_equity` provided.

The table SHALL compare strategy vs benchmark on: Total Return, Annualized Return, Volatility, Sharpe Ratio, Max Drawdown, Correlation.

#### Scenario: Benchmark comparison table rendered
- GIVEN `config.benchmark_equity` provided
- WHEN HTML report generates
- THEN table with 6 rows (metrics) and 2 columns (Strategy, Benchmark)
- AND correlation coefficient shown

---

## Interface Specifications

### Extended Models

```python
# quantlab.reporting.models (extends existing)
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List

class ReportTheme(str, Enum):
    light = "light"
    dark = "dark"

class EquityPoint(BaseModel):
    timestamp: str  # ISO8601
    equity: float

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

class ReportConfig(BaseModel):
    campaign_id: str
    output_dir: Path = Path("reports")
    formats: List[str] = Field(default_factory=lambda: ["html", "json"])  # ReportFormat enum
    include_charts: bool = True
    theme: ReportTheme = ReportTheme.light
    title: Optional[str] = None
    benchmark_equity: Optional[List[EquityPoint]] = None
    chart_config: ChartConfig = Field(default_factory=ChartConfig)
    template_path: Optional[Path] = None  # NEW

class ReportResult(BaseModel):
    campaign_id: str
    html_path: Optional[Path] = None
    json_path: Optional[Path] = None
    charts_generated: List[str] = Field(default_factory=list)
    generation_time_ms: float
    warnings: List[str] = Field(default_factory=list)
```

### Generator Interface

```python
# quantlab.reporting.generator (extends existing)
class ReportGenerator:
    def __init__(self, knowledge_root: Optional[Path] = None):
        ...

    def generate_html(self, campaign_result: CampaignResult, config: ReportConfig) -> Path:
        """Generates HTML report with dark theme, benchmark overlay, matplotlib fallback, custom template."""

    def generate_json(self, campaign_result: CampaignResult, config: ReportConfig) -> Path:
        """Generates JSON report with benchmark_equity array if provided."""

    def generate(self, campaign_result: CampaignResult, config: ReportConfig) -> ReportResult:
        """Generates all requested formats."""
        ...

    def _try_plotly(self) -> bool:
        """Returns True if plotly available."""
        ...

    def _try_matplotlib(self) -> bool:
        """Returns True if matplotlib available (for reporting-matplotlib extra)."""
        ...

    def _render_chart_matplotlib(self, chart_type: str, data: dict) -> str:
        """Returns base64 PNG data URI for chart type."""
        ...
```

### Template Variables (Required for Custom Templates)

```jinja2
{# Required variables in template context #}
campaign_id: str
campaign_name: str
generated_at: str  # ISO8601
theme: "light" | "dark"
css_variables: dict  # CSS custom properties for theme
title: str
executive_summary: {
    net_profit: float,
    sharpe: float,
    max_drawdown: float,
    win_rate: float,
    profit_factor: float,
    assessment: str,
    indicator: "green" | "amber" | "red"
}
equity_curve_data: list[EquityPoint]
benchmark_equity_data: list[EquityPoint] | None
drawdown_data: list[EquityPoint]
trades_data: list[TradePoint]
metrics_table: list[dict]  # [{metric, value, formatted}]
phase_timing: list[dict]   # [{phase, status, duration_ms, start, end}]
benchmark_comparison: list[dict] | None  # [{metric, strategy, benchmark}]
charts: {
    equity: str,      # Plotly JSON or base64 PNG
    drawdown: str,
    trades: str,
    metrics: str
}
warnings: list[str]
```

### CLI Extension

```bash
quantlab report generate <campaign_id> \
    [--html] [--json] \
    [--output-dir PATH] \
    [--theme light|dark] \
    [--no-charts] \
    [--benchmark FILE] \          # CSV with timestamp,equity columns
    [--template PATH]             # NEW: custom Jinja2 template
```

Benchmark CSV format:
```csv
timestamp,equity
2024-01-01T00:00:00Z,100000
2024-01-02T00:00:00Z,100150
...
```

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Dark theme applies CSS variables + Plotly `plotly_dark` | Generate with `--theme dark`, inspect HTML for CSS vars and Plotly template |
| Benchmark overlay adds 2nd trace to equity chart | Unit test: pass benchmark, assert chart has 2 traces |
| Matplotlib fallback generates base64 PNG charts | Install `quantlab[reporting-matplotlib]` without plotly, generate HTML, assert `<img src="data:image/png` |
| Missing deps shows warning banner | Base install, generate HTML, assert banner text present |
| Custom template loads and renders | Provide valid `.j2` file, assert output matches template |
| Missing template falls back to default | Provide nonexistent path, assert default template used + warning |
| Executive summary shows 5 metrics + assessment | Generate report, parse HTML for executive summary section |
| Phase timing table has Phase/Status/Duration columns | Generate report, parse HTML table headers |
| Benchmark comparison table when benchmark provided | Pass benchmark equity, assert comparison table rendered |
| Optional extra `reporting-matplotlib` in pyproject.toml | `pip show quantlab` or inspect `pyproject.toml` |
| JSON includes benchmark_equity array | Generate JSON with benchmark, assert field present |

---

## Non-Functional Requirements

- **Performance**: HTML generation < 5s (Plotly), < 10s (matplotlib fallback) for 10k trades
- **Output size**: HTML < 5MB (Plotly), < 2MB (matplotlib PNGs); JSON < 1MB
- **Dependencies**: Base = `pydantic`, `pandas`, `jinja2`, `pyyaml`; `plotly` optional `[reporting]`; `matplotlib` optional `[reporting-matplotlib]`
- **Template stability**: Required template variables documented; breaking changes require major version
- **Backward compatibility**: Existing `ReportConfig` fields unchanged; new fields optional with defaults