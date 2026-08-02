# Delta Spec: Production Readiness

**Change**: production-readiness · **Date**: 2026-07-31 · **Status**: Ready for design
**Scope**: All RESOLVED proposal decisions Q1–Q5 (SQX zip removal, news implementation, minimal real dashboard API, env-based license guard, untracked triage).

## 1. cli-entrypoint (NEW capability — full spec)

### Requirement: CLI-01 Console script `quantlab`

The system MUST expose an installed console command `quantlab` via `[project.scripts]` mapping to `quantlab.cli.main:cli_entry` (main.py:1157).

#### Scenario: Help exits zero
- GIVEN the package is installed
- WHEN `quantlab --help` runs
- THEN it prints usage and exits 0

#### Scenario: No args exits non-zero
- GIVEN no subcommand
- WHEN `quantlab` runs bare
- THEN usage prints to stderr and exit code is non-zero

**Acceptance**: `quantlab --help` exits 0 in a fresh uv venv.

### Requirement: CLI-02 Module entry `python -m quantlab.cli`

The system MUST ship `sdk/quantlab/cli/__main__.py` invoking `main()` so module invocation matches the console script.

#### Scenario: Module invocation works
- GIVEN repo checkout without install
- WHEN `python -m quantlab.cli --help` runs
- THEN usage prints and exit code is 0

**Acceptance**: module invocation works from repo root and from `sdk/`.

### Requirement: CLI-03 `api` subcommand

The system MUST add an `api` subcommand that boots the dashboard server (`DashboardServer`) on host 0.0.0.0, port configurable (default 8080), and blocks until interrupted.

#### Scenario: API server boots
- GIVEN `quantlab api` invoked
- WHEN the server starts
- THEN `GET /api/health` returns 200 on 0.0.0.0:8080

#### Scenario: Clean shutdown
- GIVEN the server running
- WHEN Ctrl+C is sent
- THEN the server shuts down cleanly with exit 0

**Acceptance**: `quantlab api` boots (proposal success criterion).

### Requirement: CLI-04 Packaging + lockfile

`sdk/pyproject.toml` MUST declare `[build-system]`; the project SHOULD ship a `uv.lock`; a fresh `uv sync` in a clean venv MUST install the package with the console script.

#### Scenario: Fresh uv sync works
- GIVEN a clean venv
- WHEN `uv sync` runs from `sdk/`
- THEN `quantlab` is on PATH and imports resolve

#### Scenario: pip editable install still works
- GIVEN `[build-system]` added
- WHEN `pip install -e "sdk[dev]"` runs
- THEN install succeeds (no regression on hand-built venv)

**Acceptance**: fresh uv sync + console script works (proposal success criterion).

## 2. packaging-deps (NEW)

### Requirement: DEP-01 Declared deps match reality

The 4 missing runtime deps `mcp`, `openai`, `feedparser`, `duckduckgo-search` MUST be installed in the venv(s) and declared in `[project].dependencies`.

#### Scenario: Imports resolve
- GIVEN the installed venv
- WHEN `import mcp, openai, feedparser, duckduckgo_search` runs
- THEN all four import without error

#### Scenario: mcp bridge loads
- GIVEN `mcp` installed
- WHEN `sdk/quantlab/mcp/bridge.py` is imported
- THEN no module-level ImportError occurs

**Acceptance**: no module-level ImportError in quantlab packages.

## 3. test-suite (NEW — canonical tree definition)

### Requirement: TST-01 Canonical tree and green suite

The ROOT tree is canonical: bare `pytest` from repo root MUST collect both `tests/` and `sdk/tests/` and pass ~1315 tests with 0 failures once news, guardian, and stats fixes land.

#### Scenario: Bare pytest green
- GIVEN news implemented, guardian imports fixed, stats test updated
- WHEN `pytest` runs from repo root
- THEN ~1315 tests pass, 0 fail, 0 collection errors

#### Scenario: CI runs the same command
- GIVEN CI test job
- WHEN it runs the root pytest command after `pip install -e "sdk[dev]"`
- THEN the full suite (incl. root `tests/`) is exercised

**Acceptance**: ~1315 pass / 0 fail (proposal success criterion).

### Requirement: TST-02 pytest.ini testpaths/norecursedirs

Root `pytest.ini` MUST set `testpaths` and `norecursedirs` so bare pytest never crawls `assets/`, venvs, or build dirs.

#### Scenario: No asset crawl
- GIVEN `assets/` contains numpy blobs and bundled tests
- WHEN bare `pytest` runs
- THEN collection avoids `assets/` and completes without crash

**Acceptance**: bare pytest reaches only test trees.

### Requirement: TST-03 Guardian imports fixed

`sdk/tests/test_guardian/*` MUST import `from quantlab.guardian...` (drop the `sdk.` prefix) so all 8 files collect.

#### Scenario: Guardian suite collects
- GIVEN corrected imports
- WHEN `pytest sdk/tests/test_guardian -q` runs
- THEN 0 collection errors; tests execute

**Acceptance**: 8 collection errors eliminated.

### Requirement: TST-04 Stats degrade semantics

`test_pr3_statistics_agent.py::test_run_missing_export_paths_raises` MUST assert the graceful-degrade behavior (empty statistics + warning) instead of `ValueError`.

#### Scenario: Missing export paths degrades
- GIVEN a statistics agent run without export_paths
- WHEN the test invokes it
- THEN empty statistics are returned, a warning is logged, and no exception is raised

**Acceptance**: stale expectation replaced.

## 4. ci-docker (NEW)

### Requirement: CID-01 CI install + coverage

CI MUST install via `pip install -e "sdk[dev]"` (poetry removed everywhere) and run pytest with `--cov --cov-report=xml:coverage.xml` so `sdk/coverage.xml` exists for the codecov upload.

#### Scenario: Coverage artifact produced
- GIVEN the CI test job
- WHEN pytest runs with the cov flags
- THEN `sdk/coverage.xml` is generated and uploaded

**Acceptance**: CI green + coverage.xml generated (proposal success criterion).

### Requirement: CID-02 CI docs job

The docs job MUST either use a real mkdocs setup (`mkdocs.yml` + a `docs` extra) or be removed; it MUST NOT reference the nonexistent `--with docs` extra.

#### Scenario: Docs build succeeds or job removed
- GIVEN ci.yml docs job
- WHEN it runs
- THEN `mkdocs build` succeeds, or the job is deleted from the workflow

**Acceptance**: no failing phantom job in ci.yml.

### Requirement: CID-03 Dockerfile CMD + install path

The Dockerfile MUST install via `[build-system]` (not poetry), set PYTHONPATH where needed, and set both broken CMDs (L122, L157) to a working entrypoint (`quantlab api`).

#### Scenario: Image builds and serves
- GIVEN the fixed Dockerfile
- WHEN `docker build` then the container starts
- THEN `quantlab api` runs and `GET /api/health` returns 200

**Acceptance**: docker build valid (proposal success criterion).

### Requirement: CID-04 Compose defects fixed

`docker-compose.yml` MUST fix all 9 defects: correct build contexts (L10, L47), dedupe `container_name` (L44/49) and `deploy` blocks (L66/80), point nginx/init-schema at `docker/`, drop or create `certs/` and `data/sqx`, and remove the nonexistent `Dockerfile.sqx` build block.

#### Scenario: Compose validates
- GIVEN the fixed compose file
- WHEN `docker compose config` runs
- THEN it validates without errors

**Acceptance**: compose config valid (proposal success criterion).

## 5. dashboard-api (delta)

### ADDED Requirements

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

### MODIFIED Requirements

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

> Unchanged, preserved from main spec: `GET /api/health` (status ok + uptime) and the consistent JSON error envelope.

## 6. sqx-cli-wrapper (delta: mock loudness)

### ADDED Requirements

### Requirement: MOK-01 Loud mock warning

Whenever mock dispatch is chosen — `SQX_FORCE_MOCK` set OR sqcli not found — the system MUST emit a prominent warning (logger/stderr) stating results are simulated, at every decision point (`cli_wrapper.py` and `builder_agent.py:604-606`). (Previously: silent fallback at cli_wrapper.py:132-160)

#### Scenario: Missing sqcli warns
- GIVEN sqcli not found and no SQX_FORCE_MOCK
- WHEN a command dispatches
- THEN mock dispatch occurs AND a MOCK MODE warning is emitted

#### Scenario: Forced mock warns
- GIVEN `SQX_FORCE_MOCK=1`
- WHEN a command dispatches
- THEN mock is used AND the warning is emitted

**Acceptance**: no silent mock dispatch (proposal success criterion).

### Requirement: MOK-02 Production hard-fail

When `QUANTLAB_ENV=production` and mock would be used WITHOUT explicit `SQX_FORCE_MOCK`, the system MUST abort (raise/exit) before dispatching.

#### Scenario: Production blocks silent mock
- GIVEN QUANTLAB_ENV=production, no sqcli, no SQX_FORCE_MOCK
- WHEN a command dispatches
- THEN an error is raised and no mock result is returned

#### Scenario: Production allows explicit mock
- GIVEN QUANTLAB_ENV=production and SQX_FORCE_MOCK=1
- WHEN a command dispatches
- THEN mock is used with the MOK-01 warning

**Acceptance**: production never silently mocks.

## 7. license-manager (delta: guard)

### MODIFIED Requirements

### Requirement: Startup Guard

The system MUST run `LicenseManager.check()` as a pre-flight on REAL dispatch (mock path skips it). Non-LICENSED status SHALL log a warning with detail; the run SHALL block (raise) only when `QUANTLAB_ENV=production`. (Previously: CampaignRunner raised LicenseError at startup for unlicensed/expired regardless of environment)

#### Scenario: Production unlicensed aborts
- GIVEN production env and unlicensed SQX
- WHEN a real dispatch starts
- THEN a LicenseError is raised and no sqcli commands beyond the license check run

#### Scenario: Production licensed proceeds
- GIVEN production env and a licensed SQX
- WHEN a real dispatch starts
- THEN the check passes and the run proceeds

#### Scenario: Dev unlicensed warns only
- GIVEN non-production env and unlicensed SQX
- WHEN a real dispatch starts
- THEN a warning with detail is logged and the run proceeds

#### Scenario: Mock path skips check
- GIVEN mock dispatch (SQX_FORCE_MOCK)
- WHEN a command dispatches
- THEN no license check runs

**Acceptance**: license guard active on real dispatch in production (proposal success criterion).

### ADDED Requirements

### Requirement: LIC-02 SQX_LICENSE override + raw logging

The system MUST accept the `SQX_LICENSE` env value as a passed-through license status override (CI/dev) and MUST always log the raw `sqcli -license action=info` output. No real-format parsing is required.

#### Scenario: Env override short-circuits
- GIVEN `SQX_LICENSE=licensed`
- WHEN check() runs
- THEN the override value is reported without invoking sqcli

#### Scenario: Raw output logged
- GIVEN a real license check
- WHEN check() executes sqcli
- THEN the raw output is logged for diagnosis

**Acceptance**: env override works; raw output visible in logs.

## 8. llm-research (delta: news feature)

### ADDED Requirements

### Requirement: NWS-01 Guarded provider singletons

`LLMResearchAgent` MUST expose `_get_web_search()` / `_get_rss_news()` returning lazily-initialized singleton providers, guarded by ImportError (missing duckduckgo-search/feedparser → None). Fresh instances SHALL have `_web_search` and `_rss_news` attributes set to None.

#### Scenario: Fresh instance attrs are None
- GIVEN a new LLMResearchAgent
- WHEN attributes are inspected
- THEN `_web_search is None` and `_rss_news is None`

#### Scenario: Providers are singletons
- GIVEN providers importable
- WHEN `_get_web_search()` / `_get_rss_news()` are called twice
- THEN each returns the same instance on repeat calls

#### Scenario: Missing provider degrades to None
- GIVEN the provider library is not installed
- WHEN the getter is called
- THEN it returns None without raising ImportError

**Acceptance**: 17 RED tests in tests/agents/test_llm_agent_news.py turn green.

### Requirement: NWS-02 fetch_data orchestration

`fetch_data()` MUST query web search and RSS (ticker-scoped; RSS skipped when no ticker), merge results into news items with expected keys, tolerate provider failures, and handle empty market context gracefully.

#### Scenario: Both providers contribute
- GIVEN mocked providers returning items
- WHEN fetch_data runs
- THEN news data contains items from both sources with expected keys

#### Scenario: Web search failure degrades
- GIVEN web search raises
- WHEN fetch_data runs
- THEN RSS still contributes and no exception propagates

#### Scenario: RSS failure degrades
- GIVEN RSS raises
- WHEN fetch_data runs
- THEN web results still contribute and no exception propagates

#### Scenario: No ticker skips RSS
- GIVEN no ticker in market context
- WHEN fetch_data runs
- THEN RSS is not invoked; web search still runs

#### Scenario: Empty context is graceful
- GIVEN an empty market context
- WHEN fetch_data runs
- THEN it completes without raising

#### Scenario: Query source precedence
- GIVEN context with a market
- WHEN fetch_data runs
- THEN the query uses context.market; with no market it falls back to the objective

**Acceptance**: fetch_data robust in all six cases.

### Requirement: NWS-03 News in prompt

`build_prompt` MUST include fetched articles as text with their URLs; articles without a URL SHALL show text without a URL line.

#### Scenario: Articles include URLs
- GIVEN articles with URLs
- WHEN build_prompt runs
- THEN the prompt contains article text and the URL

#### Scenario: Article without URL
- GIVEN an article missing a URL
- WHEN build_prompt runs
- THEN the prompt shows the text with no URL line

**Acceptance**: news-in-prompt behavior asserted by the tests.

### MODIFIED Requirements

### Requirement: Prompt Templates

The system MUST provide structured prompt templates by analysis type: technical, fundamental, macro, and news-based. Each template SHALL include relevant data context; the news-based template SHALL include fetched news articles. (Previously: templates existed but had no news-provider data source to include)

#### Scenario: Fundamental prompt includes financial data
- GIVEN a fundamental analysis objective with PE ratio, revenue, and debt data
- WHEN the fundamental template is selected
- THEN the prompt includes structured financial metrics

#### Scenario: Technical prompt excludes macro data
- GIVEN a technical analysis objective (price, volume, indicators)
- WHEN the technical template is selected
- THEN the prompt omits macroeconomic indicators

#### Scenario: News-based prompt includes articles
- GIVEN fetched news articles
- WHEN the news-based template is selected
- THEN the prompt includes the article text and URLs

**Acceptance**: news-based template consumes NWS-03 output.

## 9. hygiene (NEW)

### Requirement: HGN-01 Tracked junk removed

The system MUST `git rm` tracked junk: `=5.18`, the `Save location: /` directory, the installer skeleton (go.sum + compiled binary), and duplicated test files (e.g. root `test_refutation_layer.py`). Untracked `=3.0` MUST be deleted.

#### Scenario: Junk absent from tracking
- GIVEN the cleanup commits
- WHEN `git ls-files` is checked
- THEN none of the junk paths appear

**Acceptance**: junk gone (proposal success criterion).

### Requirement: HGN-02 SQX zip untracked

The SQX zip (`assets/SQX_144_2953_linux_20260601.zip`, 1224.5M) MUST be removed from tracking via `git rm --cached` and kept on an external volume; runtime resolution follows config → `SQX_INSTALL_PATH` → default. No LFS.

#### Scenario: Zip untracked but resolvable
- GIVEN the zip removed from tracking
- WHEN `git ls-files` is checked
- THEN the zip is absent; with SQX_INSTALL_PATH set the external copy resolves

#### Scenario: Missing zip errors clearly
- GIVEN no zip resolvable
- WHEN a component needs SQX
- THEN a clear error is returned, no crash

**Acceptance**: .git stops growing from the zip (proposal: SQX zip removal).

### Requirement: HGN-03 Untracked triage committed

Untracked specs (`sdd/`, `openspec/`) and refutation work MUST be committed in their own commits; deletions in their own commits.

#### Scenario: Triage commits land cleanly
- GIVEN the triage
- WHEN commits are made
- THEN each logical group (specs, refutation, deletions) is a separate commit

**Acceptance**: per-slice rollback preserved (proposal rollback plan).

### Requirement: HGN-04 STATE.md refreshed

`STATE.md` MUST reflect current reality (workflow, test counts) or be deleted; stale claims (e.g. poetry, 630 tests) MUST NOT remain.

#### Scenario: STATE.md matches repo
- GIVEN the updated document
- WHEN it is read
- THEN workflow and test counts match the repo

**Acceptance**: no stale documentation.

## Non-Goals (explicit)

- **Installer implementation** — skeleton deleted, not finished.
- **Refutation completion** — existing code committed as-is; no new features.
- **Poetry migration** — workflow unified on uv/pip; poetry removed from CI/Docker/README.
- **SQX zip history rewrite** — removed from tracking only; history retained in `.git`.
- **Real license validation** — no real `-license action=info` format parsing.
- **Config-wizard / autonomous-monitor** — out of scope.
- **LFS adoption** — explicitly rejected for the SQX zip.

## Success Criteria (mapped to proposal)

- [ ] `quantlab api` boots server (CLI-03)
- [ ] Fresh uv sync; console script works (CLI-01/04, DEP-01)
- [ ] CI green; coverage.xml generated (CID-01/02)
- [ ] Bare pytest ~1315 pass / 0 fail (TST-01)
- [ ] compose config + docker build valid (CID-03/04)
- [ ] Mock warns; production hard-fails (MOK-01/02)
- [ ] License active on real dispatch (LIC guard)
- [ ] Junk gone; SQX zip untracked (HGN-01/02)
