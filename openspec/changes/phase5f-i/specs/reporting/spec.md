# Delta Spec: Reporting (Modified Capability)

## Change Summary

Extends existing `reporting` capability (see `openspec/specs/reporting/spec.md`) with dark theme, benchmark overlay, matplotlib fallback, custom templates, and expanded report sections.

This delta modifies the existing `ReportConfig`, `ReportGenerator`, and CLI. The new capability `reporting-completo` (full spec at `openspec/specs/reporting-completo/spec.md`) provides complete implementation details. This delta documents what CHANGES in the existing spec.

---

## ADDED Requirements

### Requirement: Dark Theme Support (FR-001)

**ADDED to `ReportConfig`**: `theme` field already exists (enum: `light`, `dark`). Implementation now:
- Applies CSS custom properties for all colors
- Switches Plotly template to `plotly_dark` when `theme == "dark"`
- Renders `<html class="theme-dark">` for CSS variable scoping

**ADDED to `ReportGenerator.generate_html()`**:
- Theme-aware CSS variable injection
- Plotly template selection based on config

#### Scenario: Dark theme renders with CSS variables
- GIVEN `ReportConfig(theme=ReportTheme.dark)`
- WHEN `generate_html()` executes
- THEN output HTML contains CSS variables for dark palette
- AND Plotly charts use `plotly_dark` template

---

### Requirement: Benchmark Equity Overlay (FR-002)

**EXISTING**: `ReportConfig.benchmark_equity: list[EquityPoint] | None` (already in spec)

**ADDED implementation in `ReportGenerator.generate_html()`**:
- Adds second trace to equity curve chart when `benchmark_equity` provided
- Uses `config.chart_config.colors.benchmark` color (default `#9467bd`)
- Shows legend with "Strategy" and "Benchmark" labels
- Aligns timestamps (interpolates if needed)

**ADDED to JSON output**: `benchmark_equity` array included when provided

#### Scenario: Benchmark overlay on equity chart
- GIVEN `config.benchmark_equity` with 100 points
- WHEN equity curve chart renders
- THEN chart has 2 traces (strategy + benchmark)
- AND legend shows both labels

---

### Requirement: Matplotlib Static Fallback (FR-003)

**ADDED to `ReportGenerator`**:
- Module-level `PLOTLY_AVAILABLE` flag (try/except import)
- Module-level `MATPLOTLIB_AVAILABLE` flag (try/except import)
- `_try_plotly()` method
- `_try_matplotlib()` method
- `_render_chart_matplotlib(chart_type, data)` → returns base64 PNG data URI

**ADDED optional dependency**: `quantlab[reporting-matplotlib]` extra in `pyproject.toml` with `matplotlib>=3.7`

**BEHAVIOR CHANGE**: When Plotly not installed:
- If matplotlib available (via extra): generates static PNG charts embedded as base64
- If neither: warning banner in HTML, `charts_generated = []`, warning in `ReportResult.warnings`

#### Scenario: Matplotlib fallback generates static charts
- GIVEN `pip install quantlab[reporting-matplotlib]` (no plotly)
- WHEN `generate_html()` with `include_charts=True`
- THEN HTML contains `<img src="data:image/png;base64,...">` for each chart
- AND `ReportResult.warnings` contains matplotlib fallback notice

---

### Requirement: Custom Jinja2 Template Support (FR-004)

**ADDED to `ReportConfig`**: `template_path: Path | None = None`

**ADDED to `ReportGenerator.generate_html()`**:
- If `template_path` provided and exists: load as Jinja2 template
- If not provided or missing: fall back to embedded default template
- Warning added to `ReportResult.warnings` if fallback used

**ADDED CLI option**: `--template <path>`

#### Scenario: Custom template loaded and rendered
- GIVEN `ReportConfig(template_path=Path("custom.j2"))` with valid template
- WHEN `generate_html()` executes
- THEN output rendered from custom template
- AND all required template variables available

---

### Requirement: Expanded Report Sections (FR-005, FR-006, FR-007)

**ADDED sections to HTML template context**:

1. **Executive Summary** (`executive_summary` dict):
   - `net_profit`, `sharpe`, `max_drawdown`, `win_rate`, `profit_factor`
   - `assessment`: "Strong risk-adjusted returns..." / "Moderate..." / "Weak..."
   - `indicator`: `"green"` | `"amber"` | `"red"` (based on Sharpe thresholds)

2. **Phase Timing Table** (`phase_timing` list):
   - From `CampaignResult.phases`: `[{phase, status, duration_ms, start, end}, ...]`
   - Rendered as HTML table: Phase | Status | Duration | Start | End

3. **Benchmark Comparison Table** (`benchmark_comparison` list, when benchmark provided):
   - Metrics: Total Return, Annualized Return, Volatility, Sharpe, Max DD, Correlation
   - Columns: Strategy | Benchmark

---

## MODIFIED Requirements

### Requirement: Report Configuration Model (MODIFIED)

**PREVIOUS** (from existing spec):
```python
class ReportConfig(BaseModel):
    campaign_id: str
    output_dir: Path = Path("reports")
    formats: list[ReportFormat] = Field(default_factory=lambda: [ReportFormat.html, ReportFormat.json])
    include_charts: bool = True
    theme: ReportTheme = ReportTheme.light
    title: str | None = None
    benchmark_equity: list[EquityPoint] | None = None
    chart_config: ChartConfig = Field(default_factory=ChartConfig)
```

**UPDATED** (adds `template_path`):
```python
class ReportConfig(BaseModel):
    campaign_id: str
    output_dir: Path = Path("reports")
    formats: list[ReportFormat] = Field(default_factory=lambda: [ReportFormat.html, ReportFormat.json])
    include_charts: bool = True
    theme: ReportTheme = ReportTheme.light
    title: str | None = None
    benchmark_equity: list[EquityPoint] | None = None
    chart_config: ChartConfig = Field(default_factory=ChartConfig)
    template_path: Path | None = None          # NEW
```
(Previously: no `template_path` field)

---

### Requirement: HTML Report Generator (MODIFIED)

**PREVIOUS**: Generated HTML with 4 charts + metrics table using Plotly only.

**UPDATED**: 
- Dark theme via CSS variables + Plotly `plotly_dark`
- Benchmark overlay on equity curve when `benchmark_equity` provided
- Matplotlib fallback when Plotly unavailable
- Custom template support via `template_path`
- Executive summary, phase timing, benchmark comparison sections
- All charts rendered via `_render_chart()` which dispatches to Plotly or matplotlib

---

### Requirement: CLI Report Generation Command (MODIFIED)

**PREVIOUS** options:
```
--html / --no-html
--json / --no-json
--output-dir PATH
--theme light|dark
--no-charts
--benchmark FILE
```

**UPDATED** (adds `--template`):
```
--html / --no-html
--json / --no-json
--output-dir PATH
--theme light|dark
--no-charts
--benchmark FILE
--template PATH          # NEW: custom Jinja2 template
```

---

### Requirement: Optional Plotly Dependency (MODIFIED)

**PREVIOUS**: Plotly optional extra `[reporting]`. If missing: HTML with banner, no charts.

**UPDATED**: Two optional extras:
- `[reporting]` — Plotly (interactive charts)
- `[reporting-matplotlib]` — Matplotlib (static PNG fallback)

Behavior matrix:
| Install | Plotly | Matplotlib | HTML Charts |
|---------|--------|------------|-------------|
| `quantlab` | ❌ | ❌ | Banner only |
| `quantlab[reporting]` | ✅ | ❌ | Interactive Plotly |
| `quantlab[reporting-matplotlib]` | ❌ | ✅ | Static PNG (base64) |
| Both | ✅ | ✅ | Interactive Plotly (preferred) |

---

## REMOVED Requirements

None. All existing requirements preserved with backward-compatible additions.

---

## RENAMED Requirements

None.

---

## Interface Changes Summary

| Interface | Change |
|-----------|--------|
| `ReportConfig` | Added `template_path: Path \| None` |
| `ReportGenerator.generate_html()` | Theme-aware, benchmark overlay, matplotlib dispatch, custom template |
| `ReportGenerator.generate_json()` | Includes `benchmark_equity` in output when provided |
| `ReportGenerator` | Added `_try_plotly()`, `_try_matplotlib()`, `_render_chart_matplotlib()` |
| `report_generate_command` | Added `--template` argument |
| `pyproject.toml` | Added `[project.optional-dependencies] reporting-matplotlib = ["matplotlib>=3.7"]` |

---

## Acceptance Criteria (Delta)

| Criterion | Verification |
|-----------|--------------|
| Dark theme uses CSS variables + `plotly_dark` | Generate with `--theme dark`, inspect HTML for CSS vars and Plotly template |
| Benchmark overlay adds 2nd trace | Unit test: pass benchmark, assert 2 traces in equity chart |
| Matplotlib fallback works | Install `[reporting-matplotlib]` w/o plotly, generate HTML, assert base64 PNG |
| Custom template loads | Provide valid `.j2`, assert output matches template |
| Missing template falls back | Provide bad path, assert default template used + warning |
| Executive summary rendered | Generate report, parse HTML for executive summary section |
| Phase timing table rendered | Generate report, parse HTML for phase timing table |
| Benchmark comparison table | Pass benchmark, assert comparison table in HTML |
| JSON includes benchmark_equity | Generate JSON with benchmark, assert field present |
| Two optional extras in pyproject.toml | `pip show quantlab` or inspect pyproject.toml |

---

## Migration Notes

- **Backward compatible**: All existing `ReportConfig` fields unchanged; new field optional
- **Default behavior unchanged**: `theme="light"`, no template, Plotly primary
- **Breaking change**: None
- **Deprecation**: None