# Documentation Specification

## Purpose

Comprehensive user-facing documentation for QuantLab AI CLI commands, pipeline YAML schema, reporting module, and knowledge query syntax. Four new documents + README updates.

---

## Requirements

### Requirement: FR-001 — README.md Updates

The system SHALL update `README.md` with new sections for `report`, `knowledge`, and `pipeline` commands.

#### Section: Pipeline Commands

```markdown
## Pipeline Commands

QuantLab AI provides a pipeline execution framework for walk-forward optimization and strategy validation.

### List Available Pipelines
```bash
quantlab pipeline list
quantlab pipeline list --json
```

### Run Pipeline (Dry-Run)
Outputs CFX base64 without executing SQX:
```bash
quantlab pipeline run wf_opt --dry-run
quantlab pipeline run wf_opt --dry-run --output-dir ./output
```

### Run Pipeline (Real Execution)
Executes all SQX stages and persists results to Knowledge Lake:
```bash
quantlab pipeline run wf_opt
quantlab pipeline run wf_opt --params window=10 --params step=2
quantlab pipeline run wf_opt --config custom_pipeline.yaml --timeout 300
```

### Pipeline History
```bash
quantlab pipeline history
quantlab pipeline history --status completed --limit 20
quantlab pipeline history --json
```

### Pipeline Configuration
See [Pipeline YAML Schema](docs/pipeline-yaml.md) for complete schema reference.
```

#### Section: Report Commands

```markdown
## Report Commands

Generate publication-grade HTML and JSON reports from campaign results.

### Install Reporting Extras
```bash
# Interactive Plotly charts (default)
pip install quantlab[reporting]

# Matplotlib static fallback (no Plotly needed)
pip install quantlab[reporting-matplotlib]
```

### Generate Report
```bash
# Both HTML + JSON (default)
quantlab report generate campaign-123

# Dark theme
quantlab report generate campaign-123 --theme dark

# Benchmark overlay (CSV with timestamp,equity columns)
quantlab report generate campaign-123 --benchmark benchmark.csv

# Custom Jinja2 template
quantlab report generate campaign-123 --template ./my_report.j2

# JSON only (CI/CD)
quantlab report generate campaign-123 --json --no-html --output-dir ./ci-artifacts
```

### Report Sections
- Executive Summary (key metrics + assessment)
- Equity Curve (interactive Plotly, benchmark overlay)
- Drawdown Underwater Chart
- Trade P&L Scatter Plot
- Metrics Summary Table
- Phase Timing Table
- Benchmark Comparison Table (when benchmark provided)

See [Reporting Documentation](docs/reporting.md) for details.
```

#### Section: Knowledge Commands

```markdown
## Knowledge Lake Commands

Query, tag, and link campaigns in the Knowledge Lake.

### Query Campaigns
```bash
# By Sharpe ratio
quantlab knowledge query --sharpe ">1.5"

# Multiple filters
quantlab knowledge query --sharpe ">1.0" --pf ">2.0" --tag strategy=trend --tag market=forex

# Date range + text search
quantlab knowledge query --date "2024-01-01..2024-12-31" --text "eurusd"

# JSON output for scripting
quantlab knowledge query --sharpe ">1.0" --json --limit 10
```

### Tag Campaigns
```bash
quantlab knowledge tag campaign-123 --tag strategy=mean_reversion --tag version=v2
quantlab knowledge tag campaign-123 --show
```

### Link Campaigns (parent/child)
```bash
quantlab knowledge link campaign-parent --children campaign-child-1 campaign-child-2
quantlab knowledge link campaign-child-1 --show-links
```

See [Knowledge Query Documentation](docs/knowledge-query.md) for complete syntax.
```

---

### Requirement: FR-002 — docs/pipeline-yaml.md (Complete Pipeline YAML Schema)

The system SHALL create `docs/pipeline-yaml.md` documenting the complete pipeline YAML schema.

#### Document Structure

```markdown
# Pipeline YAML Schema Reference

Complete schema for QuantLab AI pipeline configuration files.

## File Location
- Built-in: `config/pipelines/*.yaml`
- User: `~/.quantlab/pipelines/*.yaml`

## Top-Level Structure

```yaml
name: "pipeline-identifier"          # required, unique, kebab-case
description: "Human-readable description"  # required
version: "1.0"                       # required, semver
stages:                              # required, list of stage configs
  - name: "stage-name"
    type: "stage-type"               # must match registered type
    config: {}                       # stage-specific config (optional)
    timeout: 300                     # optional, seconds (default: 300)
    retry: 0                         # optional, retry count (default: 0)
```

## Stage Types

All stage types are registered in `PipelineRegistry`. Built-in SQX stages (from `phase4.stages`):

| Type | Class | Description |
|------|-------|-------------|
| `validate` | `SQXValidateStage` | Validate SQX strategy syntax |
| `translate` | `SQXTranslateStage` | Translate SQX → CFX |
| `optimize` | `SQXOptimizeStage` | Walk-forward parameter optimization |
| `walkforward` | `SQXWalkForwardStage` | Walk-forward analysis |
| `montecarlo` | `SQXMonteCarloStage` | Monte Carlo simulation |
| `portfolio` | `SQXPortfolioStage` | Portfolio composition |
| `risk` | `SQRiskStage` | Risk analysis |
| `report` | `SQXReportStage` | Generate reports |
| `knowledge_store` | `SQXKnowledgeStoreStage` | Persist to Knowledge Lake |
| `history` | `SQXHistoryStage` | Record pipeline history |
| `finalize` | `SQXFinalizeStage` | Cleanup and summary |

## Stage Configurations

Each stage type accepts specific config fields. All configs are optional unless marked required.

### validate
```yaml
config:
  sqx_path: "strategies/my_strategy.sqx"  # required
  strict: true                              # optional, default: true
```

### translate
```yaml
config:
  sqx_path: "strategies/my_strategy.sqx"   # required
  output_format: "cfx"                     # optional, default: "cfx"
```

### optimize
```yaml
config:
  parameter_space:                         # required
    param_name:
      min: 5
      max: 50
      step: 5
  objective: "sharpe"                      # optional: sharpe, pf, net_profit
  walkforward_window: 252                  # optional, trading days
  step_size: 63                            # optional
```

### walkforward
```yaml
config:
  window_days: 252                         # optional, default: 252
  step_days: 63                            # optional, default: 63
  anchor: "start"                          # optional: start, end
```

### montecarlo
```yaml
config:
  simulations: 1000                        # optional, default: 1000
  confidence_level: 0.95                   # optional, default: 0.95
  method: "bootstrap"                      # optional: bootstrap, parametric
```

### portfolio
```yaml
config:
  max_positions: 10                        # optional, default: 10
  allocation_method: "equal_weight"        # optional: equal_weight, risk_parity
  rebalance_frequency: "monthly"           # optional: daily, weekly, monthly
```

### risk
```yaml
config:
  var_confidence: 0.99                     # optional, default: 0.99
  var_horizon: 1                           # optional, days
  stress_scenarios: []                     # optional, list of scenario names
```

### report
```yaml
config:
  template: "default"                      # optional: default, custom path
  theme: "light"                           # optional: light, dark
  include_charts: true                     # optional, default: true
  benchmark_equity: "data/benchmark.csv"   # optional
```

### knowledge_store
```yaml
config:
  campaign_id: "auto"                      # optional: auto, or explicit ID
  tags: {}                                 # optional, dict of tags
```

### history
```yaml
config: {}                                 # no config options
```

### finalize
```yaml
config:
  cleanup_temp: true                       # optional, default: true
  notify: false                            # optional, default: false
```

## Parameter Overrides

CLI `--params key=value` overrides stage config at runtime:
```bash
quantlab pipeline run wf_opt --params optimize.parameter_space.param_name.min=10
```

Syntax: `stage_name.config_key=value` (dot notation for nested keys).

## Complete Example

```yaml
name: "wf_opt_v2"
description: "Walk-forward optimization with Monte Carlo validation"
version: "2.1"
stages:
  - name: validate
    type: validate
    config:
      sqx_path: "strategies/mean_reversion.sqx"
    timeout: 60

  - name: translate
    type: translate
    config:
      sqx_path: "strategies/mean_reversion.sqx"
    timeout: 60

  - name: optimize
    type: optimize
    config:
      parameter_space:
        lookback:
          min: 10
          max: 50
          step: 5
        threshold:
          min: 0.5
          max: 2.0
          step: 0.25
      objective: "sharpe"
      walkforward_window: 252
      step_size: 63
    timeout: 600

  - name: walkforward
    type: walkforward
    config:
      window_days: 252
      step_days: 63
    timeout: 300

  - name: montecarlo
    type: montecarlo
    config:
      simulations: 2000
      confidence_level: 0.95
    timeout: 300

  - name: portfolio
    type: portfolio
    config:
      max_positions: 5
      allocation_method: "risk_parity"
    timeout: 60

  - name: risk
    type: risk
    config:
      var_confidence: 0.99
    timeout: 60

  - name: report
    type: report
    config:
      theme: "dark"
      include_charts: true
    timeout: 60

  - name: knowledge_store
    type: knowledge_store
    config:
      campaign_id: "auto"
      tags:
        strategy: "mean_reversion"
        version: "2.1"
    timeout: 30

  - name: history
    type: history
    timeout: 10

  - name: finalize
    type: finalize
    config:
      cleanup_temp: true
    timeout: 10
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `QUANTLAB_KNOWLEDGE_ROOT` | Knowledge Lake root path | `./knowledge` |
| `QUANTLAB_SQX_PATH` | Path to SQX binary | auto-detect |
| `QUANTLAB_PIPELINE_TIMEOUT` | Default stage timeout (seconds) | `300` |

## Validation

Run `quantlab pipeline run <name> --dry-run` to validate config without executing.
```

---

### Requirement: FR-003 — docs/reporting.md (Reporting Documentation)

The system SHALL create `docs/reporting.md` documenting reporting features.

#### Document Structure

```markdown
# Reporting Module Documentation

Generate publication-grade HTML and JSON reports from campaign results.

## Installation

```bash
# Interactive Plotly charts (recommended)
pip install quantlab[reporting]

# Static matplotlib fallback (no Plotly required)
pip install quantlab[reporting-matplotlib]

# Both
pip install quantlab[reporting,reporting-matplotlib]
```

## CLI Usage

```bash
quantlab report generate <campaign_id> [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--html` / `--no-html` | Generate HTML report | `--html` |
| `--json` / `--no-json` | Generate JSON report | `--json` |
| `--output-dir PATH` | Output directory | `reports/` |
| `--theme light\|dark` | HTML theme | `light` |
| `--no-charts` | Skip charts in HTML | charts included |
| `--benchmark FILE` | Benchmark equity CSV | none |
| `--template FILE` | Custom Jinja2 template | built-in |

### Output Files

- `<campaign_id>-report.html` — Interactive HTML report
- `<campaign_id>-report.json` — Machine-readable JSON

## Themes

### Light Theme (Default)
Clean white background, standard Plotly colors.

### Dark Theme
```bash
quantlab report generate campaign-123 --theme dark
```
- CSS variables for all colors (see Custom Templates)
- Plotly `plotly_dark` template
- Automatic contrast for text/charts

## Benchmark Overlay

Compare strategy equity curve against a benchmark (e.g., buy-and-hold, index).

```bash
quantlab report generate campaign-123 --benchmark data/sp500_equity.csv
```

### Benchmark CSV Format

```csv
timestamp,equity
2024-01-01T00:00:00Z,100000
2024-01-02T00:00:00Z,100150
2024-01-03T00:00:00Z,99800
```

- Timestamps: ISO8601 (UTC recommended)
- Equity: Numeric portfolio value
- Must cover same date range as campaign for meaningful comparison

### Report Sections Added

When benchmark provided:
- Equity Curve: Second trace "Benchmark" (purple)
- Benchmark Comparison Table: Strategy vs Benchmark on Return, Volatility, Sharpe, Max DD, Correlation

## Custom Templates

Override the default HTML template with a custom Jinja2 template.

```bash
quantlab report generate campaign-123 --template ./my_template.j2
```

### Required Template Variables

Your template MUST provide these variables (provided by `ReportGenerator`):

| Variable | Type | Description |
|----------|------|-------------|
| `campaign_id` | str | Campaign identifier |
| `campaign_name` | str | Human-readable name |
| `generated_at` | str | ISO8601 timestamp |
| `theme` | "light"\|"dark" | Active theme |
| `css_variables` | dict | CSS custom properties for theme |
| `title` | str | Report title |
| `executive_summary` | dict | See below |
| `equity_curve_data` | list[dict] | `{timestamp, equity}` points |
| `benchmark_equity_data` | list[dict] \| null | Benchmark points |
| `drawdown_data` | list[dict] | `{timestamp, drawdown_pct}` points |
| `trades_data` | list[dict] | Trade records |
| `metrics_table` | list[dict] | `[{metric, value, formatted}]` |
| `phase_timing` | list[dict] | `[{phase, status, duration_ms, start, end}]` |
| `benchmark_comparison` | list[dict] \| null | `[{metric, strategy, benchmark}]` |
| `charts` | dict | `{equity, drawdown, trades, metrics}` Plotly JSON or base64 PNG |
| `warnings` | list[str] | Generation warnings |

### Executive Summary Structure

```python
executive_summary = {
    "net_profit": 25000.0,
    "sharpe": 1.8,
    "max_drawdown": 8.5,
    "win_rate": 58.3,
    "profit_factor": 2.1,
    "assessment": "Strong risk-adjusted returns with controlled drawdown",
    "indicator": "green"  # "green" | "amber" | "red"
}
```

### CSS Variables (for dark/light themes)

```css
:root {
  --color-bg: #ffffff;
  --color-text: #1a1a2e;
  --color-primary: #1f77b4;
  --color-secondary: #ff7f0e;
  --color-equity: #1f77b4;
  --color-drawdown: #d62728;
  --color-long: #2ca02c;
  --color-short: #ff7f0e;
  --color-benchmark: #9467bd;
  --color-grid: #e0e0e0;
  --color-border: #cccccc;
}

.theme-dark {
  --color-bg: #1a1a2e;
  --color-text: #eaeaea;
  --color-primary: #4da6ff;
  --color-secondary: #ffa64d;
  --color-equity: #00d4aa;
  --color-drawdown: #ff6b6b;
  --color-long: #4ade80;
  --color-short: #fb923c;
  --color-benchmark: #c084fc;
  --color-grid: #333344;
  --color-border: #444455;
}
```

### Default Template Location

`src/quantlab/reporting/templates/default_report.html.j2` (embedded in package).

## Matplotlib Fallback

If Plotly not installed but `quantlab[reporting-matplotlib]` is:
- Charts rendered as static PNG (base64 embedded in HTML)
- No interactivity (hover, zoom, range slider)
- Warning added to report: "Using matplotlib static fallback"

Install:
```bash
pip install quantlab[reporting-matplotlib]
```

## JSON Output Schema

```json
{
  "campaign_id": "campaign-123",
  "generated_at": "2024-07-18T12:00:00Z",
  "summary": {
    "total_trades": 150,
    "net_profit": 25000.0,
    "winning_trades": 88,
    "losing_trades": 62
  },
  "statistics": {
    "sharpe": 1.8,
    "profit_factor": 2.1,
    "max_drawdown": 8.5,
    "win_rate": 58.3,
    "expectancy": 166.7,
    "mar_ratio": 2.94
  },
  "equity_curve": [
    {"timestamp": "2024-01-01T00:00:00Z", "equity": 100000.0}
  ],
  "benchmark_equity": [
    {"timestamp": "2024-01-01T00:00:00Z", "equity": 100000.0}
  ],
  "trades": [
    {"entry_time": "...", "exit_time": "...", "direction": "long", "profit": 150.0, "symbol": "EURUSD"}
  ],
  "phases": [
    {"phase": "translate", "status": "completed", "duration_ms": 1200}
  ],
  "charts_generated": ["equity_curve", "drawdown_underwater", "trade_scatter", "metrics_table"],
  "warnings": []
}
```

## Report Sections Detail

| Section | Description | Theme Aware |
|---------|-------------|-------------|
| Executive Summary | 5 key metrics + qualitative assessment | Yes |
| Equity Curve | Interactive Plotly line chart, benchmark overlay | Yes |
| Drawdown Underwater | Filled area chart, peak annotations | Yes |
| Trade P&L Scatter | Entry time vs profit, color by direction | Yes |
| Metrics Table | All statistics formatted | Yes |
| Phase Timing | Pipeline phase durations | Yes |
| Benchmark Comparison | Strategy vs benchmark metrics table | Yes |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Campaign not found in Knowledge Lake |
| 2 | Generation error (template, data, etc.) |
| 3 | Invalid configuration |

## Programmatic API

```python
from quantlab.reporting import ReportGenerator, ReportConfig, ReportTheme
from quantlab.knowledge import KnowledgeStore

store = KnowledgeStore()
campaign = store.load_campaign("campaign-123")

config = ReportConfig(
    campaign_id="campaign-123",
    theme=ReportTheme.dark,
    benchmark_equity=[...],  # list of EquityPoint
    template_path=Path("custom.j2")
)

generator = ReportGenerator()
result = generator.generate(campaign, config)

print(result.html_path)
print(result.json_path)
print(result.warnings)
```
```

---

### Requirement: FR-004 — docs/knowledge-query.md (Knowledge Query Documentation)

The system SHALL create `docs/knowledge-query.md` documenting query syntax, tag/link commands, and export formats.

#### Document Structure

```markdown
# Knowledge Lake Query Documentation

Query, tag, and link campaigns in the QuantLab AI Knowledge Lake.

## Overview

The Knowledge Lake stores campaign results, metadata, and metrics in a filesystem-based index. The query system provides filtering, search, and relationship management.

## CLI: `quantlab knowledge query`

### Basic Syntax

```bash
quantlab knowledge query [FILTERS] [OPTIONS]
```

### Filter Options

| Option | Syntax | Description |
|--------|--------|-------------|
| `--sharpe` | `">1.5"`, `">=1.0"`, `"<2.0"`, `"1.0..2.0"` | Sharpe ratio range |
| `--pf` | `">2.0"`, `">=1.5"` | Profit Factor range |
| `--win-rate` | `">50"`, `"40..60"` | Win rate percentage range |
| `--mdd` | `"<10"`, `"5..15"` | Max Drawdown percentage range |
| `--tag` | `KEY=VALUE` (repeatable) | Tag filters (ALL must match) |
| `--date` | `"2024-01-01..2024-12-31"` | Created date range |
| `--text` | `"search term"` | Full-text search |

### Range Syntax

| Syntax | Meaning |
|--------|---------|
| `">1.5"` | Greater than 1.5 |
| `">=1.0"` | Greater than or equal |
| `"<2.0"` | Less than 2.0 |
| `"<=10"` | Less than or equal |
| `"1.0..2.0"` | Between 1.0 and 2.0 (inclusive) |

### Sorting & Output

| Option | Description | Default |
|--------|-------------|---------|
| `--sort FIELD` | Sort field: `sharpe`, `pf`, `win_rate`, `mdd`, `created`, `net_profit` | `sharpe` |
| `--desc` / `--asc` | Sort direction | `--desc` |
| `--limit N` | Max results | `20` |
| `--json` | Output as JSON array | table |
| `--show-tags` / `--hide-tags` | Include tags in output | show |
| `--show-links` / `--hide-links` | Include links in output | show |

### Examples

```bash
# High Sharpe trend strategies in forex
quantlab knowledge query --sharpe ">1.5" --tag strategy=trend --tag market=forex

# Recent campaigns with good profit factor
quantlab knowledge query --pf ">2.0" --date "2024-01-01..2024-12-31" --sort pf --desc

# Text search in tags and campaign IDs
quantlab knowledge query --text "eurusd" --json

# All campaigns, JSON for scripting
quantlab knowledge query --json --limit 100

# Low drawdown, high win rate
quantlab knowledge query --mdd "<5" --win-rate ">60"
```

### Output Formats

#### Table (Default)

```
campaign_id          | created               | sharpe | pf    | win%  | mdd%  | trades | tags
---------------------|-----------------------|--------|-------|-------|-------|--------|------------------
campaign-abc123      | 2024-07-15T10:30:00Z | 1.82   | 2.15  | 58.3  | 8.5   | 150    | strategy=trend
campaign-def456      | 2024-07-14T15:22:00Z | 1.65   | 1.98  | 55.1  | 10.2  | 200    | strategy=mean_rev
```

#### JSON (`--json`)

```json
[
  {
    "campaign_id": "campaign-abc123",
    "created": "2024-07-15T10:30:00Z",
    "metrics": {
      "sharpe": 1.82,
      "profit_factor": 2.15,
      "win_rate": 58.3,
      "max_drawdown": 8.5,
      "total_trades": 150,
      "net_profit": 25000.0
    },
    "tags": {"strategy": "trend", "market": "forex"},
    "links": ["campaign-parent-789"],
    "artifact_path": "knowledge/structured/campaign-abc123"
  }
]
```

## CLI: `quantlab knowledge tag`

Add or view tags on a campaign.

```bash
# Add/update tags (merges with existing)
quantlab knowledge tag campaign-123 --tag strategy=mean_reversion --tag version=v2

# View tags
quantlab knowledge tag campaign-123 --show
```

### Tag Rules
- Key-value pairs, both strings
- Keys: alphanumeric + underscore, max 32 chars
- Values: any string, max 128 chars
- `--tag` merges with existing (does not replace)
- Stored in campaign's `metadata.yaml`, reflected in index on rebuild

## CLI: `quantlab knowledge link`

Create bidirectional parent-child relationships between campaigns.

```bash
# Link parent to children
quantlab knowledge link campaign-parent --children campaign-child-1 campaign-child-2

# View links for a campaign
quantlab knowledge link campaign-child-1 --show-links
```

### Link Rules
- Bidirectional: parent→children, children→parent stored in both
- Multiple parents allowed (many-to-many)
- Stored in both campaigns' `metadata.yaml`
- Reflected in index `links` array on rebuild

## Index Rebuild

After tagging/linking, rebuild index to update query results:

```bash
quantlab knowledge rebuild-index
# or programmatically:
from quantlab.knowledge import KnowledgeStore
KnowledgeStore().rebuild_index()
```

## Export Formats

### JSON (CLI)
```bash
quantlab knowledge query --sharpe ">1.0" --json > high_sharpe.json
```

### CSV (Programmatic)
```python
from quantlab.knowledge import KnowledgeStore
import pandas as pd

store = KnowledgeStore()
results = store.query().filter_by_sharpe(min=1.0).execute()

df = pd.DataFrame([{
    "campaign_id": c.campaign_id,
    "created": c.created,
    "sharpe": c.metrics.sharpe,
    "profit_factor": c.metrics.profit_factor,
    "win_rate": c.metrics.win_rate,
    "max_drawdown": c.metrics.max_drawdown,
    "total_trades": c.metrics.total_trades,
    "net_profit": c.metrics.net_profit,
    **{f"tag_{k}": v for k, v in c.tags.items()}
} for c in results.campaigns])

df.to_csv("campaigns.csv", index=False)
```

### Parquet (Programmatic)
```python
df.to_parquet("campaigns.parquet")
```

## Programmatic API

```python
from quantlab.knowledge import KnowledgeStore

store = KnowledgeStore()

# Query
qb = store.query()
results = (qb
    .filter_by_sharpe(min=1.5)
    .filter_by_tags({"market": "forex"})
    .filter_by_date("2024-01-01", "2024-12-31")
    .sort_by("profit_factor", descending=True)
    .limit(10)
    .execute())

for campaign in results.campaigns:
    print(f"{campaign.campaign_id}: Sharpe={campaign.metrics.sharpe}")

# Tag
store.tag("campaign-123", {"author": "alice", "version": "v3"})

# Link
store.link("campaign-parent", ["campaign-child-1", "campaign-child-2"])

# Get tags/links
tags = store.get_tags("campaign-123")
links = store.get_links("campaign-123")
```

## Index Schema (v2)

Each index entry:

```yaml
- campaign_id: "campaign-abc123"
  created: "2024-07-15T10:30:00Z"
  sharpe: 1.82
  profit_factor: 2.15
  win_rate: 58.3
  max_drawdown: 8.5
  total_trades: 150
  net_profit: 25000.0
  tags:
    strategy: "trend"
    market: "forex"
  links:
    - "campaign-parent-789"
  artifact_path: "knowledge/structured/campaign-abc123"
```

Missing metrics = `null`, empty tags/links = `{}` / `[]`.

## Performance

- In-memory index filtering: < 500ms for 10,000 campaigns
- Index rebuild: ~30s for 10,000 campaigns
- Index size: ~1KB per campaign (~10MB for 10k)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Query returns no results | Check index rebuilt after tag/link changes; verify metric values in `statistics.yaml` |
| Tags not appearing | Run `quantlab knowledge rebuild-index` |
| Date filter not working | Use ISO8601: `2024-01-01` or `2024-01-01T00:00:00Z` |
| Text search misses | Searches campaign_id, tag keys/values, statistics summary |
```

---

## Acceptance Criteria

| Document | Verification |
|----------|--------------|
| `README.md` updated with 3 new sections | `grep -A 20 "## Pipeline Commands" README.md` shows content |
| `docs/pipeline-yaml.md` exists with complete schema | File exists, has all 11 stage types, example YAML |
| `docs/reporting.md` exists with all features | File exists, covers themes, benchmark, templates, matplotlib, JSON schema |
| `docs/knowledge-query.md` exists with syntax | File exists, has all filter options, range syntax, tag/link commands |
| All CLI examples are accurate | Run each example, verify output matches docs |
| Cross-links between docs work | `README.md` links to `docs/*.md` resolve |

---

## Non-Functional Requirements

- **Format**: Markdown (GitHub-flavored)
- **Style**: Consistent with existing docs (headers, code blocks, tables)
- **Examples**: All CLI commands tested and working
- **Versioning**: Docs versioned with code (in repo)
- **No new dependencies**: Pure Markdown