# Design: Phase 2 — Dashboard UI

## Technical Approach

Flask serves the HTML frontend and API from the quantlab CLI process. The existing CLI bridge (`CliRunner`/`RealExecutor` from Phase 1) becomes the API layer — dashboard endpoints delegate to existing `sqcli` and SDK pipeline interfaces without duplicating command construction. Plotly charts render client-side from JSON. `DashboardServer` class encapsulates server lifecycle, allowing clean replacement by Tauri webview in Phase 3.

## Architecture Decisions

| # | Decision | Tradeoff | Rationale |
|---|----------|----------|-----------|
| 1 | Flask app at `sdk/quantlab/dashboard/app.py` | vs extending `cli/main.py` | Matches existing module pattern; isolates HTTP lifecycle |
| 2 | API delegates via `CliRunner` | vs duplicating sqcli invocation | Reuses `RealExecutor`/`MockExecutor` and `CliResult` from Phase 1 |
| 3 | `ReportResult.to_json()` for serialization | vs custom serializer per endpoint | Single path; `Path`→string, `datetime`→ISO8601; follows Pydantic pattern |
| 4 | Plotly CDN + client-side rendering | vs server-side chart generation | Eliminates server rendering burden; reuses same chart JSON format as `reporting/generator.py` |
| 5 | Bind `127.0.0.1`, no auth for MVP | vs 0.0.0.0 or auth layer | Local-only per spec |
| 6 | `DashboardServer` class wrapping Flask | vs bare Flask app | Encapsulates start/stop; clean replacement by Tauri webview in Phase 3 |

## Data Flow

```
Browser ──HTTP──→ Flask route ──delegate──→ CliRunner.execute() ──subprocess──→ sqcli / SDK pipeline
                                                                                             │
                                                                                             ↓
Browser ←──JSON──── Flask route ←──serialize──┬── PipelineRunner / ReportGenerator ──┘
                                                   │
Browser ←──HTML+JS← Jinja2 template ←──Campaign/pipeline data from Knowledge Lake
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/dashboard/__init__.py` | Create | Package init; exports `DashboardServer` |
| `sdk/quantlab/dashboard/app.py` | Create | Flask app: routes, API endpoints, HTML serving |
| `sdk/quantlab/dashboard/templates/base.html` | Create | Base template with Nav, Plotly CDN, shared CSS |
| `sdk/quantlab/dashboard/templates/campaign_list.html` | Create | Sidebar + summary table with search/filter |
| `sdk/quantlab/dashboard/templates/campaign_detail.html` | Create | Equity curve, metrics cards, Trades/Stages/Reports tabs |
| `sdk/quantlab/dashboard/templates/pipeline_monitor.html` | Create | Horizontal step indicator + log panel |
| `sdk/quantlab/dashboard/templates/stats_dashboard.html` | Create | Cross-campaign charts with benchmark overlay toggle |
| `sdk/quantlab/dashboard/static/dashboard.js` | Create | Plotly rendering, fetch calls, SPA navigation, report trigger |
| `sdk/quantlab/dashboard/static/dashboard.css` | Create | Layout, badges, charts |
| `sdk/quantlab/cli/dashboard_commands.py` | Create | `quantlab dashboard start/stop` subcommand |
| `sdk/quantlab/cli/main.py` | Modify | Register `dashboard` subcommand |
| `sdk/quantlab/reporting/models.py` | Modify | Add `to_json()` to `ReportResult` |
| `sdk/pyproject.toml` | Modify | Add `flask` dependency |

## API Endpoints

```
GET  /api/health                         → {"status": "ok", "uptime_seconds": float}
GET  /api/campaigns                       → [{campaign_id, market, timeframe, sharpe, profit_factor, win_rate, status, total_return}]
GET  /api/campaigns/<id>                 → {equity_curve: [...], trades: [...], statistics: {...}, phases: [...]}
GET  /api/pipeline                        → [{run_id, pipeline_name, status, started_at, duration, stage_count}]
GET  /api/pipeline/<run_id>              → {stages: [{name, status, duration, error}]}
GET  /api/stats                           → {sharpe_mean, sharpe_std, max_drawdown_pct, win_rate_mean, total_trades, benchmark_comparison}
POST /api/reports/generate               → {campaign_id, html_path, json_path, charts_generated: [...], generation_time_ms}
```
Errors return `{"success": false, "error": {"code": "...", "message": "..."}}`.

## CLI Bridge Extension

`quantlab dashboard start` launches Flask via `DashboardServer` on `127.0.0.1:8080` (configurable via `--port`). `quantlab dashboard stop` calls `DashboardServer.stop()`, which gracefully shuts down the Werkzeug server. The `dashboard_commands.py` module follows the same pattern as `daemon_commands.py` and `pipeline_commands.py`.

## Reporting Extension

`to_json()` on `ReportResult` serializes all fields to JSON-safe types (`Path` → string, includes `formats` and `theme`). Called by `POST /api/reports/generate` instead of manual field-by-field serialization.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | API response shapes | Mock CliRunner and KnowledgeStore; verify JSON schema |
| Integration | GET /api/campaigns with real data | Test client; load fixture from knowledge/stats/ |
| Integration | POST /api/reports/generate | Mock ReportGenerator.generate(); verify to_json() output |
| E2E | dashboard start launches server | Subprocess: start, curl /api/health, assert 200 |
| E2E | Template rendering | Request via test client; assert Plotly divs present |

## Threat Matrix

| Boundary | Applicability | Design response |
|---|---|---|
| Shell commands (CLI bridge) | Applicable | CliRunner handles path resolution and 300s timeout; errors return structured JSON envelope |
| Subprocess execution | Applicable | RealExecutor maps non-zero exit to 500; CliResult captures stdout/stderr |
| HTTP server process | Applicable | Flask binds 127.0.0.1 only; DashboardServer catches OSError on bind |
| Git/VCS, PR automation | N/A — no VCS/PR automation in Phase 2 | No tasks or tests required |
| Executable-file classification | N/A — no file classification boundary | No tasks or tests required |

## Migration / Rollback

No migration required. All changes are additive or backward-compatible. Rollback: stop server, remove `sdk/quantlab/dashboard/`, revert registration and dependency changes.

## Open Questions

- [ ] Port conflict strategy if 8080 is occupied — auto-increment or fail?
- [ ] Pagination needed for large campaign equity data responses?
