# Dashboard API Specification

## Purpose

Defines the HTTP API layer that exposes Phase 1 CLI bridge data as JSON, consumed by the dashboard UI and external clients.

## Requirements

### Requirement: Flask app serves API on configurable port

The system MUST start a Flask application that serves API endpoints on a configurable port (default 8080). The app MUST bind to 127.0.0.1 only.

#### Scenario: App starts on default port
- GIVEN `quantlab dashboard start` is invoked
- WHEN the Flask app initializes
- THEN it listens on `127.0.0.1:8080`
- AND `GET /api/health` returns 200

#### Scenario: Custom port is respected
- GIVEN `--port 9090` is passed to `quantlab dashboard start`
- WHEN the Flask app initializes
- THEN it listens on `127.0.0.1:9090`

### Requirement: GET /api/campaigns returns campaign list with metrics

The system MUST return a JSON array of campaigns at `GET /api/campaigns`, each containing `campaign_id`, `market`, `timeframe`, `sharpe`, `profit_factor`, `win_rate`, `status`, and `total_return`.

#### Scenario: Campaigns endpoint returns list
- GIVEN campaigns exist in the Knowledge Lake
- WHEN `GET /api/campaigns` is called
- THEN response is a JSON array
- AND each entry contains campaign_id, market, timeframe, sharpe, profit_factor, win_rate, status, total_return
- AND HTTP status is 200

#### Scenario: No campaigns returns empty array
- GIVEN no campaigns exist
- WHEN `GET /api/campaigns` is called
- THEN response is an empty JSON array `[]`
- AND HTTP status is 200

### Requirement: GET /api/campaigns/{id} returns full campaign detail

The system MUST return a campaign's full detail at `GET /api/campaigns/{id}`, including equity curve data, trade list, statistics, and phase results.

#### Scenario: Campaign detail with equity and trades
- GIVEN campaign `campaign-123` exists with trades and equity data
- WHEN `GET /api/campaigns/campaign-123` is called
- THEN response contains `equity_curve`, `trades`, `statistics` (Sharpe, PF, MDD, win_rate), and `phases`
- AND HTTP status is 200

#### Scenario: Campaign not found returns 404
- GIVEN no campaign with id `nonexistent` exists
- WHEN `GET /api/campaigns/nonexistent` is called
- THEN HTTP status is 404

### Requirement: GET /api/pipeline returns pipeline run list and detail

The system MUST return pipeline runs at `GET /api/pipeline` (list) and `GET /api/pipeline/{run_id}` (detail with stages).

#### Scenario: Pipeline list returns runs
- GIVEN pipeline runs exist in Knowledge Lake
- WHEN `GET /api/pipeline` is called
- THEN response is a JSON array with run_id, pipeline_name, status, started_at, duration, stage_count

#### Scenario: Pipeline detail shows stages
- GIVEN pipeline run `pipe-run-abc` exists with 3 stages
- WHEN `GET /api/pipeline/pipe-run-abc` is called
- THEN response contains `stages` array with name, status, duration, error (if any)

### Requirement: GET /api/stats returns cross-campaign statistics

The system MUST return aggregated statistics at `GET /api/stats`, including Sharpe distribution, drawdown stats, win rate, and benchmark comparison data.

#### Scenario: Stats endpoint returns aggregated data
- GIVEN multiple campaigns exist
- WHEN `GET /api/stats` is called
- THEN response contains `sharpe_mean`, `sharpe_std`, `max_drawdown_pct`, `win_rate_mean`, `total_trades`, and `benchmark_comparison` (alpha, beta, correlation)
- AND HTTP status is 200

### Requirement: POST /api/reports/generate triggers report generation

The system MUST accept a report generation request at `POST /api/reports/generate` with `campaign_id` in the body, and return a `ReportResult` as JSON.

#### Scenario: Report generation triggered
- GIVEN campaign `campaign-123` exists
- WHEN `POST /api/reports/generate` is called with `{"campaign_id": "campaign-123"}`
- THEN the report generator runs
- AND response contains `campaign_id`, `html_path`, `json_path`, `charts_generated`, `generation_time_ms`
- AND HTTP status is 200

### Requirement: GET /api/health returns server health

The system MUST return a health check at `GET /api/health` with `status: "ok"` and uptime.

### Requirement: API errors return consistent envelope

The system MUST return errors in a consistent JSON envelope: `{"success": false, "error": {"code": "...", "message": "..."}}`.
