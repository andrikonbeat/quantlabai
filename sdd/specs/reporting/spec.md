# Reporting Module Specification

## Purpose

Generates interactive HTML reports and machine-readable JSON summaries from `CampaignResult` objects. Produces publication-ready reports with interactive Plotly charts (equity curve, drawdown underwater, trade P&L scatter, metrics table) and JSON output for CI/CD integration. Optional Plotly dependency keeps base install lightweight.

---

## Requirements

### Requirement: Report Configuration Model

The system MUST provide a `ReportConfig` Pydantic model with fields:
- `campaign_id: str` — campaign identifier
- `output_dir: Path` — output directory (default: `reports/`)
- `formats: list[ReportFormat]` — output formats: `html`, `json`, or both (default: `["html", "json"]`)
- `include_charts: bool` — include Plotly charts in HTML (default: `True`)
- `theme: ReportTheme` — `"light"` or `"dark"` (default: `"light"`)
- `title: str | None` — custom report title (default: `"Campaign Report: {campaign_id}"`)
- `benchmark_equity: list[EquityPoint] | None` — optional benchmark equity curve for comparison

`ReportFormat` enum: `html`, `json`. `ReportTheme` enum: `light`, `dark`.

#### Scenario: Default config creates both HTML and JSON
- GIVEN a `ReportConfig` with only `campaign_id` set
- WHEN the config is validated
- THEN `formats` defaults to `["html", "json"]`, `include_charts` is `True`, `theme` is `"light"`

#### Scenario: Custom config with only JSON output
- GIVEN a `ReportConfig` with `formats=["json"]` and `include_charts=False`
- WHEN the config is validated
- THEN JSON-only report is generated without chart overhead

---

### Requirement: Report Result Model

The system MUST provide a `ReportResult` Pydantic model with fields:
- `campaign_id: str`
- `html_path: Path | None` — path to generated HTML report
- `json_path: Path | None` — path to generated JSON report
- `charts_generated: list[str]` — list of chart IDs included (e.g., `["equity_curve", "drawdown_underwater", "trade_scatter", "metrics_table"]`)
- `generation_time_ms: float`
- `warnings: list[str]` — any warnings during generation (e.g., "Plotly not installed, charts omitted")

#### Scenario: Successful HTML + JSON generation
- GIVEN a valid `CampaignResult` and `ReportConfig(formats=["html", "json"])`
- WHEN report is generated
- THEN `ReportResult` has both paths set, 4 charts listed, generation time > 0

#### Scenario: Plotly not installed, fallback documented
- GIVEN `plotly` not installed and `include_charts=True`
- WHEN report is generated
- THEN `html_path` exists with static matplotlib fallback note, `warnings` contains Plotly missing notice

---

### Requirement: HTML Report Generator

The system MUST provide a `ReportGenerator` class with method `generate_html(campaign_result: CampaignResult, config: ReportConfig) -> Path` that produces a single self-contained HTML file with:

1. **Equity Curve Chart** (interactive Plotly): timestamp vs equity, hover shows timestamp/equity/drawdown, range selector, benchmark overlay if provided
2. **Drawdown Underwater Chart**: timestamp vs drawdown %, filled area below zero, peak annotations
3. **Trade P&L Scatter Plot**: entry_time vs profit, color-coded by direction (long/short), hover shows trade details
4. **Metrics Summary Table**: all `StatsResult` fields formatted (Sharpe, PF, MDD, MAR, Expectancy, Win Rate, Total Trades)

HTML MUST be self-contained (embedded Plotly.js via CDN or bundled), responsive, and printable.

#### Scenario: Full HTML report with all charts
- GIVEN a `CampaignResult` with 100 trades and equity curve
- WHEN `generate_html()` is called
- THEN output file exists, contains 4 Plotly charts, metrics table has 8+ rows, file size < 5MB

#### Scenario: Benchmark overlay on equity curve
- GIVEN `config.benchmark_equity` provided
- WHEN equity curve chart renders
- THEN benchmark line appears with legend, different color, same timestamp axis

#### Scenario: Dark theme applies CSS variables
- GIVEN `config.theme == "dark"`
- WHEN HTML generates
- THEN CSS variables use dark palette, Plotly template is `"plotly_dark"`

---

### Requirement: JSON Report Generator

The system MUST provide `generate_json(campaign_result: CampaignResult, config: ReportConfig) -> Path` producing machine-readable JSON with schema:
```json
{
  "campaign_id": "string",
  "generated_at": "ISO8601",
  "summary": { "total_trades": 100, "net_profit": 15000, ... },
  "statistics": { "sharpe": 1.5, "profit_factor": 2.1, "max_drawdown": 12.5, ... },
  "equity_curve": [{ "timestamp": "ISO8601", "equity": 100000.0 }, ...],
  "trades": [{ "entry_time": "...", "exit_time": "...", "direction": "long", "profit": 150.0, ... }, ...],
  "phases": [{ "phase": "translate", "status": "completed", "duration_ms": 120 }, ...]
}
```
JSON MUST be valid against a documented JSON Schema (provided in `reporting/schemas/report.schema.json`).

#### Scenario: JSON report validates against schema
- GIVEN generated JSON report
- WHEN validated against `report.schema.json`
- THEN validation passes with no errors

#### Scenario: JSON includes all campaign data
- GIVEN a `CampaignResult` with trades, equity, phases
- WHEN JSON is generated
- THEN all arrays are non-empty (if source data exists), timestamps are ISO8601

---

### Requirement: Chart Configuration Model

The system MUST provide a `ChartConfig` Pydantic model for chart customization:
- `height: int = 500`
- `width: int | None = None` (responsive if None)
- `colors: ChartColors` — nested model with `equity`, `drawdown`, `long_trade`, `short_trade`, `benchmark`
- `show_range_slider: bool = True`
- `show_legend: bool = True`

Default colors MUST work for both light/dark themes.

#### Scenario: Custom chart colors applied
- GIVEN `ChartConfig(colors=ChartColors(equity="#00ff00", drawdown="#ff0000"))`
- WHEN charts render
- THEN equity line is green, drawdown area is red

---

### Requirement: CLI Report Generation Command

The system MUST provide `quantlab report generate <campaign_id> [--html] [--json] [--output-dir] [--theme] [--no-charts]` CLI command.

Options:
- `--html` / `--no-html` — generate HTML (default: on)
- `--json` / `--no-json` — generate JSON (default: on)
- `--output-dir PATH` — output directory (default: `reports/`)
- `--theme light|dark` — HTML theme (default: `light`)
- `--no-charts` — skip Plotly charts in HTML
- `--benchmark FILE` — path to benchmark equity CSV

Exit codes: `0` success, `1` campaign not found, `2` generation error, `3` invalid config.

#### Scenario: Generate both formats to custom directory
- GIVEN campaign `campaign-123` exists in Knowledge Lake
- WHEN `quantlab report generate campaign-123 --output-dir ./my-reports`
- THEN `./my-reports/campaign-123-report.html` and `.json` exist

#### Scenario: JSON only for CI/CD
- GIVEN `quantlab report generate campaign-123 --json --no-html --output-dir ./ci-artifacts`
- WHEN command runs
- THEN only JSON file created, valid schema, exit code 0

#### Scenario: Campaign not found returns exit code 1
- GIVEN campaign `nonexistent` not in Knowledge Lake
- WHEN `quantlab report generate nonexistent`
- THEN exit code 1, error message to stderr

---

### Requirement: Optional Plotly Dependency

The system MUST declare `plotly>=5.18` as optional extra `[reporting]` in `pyproject.toml`. If Plotly is not installed:
- HTML report generates with a banner noting "Interactive charts require `pip install quantlab[reporting]`"
- Matplotlib static fallback is documented (not implemented in MVP)
- JSON report works without any optional deps

#### Scenario: Base install works without Plotly
- GIVEN `pip install quantlab` (no extras)
- WHEN `generate_json()` is called
- THEN succeeds, no ImportError

#### Scenario: HTML warns when Plotly missing
- GIVEN `pip install quantlab` (no extras), `config.include_charts=True`
- WHEN `generate_html()` is called
- THEN HTML file created, warning in `ReportResult.warnings`, banner in HTML

---

## Data Flow

```
CampaignResult (from Knowledge Lake)
       │
       ├─► ReportConfig (CLI args → model)
       │
       ├─► ReportGenerator.generate_html()
       │     ├─► Extract equity curve → Plotly Figure
       │     ├─► Extract trades → Plotly Scatter
       │     ├─► Compute drawdown series → Plotly Area
       │     ├─► Format StatsResult → HTML Table
       │     └─► Render template with embedded Plotly.js → .html
       │
       └─► ReportGenerator.generate_json()
             ├─► Serialize CampaignResult to JSON schema
             └─► Write .json file
```

---

## Interface Specifications

```python
# quantlab.reporting.models
class ReportFormat(Enum):
    html = "html"
    json = "json"

class ReportTheme(Enum):
    light = "light"
    dark = "dark"

class ChartColors(BaseModel):
    equity: str = "#1f77b4"
    drawdown: str = "#d62728"
    long_trade: str = "#2ca02c"
    short_trade: str = "#ff7f0e"
    benchmark: str = "#9467bd"

class ChartConfig(BaseModel):
    height: int = 500
    width: int | None = None
    colors: ChartColors = Field(default_factory=ChartColors)
    show_range_slider: bool = True
    show_legend: bool = True

class ReportConfig(BaseModel):
    campaign_id: str
    output_dir: Path = Path("reports")
    formats: list[ReportFormat] = Field(default_factory=lambda: [ReportFormat.html, ReportFormat.json])
    include_charts: bool = True
    theme: ReportTheme = ReportTheme.light
    title: str | None = None
    benchmark_equity: list[EquityPoint] | None = None
    chart_config: ChartConfig = Field(default_factory=ChartConfig)

class ReportResult(BaseModel):
    campaign_id: str
    html_path: Path | None = None
    json_path: Path | None = None
    charts_generated: list[str] = Field(default_factory=list)
    generation_time_ms: float
    warnings: list[str] = Field(default_factory=list)

# quantlab.reporting.generator
class ReportGenerator:
    def __init__(self, knowledge_root: Path | None = None):
        ...

    def generate_html(self, campaign_result: CampaignResult, config: ReportConfig) -> Path:
        ...

    def generate_json(self, campaign_result: CampaignResult, config: ReportConfig) -> Path:
        ...

    def generate(self, campaign_result: CampaignResult, config: ReportConfig) -> ReportResult:
        """Generates all requested formats, returns ReportResult."""
        ...

# quantlab.reporting.cli
def report_generate_command(args: argparse.Namespace) -> int:
    ...
```

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| HTML report opens in browser with 4 interactive charts | Manual: open `report.html`, verify hover, zoom, range slider work |
| JSON report validates against `report.schema.json` | Automated: `jsonschema.validate(instance, schema)` passes |
| CLI `quantlab report generate` produces both formats by default | Integration test: run CLI, assert both files exist |
| Plotly optional dependency: base install works for JSON only | CI: `pip install quantlab` → `generate_json()` succeeds |
| Dark theme applies correct CSS/Plotly template | Visual: generate with `--theme dark`, verify colors |
| Benchmark overlay appears when provided | Unit test: pass benchmark equity, assert chart has 2 traces |
| Generation time < 5s for 1000 trades | Performance test: measure `generation_time_ms` |
| Exit codes correct for success/not found/error | Integration tests for each exit code |

---

## Non-Functional Requirements

- **Performance**: HTML generation < 5s for 10k trades, JSON < 1s
- **Output size**: HTML < 5MB (embedded Plotly.js ~3MB), JSON < 1MB
- **Dependencies**: Base install = `pydantic`, `pandas`, `pyyaml`; `plotly` optional extra
- **Schema versioning**: JSON schema includes `$schema` and `version` field for forward compatibility