# Tasks: Phase 2 — Dashboard UI

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 1200–1800 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation + API → PR 2: Templates + Static → PR 3: CLI + Integration Tests |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Foundation: package, Flask app skeleton, CLI command skeleton, dependency | PR 1 | `pytest tests/dashboard/test_foundation.py -v` | `quantlab dashboard start --port 8081` (smoke) | `sdk/quantlab/dashboard/`, `cli/main.py`, `pyproject.toml` |
| 2 | Core API: endpoints, CliRunner delegation, ReportResult.to_json() | PR 1 | `pytest tests/dashboard/test_api.py -v` | `curl localhost:8081/api/health` | `app.py`, `reporting/models.py` |
| 3 | Templates: 4 HTML templates (base, campaign_list, campaign_detail, pipeline_monitor, stats_dashboard) | PR 2 | `pytest tests/dashboard/test_templates.py -v` | `curl localhost:8081/` renders HTML | `templates/` |
| 4 | Static: dashboard.js (Plotly, fetch, SPA), dashboard.css | PR 2 | `pytest tests/dashboard/test_static.py -v` | Browser loads charts from `/static/` | `static/` |
| 5 | Integration: CLI start/stop, E2E health, report trigger, pipeline monitor | PR 3 | `pytest tests/dashboard/test_integration.py -v` | Full `quantlab dashboard start` + API calls | All dashboard files |

---

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Create `sdk/quantlab/dashboard/__init__.py` exporting `DashboardServer` class and `create_app()` factory
- [x] 1.2 Create `sdk/quantlab/dashboard/app.py` with Flask app factory, `DashboardServer` class (start/stop lifecycle, binds 127.0.0.1), and health endpoint `GET /api/health`
- [x] 1.3 Add `flask` dependency to `sdk/pyproject.toml` (core + optional dev deps)
- [x] 1.4 Create `sdk/quantlab/cli/dashboard_commands.py` with `dashboard_start` and `dashboard_stop` command functions (argument parsing: `--port`, `--host`, `--debug`)
- [x] 1.5 Modify `sdk/quantlab/cli/main.py` to import and register `dashboard` subcommand group
- [x] 1.6 Add unit test `tests/dashboard/test_foundation.py`: test `DashboardServer` start/stop, port binding, health endpoint returns 200

## Phase 2: Core API Implementation

- [x] 2.1 Implement `GET /api/campaigns` in `app.py`: delegate to `CliRunner.execute(["campaign", "list", "--json"])`; return campaign summary array
- [x] 2.2 Implement `GET /api/campaigns/<id>` in `app.py`: delegate to `CliRunner.execute(["campaign", "show", id, "--json"])`; return equity_curve, trades, statistics, phases
- [x] 2.3 Implement `GET /api/pipeline` in `app.py`: delegate to `CliRunner.execute(["pipeline", "list", "--json"])`; return run summary array
- [x] 2.4 Implement `GET /api/pipeline/<run_id>` in `app.py`: delegate to `CliRunner.execute(["pipeline", "show", run_id, "--json"])`; return stage details
- [x] 2.5 Implement `GET /api/stats` in `app.py`: delegate to `CliRunner.execute(["stats", "summary", "--json"])`; return cross-campaign metrics
- [x] 2.6 Implement `POST /api/reports/generate` in `app.py`: parse JSON body, delegate to `ReportGenerator.generate()`; return `ReportResult.to_json()`
- [x] 2.7 Modify `sdk/quantlab/reporting/models.py`: add `to_json()` method to `ReportResult` (serialize Path→str, datetime→ISO8601, include formats/theme)
- [x] 2.8 Add error envelope: all endpoints catch exceptions and return `{"success": false, "error": {"code": "...", "message": "..."}}`
- [x] 2.9 Add unit test `tests/dashboard/test_api.py`: mock `CliRunner` and `ReportGenerator`; verify JSON response shapes for all 6 endpoints

## Phase 3: Frontend Templates

- [x] 3.1 Create `sdk/quantlab/dashboard/templates/base.html`: Jinja2 base with `<head>` (Plotly CDN, CSS link), nav bar, `{% block content %}`, footer
- [x] 3.2 Create `sdk/quantlab/dashboard/templates/campaign_list.html`: extends base; sidebar with campaign list, status badges, search/filter input; summary table (ID, Market, Timeframe, Sharpe, Profit Factor, Win Rate, Status, Total Return); "New Report" button
- [x] 3.3 Create `sdk/quantlab/dashboard/templates/campaign_detail.html`: extends base; equity curve Plotly div, metrics cards (Sharpe, Max DD, Win Rate, Total Return); tabs for Trades (table), Stages (list), Reports (list with download links)
- [x] 3.4 Create `sdk/quantlab/dashboard/templates/pipeline_monitor.html`: extends base; horizontal step indicator for stages (pending/running/success/error), duration per stage, "View Log" links; bottom log panel with pre-formatted output
- [x] 3.5 Create `sdk/quantlab/dashboard/templates/stats_dashboard.html`: extends base; cross-campaign charts (Sharpe distribution, drawdown, win rate); benchmark overlay toggle; filters by market/timeframe/date range
- [x] 3.6 Add Flask routes in `app.py` to render each template at `/`, `/campaigns`, `/campaigns/<id>`, `/pipeline`, `/stats`
- [x] 3.7 Add unit test `tests/dashboard/test_templates.py`: test client requests each route; assert 200 and Plotly divs present in HTML

## Phase 4: Frontend Static Assets

- [x] 4.1 Create `sdk/quantlab/dashboard/static/dashboard.css`: layout (grid/flex), badge styles, table styles, chart container sizing, tab styling, log panel monospace
- [x] 4.2 Create `sdk/quantlab/dashboard/static/dashboard.js`: SPA navigation (fetch HTML fragments), `fetchCampaigns()`, `fetchCampaignDetail(id)`, `fetchPipeline()`, `fetchStats()`, `renderEquityCurve(data)`, `renderTradesTable(data)`, `renderMetricsCards(data)`, `renderPipelineStages(data)`, `renderStatsCharts(data)`, `triggerReport(campaign_id)`
- [x] 4.3 Add Plotly chart configs in JS: equity curve (line), trade scatter (P&L vs time), Sharpe distribution (histogram), benchmark comparison (multi-line)
- [x] 4.4 Add polling-based refresh (5s interval) for pipeline monitor and campaign list
- [x] 4.5 Add unit test `tests/dashboard/test_static.py`: verify static files served; JS syntax check (node --check or eslint if available)

## Phase 5: Integration & E2E Testing

- [x] 5.1 Integration test `tests/dashboard/test_integration.py`: start `DashboardServer` on random port; `GET /api/health` → 200; `GET /api/campaigns` → valid JSON array
- [x] 5.2 Integration test: `POST /api/reports/generate` with valid campaign_id; mock `ReportGenerator`; verify response matches `ReportResult.to_json()` schema
- [x] 5.3 Integration test: pipeline monitor endpoints return stage progress with status/duration/error fields
- [x] 5.4 E2E test: subprocess `quantlab dashboard start --port 8081`; wait for ready; `curl /api/health`; `curl /api/campaigns`; `quantlab dashboard stop`; assert clean shutdown
- [x] 5.5 Threat-matrix RED tests (run first, expect failure):
  - [x] 5.5.1 Shell command injection via campaign_id param → expect 400/500 structured error
  - [x] 5.5.2 Subprocess timeout (sqcli hangs) → expect 500 with timeout error code
  - [x] 5.5.3 Port 8080 already in use → `DashboardServer.start()` raises/catches OSError, returns clear error
- [x] 5.6 GREEN tests: implement fixes for 5.5.1–5.5.3 (input validation, timeout config, port retry/fallback)
- [x] 5.7 REFACTOR test: verify error handling unified across all endpoints

## Phase 6: Cleanup / Documentation

- [x] 6.1 Update `sdk/quantlab/dashboard/__init__.py` with version and public API exports
- [x] 6.2 Add docstrings to all public functions/classes in `app.py`, `dashboard_commands.py`, `models.py`
- [x] 6.3 Verify `quantlab dashboard --help` shows correct usage
- [x] 6.4 Run full test suite: `pytest tests/dashboard/ -v` and `pytest tests/ -k dashboard -v`
- [x] 6.5 Manual smoke test: `quantlab dashboard start`, open browser at `http://localhost:8080`, navigate all pages, trigger report generation

---

## Implementation Order Rationale

1. **Phase 1** establishes the Flask package, server lifecycle, and CLI entry point — everything else depends on this.
2. **Phase 2** builds the API layer that the frontend consumes — templates and static assets need working endpoints.
3. **Phase 3** creates the HTML structure — JS in Phase 4 targets specific DOM elements from these templates.
4. **Phase 4** adds interactivity and charts — depends on template DOM structure and API contracts.
5. **Phase 5** validates end-to-end flow and threat-matrix cases — requires all prior phases complete.
6. **Phase 6** polishes and verifies — final quality gate.

## Next Step

Await user decision on chain strategy (feature-branch-chain confirmed above). Then proceed to `sdd-apply` for PR 1 (Phase 1 + Phase 2 tasks).