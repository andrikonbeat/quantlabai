# Delta for Reporting

## MODIFIED Requirements

### Requirement: Report Result Model

The system MUST provide a `ReportResult` Pydantic model with fields:
- `campaign_id: str`
- `html_path: Path | None` — path to generated HTML report
- `json_path: Path | None` — path to generated JSON report
- `charts_generated: list[str]` — list of chart IDs included
- `generation_time_ms: float`
- `warnings: list[str]` — any warnings during generation
- `to_json() -> dict` — serializes the ReportResult to a JSON-serializable dict for API consumption

The `to_json()` method MUST return a dict with all fields, converting `Path` objects to strings and `datetime` objects to ISO8601 strings. This enables the dashboard API to return report results as JSON without additional serialization logic.

(Previously: ReportResult had no `to_json()` method; API consumers had to manually serialize Path and datetime fields.)

#### Scenario: to_json() returns serializable dict
- GIVEN a `ReportResult` with `html_path=Path("reports/c1.html")`, `json_path=Path("reports/c1.json")`, `charts_generated=["equity_curve", "trade_scatter"]`, `generation_time_ms=1200.5`
- WHEN `report_result.to_json()` is called
- THEN the result is a dict with string paths, list of chart IDs, and float generation time
- AND no Path or datetime objects remain in the output

#### Scenario: to_json() includes warnings
- GIVEN a `ReportResult` with `warnings=["Plotly not installed, charts omitted"]`
- WHEN `to_json()` is called
- THEN the warnings list is included in the output dict
- AND the dict is fully JSON-serializable

## ADDED Requirements

### Requirement: ReportResult includes report format and theme in to_json()

The `to_json()` method MUST include the report's `format` (html/json/both) and `theme` (light/dark) in its output so the dashboard UI can render appropriate previews.

#### Scenario: to_json() includes format and theme
- GIVEN a ReportConfig with `formats=["html", "json"]` and `theme="dark"`
- WHEN the report is generated and `to_json()` is called
- THEN the output dict includes `formats` and `theme` fields
- AND the UI can use these to render the correct preview
