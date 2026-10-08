# Delta Spec: campaign-orchestrator (Phase 5b-5e)

## MODIFIED Requirements

### Requirement: SQXReportStage Delegates to Reporting Module

The system MUST modify `SQXReportStage` in `sdk/quantlab/phase4/stages/__init__.py` to delegate report generation to the new `quantlab.reporting.generator.ReportGenerator` (Feature 5b), replacing the current placeholder implementation.

**Current behavior (placeholder):**
```python
class SQXReportStage(CampaignStage):
    async def execute(self, context: CampaignContext) -> CampaignContext:
        # Placeholder - returns {"report_path": None}
        context.artifacts["report_path"] = None
        return context
```

**New behavior:**
```python
class SQXReportStage(CampaignStage):
    def __init__(
        self,
        report_config: ReportConfig | None = None,
        output_dir: Path | None = None,
        generate_html: bool = True,
        generate_json: bool = True,
        theme: str = "light"
    ):
        self.report_config = report_config or ReportConfig()
        self.output_dir = output_dir
        self.generate_html = generate_html
        self.generate_json = generate_json
        self.theme = theme

    async def execute(self, context: CampaignContext) -> CampaignContext:
        campaign_result = context.campaign_result
        if not campaign_result:
            raise CampaignError("No CampaignResult available for report generation")

        # Build ReportConfig from stage params + campaign data
        config = ReportConfig(
            output_dir=self.output_dir or context.config.report_output_dir,
            generate_html=self.generate_html,
            generate_json=self.generate_json,
            theme=self.theme,
            campaign_name=campaign_result.campaign_id,
            benchmark_equity_path=context.config.benchmark_equity_path
        )

        # Delegate to Reporting Module
        generator = ReportGenerator(config)
        report_result = generator.generate(campaign_result)

        # Store report paths in context
        context.artifacts["report_html"] = report_result.html_path
        context.artifacts["report_json"] = report_result.json_path
        context.artifacts["report_charts"] = report_result.charts_generated

        return context
```

**Key changes:**
1. **Removes placeholder** returning `{"report_path": None}`
2. **Accepts configuration** via constructor (report format, theme, output dir)
3. **Delegates to `ReportGenerator`** — new class from Feature 5b
4. **Stores multiple artifact paths** (html, json, charts list) instead of single `report_path`
5. **Handles missing CampaignResult** with clear error

#### Scenario: Campaign with SQXReportStage generates HTML and JSON reports
- GIVEN campaign completes with valid CampaignResult
- WHEN SQXReportStage executes
- THEN ReportGenerator called with campaign data
- AND context.artifacts contains `report_html`, `report_json`, `report_charts`

#### Scenario: SQXReportStage with HTML disabled
- GIVEN `SQXReportStage(generate_html=False, generate_json=True)`
- WHEN stage executes
- THEN only `report_json` in artifacts, `report_html` is None

#### Scenario: CampaignResult missing raises clear error
- GIVEN context without campaign_result
- WHEN SQXReportStage.execute() called
- THEN CampaignError raised with message "No CampaignResult available"

---

## Data Flow (Modified)

```
CampaignOrchestrator.run()
       │
       ├─► ... (translate, daemon, load, run, poll, export, read, compute stats)
       │
       └─► SQXReportStage.execute(context)
              │
              ├─► Extract CampaignResult from context.campaign_result
              ├─► Build ReportConfig from stage params + context.config
              ├─► ReportGenerator.generate(campaign_result, config)
              │       │
              │       ├─► Charts: equity curve, drawdown, trade scatter, stats table
              │       ├─► HTML: templates.py + Plotly → single HTML file
              │       └─► JSON: structured schema with metrics, trades, equity
              │
              └─► Update context.artifacts with report paths
```

---

## Interface Specifications (Delta)

```python
# quantlab.phase4.stages (MODIFIED)
class SQXReportStage(CampaignStage):
    def __init__(
        self,
        report_config: ReportConfig | None = None,  # from quantlab.reporting.models
        output_dir: Path | None = None,
        generate_html: bool = True,
        generate_json: bool = True,
        theme: str = "light"
    ): ...

    async def execute(self, context: CampaignContext) -> CampaignContext: ...

# quantlab.reporting.models (NEW - from Feature 5b, used here)
class ReportConfig(BaseModel):
    output_dir: Path = Path("reports")
    generate_html: bool = True
    generate_json: bool = True
    theme: Literal["light", "dark"] = "light"
    campaign_name: str = ""
    benchmark_equity_path: Path | None = None

class ReportResult(BaseModel):
    html_path: Path | None
    json_path: Path | None
    charts_generated: list[str]
    generation_time_ms: float

# quantlab.reporting.generator (NEW - from Feature 5b)
class ReportGenerator:
    def __init__(self, config: ReportConfig): ...
    def generate(self, campaign_result: CampaignResult) -> ReportResult: ...
```

---

## Acceptance Criteria (Delta)

| Criterion | Verification |
|-----------|--------------|
| SQXReportStage no longer returns `{"report_path": None}` | Code review: placeholder removed |
| Delegates to ReportGenerator from reporting module | Code review: `ReportGenerator` imported and used |
| HTML report generated when enabled | Integration: run campaign with stage, check `report_html` exists |
| JSON report generated when enabled | Integration: check `report_json` exists, valid schema |
| Both disabled stores None paths | Unit test: `generate_html=False, generate_json=False` → both None |
| Benchmark equity path passed through | Integration: provide benchmark, verify chart has benchmark trace |
| Theme parameter affects HTML output | Visual: generate with `theme="dark"`, verify CSS |
| CampaignError on missing CampaignResult | Unit test: mock context without result, assert error |
| Existing orchestrator tests pass | Run Phase 4 test suite |

---

## Migration Notes

- **Breaking change**: `context.artifacts["report_path"]` → use `report_html` / `report_json`
- **Update callers**: Any code reading `report_path` must be updated to check new keys
- **Configuration**: Stage now accepts `ReportConfig` or individual params
- **Dependencies**: Requires `quantlab.reporting` (Feature 5b) — must be installed/available
- **Optional plotly**: If `quantlab[reporting]` not installed, HTML generation falls back gracefully (Feature 5b handles this)

---

## Related Files Modified

| File | Change |
|------|--------|
| `sdk/quantlab/phase4/stages/__init__.py` | SQXReportStage rewritten to delegate |
| `sdk/quantlab/phase4/campaign_orchestrator.py` | May need updated stage instantiation with config |
| `tests/phase4/test_stages.py` | Update tests for new behavior |