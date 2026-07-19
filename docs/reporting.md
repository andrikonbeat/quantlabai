# Reporting Module

Generates interactive HTML and JSON campaign reports with Plotly charts, matplotlib fallback, and customizable Jinja2 templates.

> **SDK Reference**: [`sdk/quantlab/reporting/`](../sdk/quantlab/reporting/)

---

## Installation

```bash
# Base install (no charting)
pip install quantlab

# With interactive Plotly charts (recommended)
pip install quantlab[reporting]

# With matplotlib static PNG fallback
pip install quantlab[reporting-matplotlib]

# Both (Plotly preferred, matplotlib as fallback)
pip install quantlab[reporting] quantlab[reporting-matplotlib]
```

### Behavior Matrix

| Install | Plotly | Matplotlib | HTML Charts |
|---------|--------|------------|-------------|
| `quantlab` | ❌ | ❌ | Warning banner only |
| `quantlab[reporting]` | ✅ | ❌ | Interactive Plotly |
| `quantlab[reporting-matplotlib]` | ❌ | ✅ | Static PNG (base64) |
| Both | ✅ | ✅ | Interactive Plotly (preferred) |

---

## CLI Usage

```bash
# Basic report generation
quantlab report generate smoke_test_campaign

# Specify output directory
quantlab report generate smoke_test_campaign --output-dir reports

# Dark theme
quantlab report generate smoke_test_campaign --theme dark

# HTML-only (no JSON)
quantlab report generate smoke_test_campaign --no-json

# JSON-only (no HTML)
quantlab report generate smoke_test_campaign --no-html

# Disable charts
quantlab report generate smoke_test_campaign --no-charts

# Custom report title
quantlab report generate smoke_test_campaign --title "My Backtest Report"

# Custom Jinja2 template
quantlab report generate smoke_test_campaign --template custom_template.j2

# Benchmark overlay (CSV with timestamp,equity columns)
quantlab report generate smoke_test_campaign --benchmark benchmark.csv

# Set Knowledge Lake root
quantlab report generate smoke_test_campaign --knowledge-root /path/to/knowledge

# Combined
quantlab report generate smoke_test_campaign \
  --theme dark \
  --benchmark benchmark.csv \
  --template custom.j2 \
  --title "Final Results" \
  --output-dir ./reports
```

### CLI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `campaign_id` | positional | — | Campaign identifier (from Knowledge Lake stats) |
| `--output-dir` | path | `reports/` | Output directory for generated files |
| `--knowledge-root` | path | `knowledge/` | Knowledge Lake root path |
| `--html` / `--no-html` | flag | `True` | Generate HTML report |
| `--json` / `--no-json` | flag | `True` | Generate JSON report |
| `--theme` | choice | `light` | Report theme: `light` or `dark` |
| `--no-charts` | flag | `False` | Skip chart generation |
| `--title` | string | — | Custom report title |
| `--template` | path | — | Custom Jinja2 template file |
| `--benchmark` | path | — | Benchmark equity CSV for comparison |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — report generated |
| `1` | Campaign not found in Knowledge Lake |
| `2` | Generation error |

---

## Themes

### Light Theme (Default)

Clean white background with dark text. Uses Plotly's `plotly_white` template.

### Dark Theme

Dark background (`#1A1A2E`) with light text (`#EAEAEA`). Uses Plotly's `plotly_dark` template.

CSS variables are injected for both themes:

| Variable | Light Default | Dark Default | Description |
|----------|---------------|--------------|-------------|
| `--color-equity-up` | `#2A9D8F` | `#4ECDC4` | Positive equity color |
| `--color-equity-down` | `#E63946` | `#FF6B6B` | Negative equity color |
| `--color-equity-line` | `#2E86AB` | `#48CAE4` | Equity curve line |
| `--color-drawdown-fill` | `#E63946` | `#FF6B6B` | Drawdown fill |
| `--color-drawdown-line` | `#A62836` | `#E63946` | Drawdown line |
| `--color-trade-win` | `#2A9D8F` | `#4ECDC4` | Winning trade |
| `--color-trade-loss` | `#E63946` | `#FF6B6B` | Losing trade |
| `--color-benchmark-line` | `#F4A261` | `#FFD93D` | Benchmark overlay |
| `--color-grid` | `#E0E0E0` | `#0F3460` | Grid lines |
| `--color-background` | `#FFFFFF` | `#1A1A2E` | Page background |
| `--color-text` | `#1A1A2E` | `#EAEAEA` | Text color |

---

## Benchmark CSV Format

The benchmark equity file must be a CSV with `timestamp` and `equity` columns:

```csv
timestamp,equity
2024-01-01T00:00:00,10000
2024-01-02T00:00:00,10150
2024-01-03T00:00:00,10050
2024-01-04T00:00:00,10300
```

Alternative column names accepted: `Timestamp`, `Time`, `Equity`, `Value`.

The benchmark is parsed into `EquityPoint` objects and rendered as a dashed overlay line on the equity curve chart. A benchmark comparison table is also added:

| Metric | Strategy | Benchmark |
|--------|----------|-----------|
| Total Return | `+5.00%` | `+3.00%` |
| Sharpe Ratio | `1.50` | `0.00 (N/A)` |
| Max Drawdown | `-5.00%` | `0.00% (N/A)` |

---

## Custom Templates

The reporting module supports custom Jinja2 templates via `--template <path>`.

### Template Variables

All variables below are available in the render context:

| Variable | Type | Description |
|----------|------|-------------|
| `title` | str | Report title |
| `campaign_id` | str | Campaign identifier |
| `theme_class` | str | CSS class `theme-light` or `theme-dark` |
| `css_variables` | str | CSS custom properties for light theme |
| `css_variables_dark` | str | CSS custom properties for dark theme |
| `metrics_rows` | str | HTML table rows for key metrics |
| `trade_count` | int | Number of trades |
| `equity_count` | int | Number of equity points |
| `summary_rows` | str | HTML rows for campaign summary |
| `phase_rows` | str | HTML rows for phase timing |
| `charts_json` | str | JSON-encoded chart data (Plotly) |
| `plotly_available` | bool | Whether Plotly is installed |
| `matplotlib_available` | bool | Whether matplotlib fallback is active |
| `executive_summary` | dict | Executive summary with assessment/indicator |
| `executive_summary_section` | str | Pre-rendered HTML for executive summary |
| `benchmark_comparison` | list | Benchmark comparison data |
| `benchmark_section` | str | Pre-rendered HTML for benchmark comparison |
| `generation_time` | str | ISO timestamp of generation |

### Executive Summary Structure

```python
{
    "net_profit": 1.5,
    "sharpe": 1.2,
    "max_drawdown": 5.0,
    "win_rate": 0.6,
    "profit_factor": 1.5,
    "assessment": "Moderate risk-adjusted returns",
    "indicator": "amber"  # "green" | "amber" | "red"
}
```

Assessment thresholds:
- **Green** (Sharpe ≥ 2.0): "Strong risk-adjusted returns"
- **Amber** (Sharpe ≥ 1.0): "Moderate risk-adjusted returns"
- **Red** (Sharpe < 1.0): "Weak risk-adjusted returns"

### Minimal Custom Template Example

```jinja2
<!DOCTYPE html>
<html class="{{ theme_class }}">
<head><title>{{ title }}</title></head>
<body>
  <h1>{{ title }}</h1>
  <p>Campaign: {{ campaign_id }}</p>
  <p>Generated: {{ generation_time }}</p>
  {{ executive_summary_section }}
  {{ benchmark_section }}
</body>
</html>
```

---

## Matplotlib Fallback

When Plotly is not installed but `quantlab[reporting-matplotlib]` is, charts are rendered as static PNG images embedded in the HTML as base64 data URIs.

```python
# The generator detects availability at module level
from quantlab.reporting.generator import PLOTLY_AVAILABLE, MATPLOTLIB_AVAILABLE
print(f"Plotly: {PLOTLY_AVAILABLE}, Matplotlib: {MATPLOTLIB_AVAILABLE}")
```

The fallback respects the active theme (dark/light) and renders all four chart types:
- Equity curve
- Drawdown underwater
- Trade P&L scatter
- Metrics table

---

## JSON Output Schema

```json
{
  "campaign_id": "smoke_test_campaign",
  "generated_at": 1721318400.0,
  "statistics": {
    "profit_factor": 1.5,
    "sharpe_ratio": 1.2,
    "max_drawdown": 5.0,
    "win_rate": 0.6,
    "total_trades": 10
  },
  "trade_count": 10,
  "equity_points": 10,
  "trades": [
    {
      "entry_time": "2024-01-01T10:00:00",
      "exit_time": "2024-01-01T10:30:00",
      "direction": "long",
      "lots": 1.0,
      "profit": 100.0
    }
  ],
  "equity_curve": [
    {
      "timestamp": "2024-01-01T00:00:00",
      "equity": 10000.0
    }
  ],
  "benchmark_equity": null,
  "executive_summary": {
    "net_profit": 1.5,
    "sharpe": 1.2,
    "max_drawdown": 5.0,
    "win_rate": 0.6,
    "profit_factor": 1.5,
    "assessment": "Moderate risk-adjusted returns",
    "indicator": "amber"
  },
  "summary": {},
  "phase_results": []
}
```

---

## Report Sections

| Section | Description | Conditional |
|---------|-------------|-------------|
| Header | Title, campaign ID, generation timestamp | No |
| Executive Summary | Assessment bar + key metrics (PF, Sharpe, DD, Win Rate) | No |
| Equity Curve | Interactive chart with optional benchmark overlay | Equity data required |
| Drawdown Underwater | Drawdown percentage chart | Equity data required |
| Trade P&L Scatter | Profit/loss distribution | Trade data required |
| Key Metrics Table | 9 metrics: PF, Sharpe, Sortino, DD, Expectancy, Win Rate, Trades, MAR, Recovery | Statistics required |
| Phase Timing | Table of campaign phase durations | Phase results provided |
| Benchmark Comparison | Strategy vs benchmark metrics | Benchmark CSV provided |
| Summary | Custom campaign summary | Summary dict provided |

---

## Programmatic API

```python
from pathlib import Path
from quantlab.readers.models import Trade, EquityPoint
from quantlab.stats.models import StatsResult
from quantlab.reporting import ReportGenerator, ReportConfig, ReportTheme

# Configure
config = ReportConfig(
    campaign_id="my_campaign",
    output_dir=Path("reports"),
    theme=ReportTheme.DARK,
    include_charts=True,
    template_path=Path("custom.j2"),  # optional
    benchmark_equity=benchmark_data,  # list[EquityPoint], optional
)

# Create generator
generator = ReportGenerator(config)

# Generate report
result = generator.generate(
    campaign_id="my_campaign",
    trades=trades,           # list[Trade]
    equity=equity,           # list[EquityPoint]
    statistics=stats,        # StatsResult
    phase_results=phases,    # list[dict], optional
    summary=summary_data,    # dict, optional
)

print(f"HTML: {result.html_path}")
print(f"JSON: {result.json_path}")
print(f"Warnings: {result.warnings}")
```

### Convenience Function

```python
from quantlab.reporting import generate_report

result = generate_report(
    campaign_id="my_campaign",
    trades=trades,
    equity=equity,
    statistics=stats,
    config=ReportConfig(campaign_id="my_campaign"),
)
```
