# Dashboard API Specification

## Purpose

Defines the HTTP API layer that exposes Phase 1 CLI bridge data as JSON, consumed by the dashboard UI and external clients.

## Requirements

### Requirement: Flask app serves API on configurable port

The system MUST start a Flask app on a configurable port (default 8080). The `api` subcommand SHALL bind 0.0.0.0; `dashboard start` SHALL bind 127.0.0.1. (Previously: always bound 127.0.0.1 only)

#### Scenario: App starts on default port
- GIVEN `quantlab dashboard start`
- WHEN the Flask app initializes
- THEN it listens on 127.0.0.1:8080 and `GET /api/health` returns 200

#### Scenario: Custom port is respected
- GIVEN `--port 9090`
- WHEN the Flask app initializes
- THEN it listens on the requested port

#### Scenario: api subcommand binds externally
- GIVEN `quantlab api`
- WHEN the server starts
- THEN it binds 0.0.0.0:8080

**Acceptance**: boot verified via health check.

### Requirement: GET /api/campaigns returns campaign list with metrics

The system MUST return campaigns at `GET /api/campaigns` from REAL code paths (Knowledge Lake queries), not ad-hoc sqcli shell-outs. Each entry SHALL carry campaign_id, market, timeframe, sharpe, profit_factor, win_rate, status, total_return. (Previously: shelled out to sqcli with unverifiable ad-hoc commands)

#### Scenario: Campaigns endpoint returns list
- GIVEN campaigns exist in the Knowledge Lake
- WHEN `GET /api/campaigns` is called
- THEN a JSON array with the required fields is returned, HTTP 200

#### Scenario: No campaigns returns empty array
- GIVEN no campaigns exist
- WHEN `GET /api/campaigns` is called
- THEN `[]` is returned, HTTP 200

**Acceptance**: endpoint backed by real query code.

### Requirement: GET /api/campaigns/{id} returns full campaign detail

The system MUST return campaign detail with equity curve, trade list, statistics, and phase results from real data; missing campaigns SHALL return 404. (Previously: ad-hoc sqcli shell-out)

#### Scenario: Campaign detail with equity and trades
- GIVEN campaign `campaign-123` with data
- WHEN `GET /api/campaigns/campaign-123` is called
- THEN response has equity_curve, trades, statistics, phases, HTTP 200

#### Scenario: Campaign not found returns 404
- GIVEN no such campaign
- WHEN `GET /api/campaigns/nonexistent` is called
- THEN HTTP 404 with the error envelope

**Acceptance**: detail sourced from real stored data.

### Requirement: GET /api/pipeline returns pipeline run list and detail

The system MUST return pipeline runs from real code: list at `GET /api/pipeline` (run_id, pipeline_name, status, started_at, duration, stage_count) and detail at `GET /api/pipeline/{run_id}` (stages with name/status/duration/error), 404 when missing. (Previously: ad-hoc sqcli shell-out)

#### Scenario: Pipeline list returns runs
- GIVEN pipeline runs exist
- WHEN `GET /api/pipeline` is called
- THEN a JSON array with the run fields is returned, HTTP 200

#### Scenario: Pipeline detail shows stages
- GIVEN run `pipe-run-abc` with 3 stages
- WHEN `GET /api/pipeline/pipe-run-abc` is called
- THEN the stages array is returned, HTTP 200

#### Scenario: Unknown run 404s
- GIVEN no such run
- WHEN `GET /api/pipeline/unknown` is called
- THEN HTTP 404 with the error envelope

**Acceptance**: pipeline endpoints backed by real code.

### Requirement: GET /api/stats returns cross-campaign statistics

The system MUST return aggregated statistics (sharpe_mean, sharpe_std, max_drawdown_pct, win_rate_mean, total_trades, benchmark_comparison) computed from real stored campaigns, empty-safe. (Previously: ad-hoc sqcli shell-out)

#### Scenario: Stats endpoint returns aggregated data
- GIVEN multiple campaigns exist
- WHEN `GET /api/stats` is called
- THEN the aggregated fields are returned, HTTP 200

#### Scenario: Stats empty-safe
- GIVEN no campaigns
- WHEN `GET /api/stats` is called
- THEN zeros/empty aggregates are returned, HTTP 200, no crash

**Acceptance**: stats computed from real data.

### Requirement: POST /api/reports/generate triggers report generation

The system MUST generate reports from REAL export_paths data; the empty-data bug (trades=[], equity=[], statistics={} at app.py:188-193) MUST be fixed. (Previously: produced empty reports)

#### Scenario: Report generation with real data
- GIVEN campaign `campaign-123` with data
- WHEN `POST /api/reports/generate` with `{"campaign_id": "campaign-123"}` is called
- THEN the report contains real trades/equity/statistics, and the response has campaign_id, html_path, json_path, charts_generated, generation_time_ms, HTTP 200

#### Scenario: Missing campaign errors
- GIVEN no such campaign
- WHEN the endpoint is called
- THEN HTTP 404 with the error envelope

**Acceptance**: generated report is non-empty for a real campaign.

### Requirement: GET /api/health returns server health

The system MUST return a health check at `GET /api/health` with `status: "ok"` and uptime.

### Requirement: API errors return consistent envelope

The system MUST return errors in a consistent JSON envelope: `{"success": false, "error": {"code": "...", "message": "..."}}`.

### Requirement: DSH-01 Env-driven sqcli path

The system MUST resolve the sqcli path by precedence: config → `SQX_INSTALL_PATH` env → documented default. The hardcoded machine-specific path in `app.py:62` MUST NOT remain.

#### Scenario: Env path used
- GIVEN `SQX_INSTALL_PATH` set
- WHEN endpoints dispatch sqcli
- THEN that binary is used

#### Scenario: Missing binary is reported, not crashed
- GIVEN no sqcli resolvable
- WHEN an endpoint needs it
- THEN a clear "sqcli unavailable" error is returned

**Acceptance**: no machine-specific path in app.py.

### Requirement: DSH-02 PID-based stop/status

`dashboard stop` MUST terminate the running server via PID file; `dashboard status` MUST report running (PID, uptime) or stopped.

#### Scenario: Stop terminates server
- GIVEN a running server with a PID file
- WHEN `quantlab dashboard stop` runs
- THEN the process is terminated and the PID file is removed

#### Scenario: Status when stopped
- GIVEN no PID file
- WHEN `quantlab dashboard status` runs
- THEN it reports "not running"

**Acceptance**: stubs at dashboard_commands.py:127,134 implemented.
