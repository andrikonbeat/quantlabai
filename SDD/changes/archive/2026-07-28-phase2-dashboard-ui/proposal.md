# Proposal: Phase 2 — Dashboard UI

## Intent

Deliver a browser-based dashboard visualizing campaign data, pipeline results, monitoring metrics, and statistics through the Phase 1 CLI bridge API.

## Scope

### In Scope
- Flask+HTML web UI served by quantlab CLI as a local API (MVP)
- Campaign list/detail views with equity curves, trade tables, key metrics
- Pipeline run monitoring (stage progress, logs)
- Statistics dashboard (Sharpe, drawdown, win rate, benchmark comparison)
- Report generation trigger from UI (reuses `ReportGenerator`)
- CLI bridge API endpoints (`/api/campaigns`, `/api/pipeline`, `/api/stats`, `/api/reports`)

### Out of Scope
- Tauri desktop packaging (Phase 3)
- Real-time streaming (polling-based refresh)
- Multi-user auth or tenant isolation
- Strategy editor or CFX authoring in UI
- Mobile-responsive design (desktop-first)

## Capabilities

### New Capabilities
- `dashboard-ui`: Web UI served by quantlab CLI, consuming CLI bridge API endpoints
- `dashboard-api`: HTTP API layer exposing Phase 1 CLI bridge data as JSON

### Modified Capabilities
- `cli-bridge`: Extended with Flask HTTP routes serving structured JSON
- `reporting`: `ReportResult` gains `to_json()` for API consumption

## Approach

Flask serves the HTML frontend and API from the quantlab CLI process. The CLI bridge becomes the API layer — dashboard calls `/api/*` endpoints delegating to existing `sqcli` and SDK pipeline commands. Plotly charts render client-side from JSON. Tauri wrapper deferred to Phase 3.

## User-facing Changes

**Before**: Terminal-only — run `quantlab report generate` or `quantlab pipeline run`, then open static HTML files. **After**: Browser at `http://localhost:8080` — campaign list, equity curves, trade tables, live pipeline monitoring, report triggers — all in-browser.

## Technical Design

### New Files
| File | Purpose |
|------|---------|
| `sdk/quantlab/dashboard/app.py` | Flask app: routes, API endpoints, HTML serving |
| `sdk/quantlab/dashboard/templates/` | Jinja2 HTML templates |
| `sdk/quantlab/dashboard/static/` | JS (Plotly), CSS |
| `sdk/quantlab/cli/dashboard_commands.py` | `quantlab dashboard` CLI subcommand |

### Modified Files
| File | Change |
|------|--------|
| `sdk/quantlab/cli/main.py` | Register `dashboard` subcommand |
| `sdk/quantlab/reporting/generator.py` | Add `to_json()` on `ReportResult` |

### Patterns
- API endpoints return `CliResult`/`ReportResult` as JSON; templates reuse `reporting/templates.py`; Plotly renders client-side from JSON.

## Dependencies
- Phase 1 CLI bridge complete (the API layer); `sqcli` binary at `assets/SQX_144_2953_linux_20260601/sqcli` or `SQCLI_PATH`; Flask added as dependency (`pip install flask`).

## Rollback Plan
1. `quantlab dashboard stop`
2. Remove `sdk/quantlab/dashboard/` directory
3. Revert `sdk/quantlab/cli/main.py` to remove dashboard subcommand
4. No existing CLI commands or SDK modules modified — rollback is non-destructive

## Success Criteria
- [ ] `quantlab dashboard start` launches Flask on port 8080
- [ ] `GET /api/campaigns` returns campaigns with status and key metrics
- [ ] `GET /api/campaigns/{id}` returns full campaign detail (equity, trades, stats)
- [ ] Dashboard renders equity curves, trade scatter, metrics tables from API data
- [ ] `quantlab dashboard stop` gracefully shuts down

## UI Mockup Description

**Campaign List**: Sidebar with campaign list, status badges, search/filter, "New Report" button. Summary table (Campaign ID, Market, Timeframe, Sharpe, Profit Factor, Status). **Campaign Detail**: Equity curve and metrics cards (Sharpe, Max DD, Win Rate, Total Return). Tabs: Trades, Stages, Reports. **Pipeline Monitor**: Horizontal step indicator for stages, duration, "View Log" links, bottom log panel. **Statistics Dashboard**: Cross-campaign charts, benchmark overlay toggle, filters by market/timeframe/date.

## Proposal question round

1. **MVP scope**: Flask+HTML only, or include Tauri scaffolding now? Tradeoff: Flask ships faster; Tauri avoids a second UI rewrite.
