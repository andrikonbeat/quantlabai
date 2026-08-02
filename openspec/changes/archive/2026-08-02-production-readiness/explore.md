# Exploration: Production Readiness

**Change**: `production-readiness`
**Date**: 2026-07-31
**Status**: Ready for proposal

## 1. CLI Entrypoint

### Current state

- `sdk/quantlab/cli/main.py` (1163 lines) — `build_parser()` at L846, `main()` at L1138, `cli_entry()` at L1157 (already shaped for `[project.scripts]`), `if __name__ == "__main__"` at L1162.
- 12 top-level subcommands: `daemon`, `portfolio`, `optimizer`, `retester`, `jforex`, `report`, `knowledge`, `agent`, `campaign`, `dashboard`, `monitor`, `pipeline`. **No `api`, no `stats`.**
- **No** `sdk/quantlab/cli/__main__.py` and **no** `sdk/quantlab/__main__.py` (verified).
- `python -m quantlab.cli` → `No module named quantlab.cli.__main__` (verified). `python -m quantlab.cli.main --help` works (verified).
- The **only** API server in the codebase is `sdk/quantlab/dashboard/app.py` (Flask `create_app()` + `DashboardServer`). No FastAPI anywhere.
- Dockerfile L122 and L157 both run `CMD ["python", "-m", "quantlab.cli", "api"]` — broken twice (no `__main__`, no `api` command).

### Options

1. **Add `__main__.py` + `api` subcommand + `[project.scripts]` + `[build-system]`** — create `cli/__main__.py` calling `main()`; add an `api` subparser in `main.py` that boots the dashboard server (`DashboardServer(ServerConfig(host=0.0.0.0))`); add `quantlab = quantlab.cli.main:cli_entry` to `[project.scripts]` and `[build-system]` (`setuptools`/`hatchling`) to pyproject. Fixes root cause for both Dockerfile targets and gives a real installable console command.
   - Pros: correct end state; one fix covers `python -m quantlab.cli api` and `quantlab api`; unblocks PyPI publish job.
   - Cons: touches packaging (risk: new build-system breaks the current hand-rolled editable install); needs `api` command defined (reuse dashboard start logic).
   - Effort: Medium.

2. **Change Dockerfile CMD to something that works today** — `CMD ["python", "-m", "quantlab.cli.main", "dashboard", "start", "--host", "0.0.0.0"]`.
   - Pros: zero code; works immediately.
   - Cons: leaves `python -m quantlab.cli` broken for users; no console script; `api` still absent; masks the packaging debt.
   - Effort: Low.

### Recommendation

Option 1 (proper entrypoint), but as a two-step: ship `cli/__main__.py` + `api` subcommand + `[project.scripts]` first, and fix the Dockerfile `CMD` to `["quantlab", "api"]`. Option 2 is the acceptable minimal fallback if packaging changes are deferred. Dockerfile also needs separate fixes (see §6): L101 `COPY sdk/pyproject.toml sdk/poetry.lock* ./` (no lockfile exists), L102 `poetry install` (no `[tool.poetry]` table), L111 `pip install -e .` (no `setup.py`/`[build-system]` → build fails), L105 `COPY sdk/quantlab ./quantlab` + no `PYTHONPATH` in `base`/`runtime` targets.

## 2. Dependencies Gap

### Current state

- `sdk/pyproject.toml` `[project].dependencies` (14): pydantic, pyyaml, platformdirs, openpyxl, pandas, numpy, httpx, mcp, yfinance, pandas-datareader, openai, beautifulsoup4, feedparser, duckduckgo-search. Extras: `dev` (pytest, pytest-cov), `reporting` (plotly), `dashboard` (flask).
- **Missing from `sdk/.venv` (verified via `pip list` + import check) — exactly 4: `mcp`, `openai`, `feedparser`, `duckduckgo-search`.** Root `.venv` has openai 2.50.0 but also lacks mcp/feedparser/duckduckgo-search.
- ⚠️ Audit correction: beautifulsoup4 (4.15.0), yfinance (1.5.2), pandas-datareader (0.11.1) **are** installed in `sdk/.venv`. They were not the cause of the news-test failures (see §3).
- **No lockfile anywhere**: no `poetry.lock`, no `uv.lock` (verified).
- Workflow mismatch (3-way): README says `uv sync` from `sdk/`; CI (`.github/workflows/ci.yml`) and Dockerfile use **poetry** (`poetry install --with dev`); poetry is **not even installed** locally; pyproject has **no `[tool.poetry]` table** → `poetry install` would fail/misbehave. Reality today = hand-built venv via pip.
- `plotly 6.9.0` + `narwhals 2.24.0` in the venv were installed by a typo'd command `pip install plotly=5.18` (output captured in the stray `=5.18` file — see §8), not via extras/lockfile.

### Recommendation

Decide one workflow and make CI/Docker/README agree. Minimal path: add `[build-system]`, keep `[project.scripts]`, and drive CI with `pip install -e "sdk[dev]"` (or `uv sync` if uv is preferred). Add a lockfile (`uv lock`) for reproducibility. Install the 4 missing packages so the declared surface matches reality. `mcp` matters because `sdk/quantlab/mcp/bridge.py:21` imports `mcp.server.fastmcp` at module level (currently only broken when that module loads).

## 3. Test Architecture

### Current state

- **Two trees**: root `tests/` (largely untracked work: `agents/`, `dashboard/`, `sqx/`, `guardian/` with **correct** `from quantlab...` imports) and `sdk/tests/` (**CI canonical**).
- CI `test` job: `cd sdk && poetry run pytest tests/ -q --tb=short --maxfail=5 -x`. Root `tests/` is **never run by CI** — including the failing `test_llm_agent_news.py`.
- Root `pytest.ini` (6 lines): only `filterwarnings` + `asyncio_mode = auto`. **No `testpaths`/`norecursedirs`** → bare `pytest` from root crawls everything including `assets/` (j64/, bundled tests/, numpy blobs) → crashes. `sdk/pyproject.toml` `[tool.pytest.ini_options]` has `testpaths = ["tests"]` (correct relative to sdk/).
- **`tests/agents/test_llm_agent_news.py` (root, 19 tests, 17 fail) — root cause is NOT missing deps.** It is RED TDD code committed in `634fec2` ("test(research): LLM agent web/RSS news integration tests"): tests assert `LLMResearchAgent` has `_web_search`/`_rss_news`/`_get_web_search()`/`_get_rss_news()` and news-in-prompt — attributes/methods **never implemented** (verified by running the file: `AttributeError` on every test). `duckduckgo_search`/`feedparser` imports in `sdk/quantlab/data/news/{web_search,rss}.py` are `try/except ImportError` guarded (graceful `None`). Missing deps are real but cause failures elsewhere (e.g. `mcp.bridge` import), not these 17.
- **`sdk/tests/test_pr3_statistics_agent.py::test_run_missing_export_paths_raises` (L427)** — expects `ValueError("No export_paths")`, but `sdk/quantlab/agents/statistics_agent.py` L496-499 **returns empty statistics + warning** instead → stale test vs. changed implementation.
- **Guardian**: `sdk/tests/test_guardian/` (8 files, CI tree) import `from sdk.quantlab.guardian...` → **all 8 fail collection** (`ModuleNotFoundError: No module named 'sdk'`, verified). Root `tests/guardian/` (3 files) uses correct `from quantlab.guardian...`. `sdk/tests/conftest.py` inserts `sdk/` into `sys.path` — the canonical pattern.

### Recommendation

- Guardian: fix the `sdk.tests.test_guardian` imports to `from quantlab.guardian...` (or fold in the fixed root copies; note root only has 3 of the 8 files).
- News tests: delete the RED suite or implement the provider methods (decision for proposal — they target an unimplemented feature; **do not** attribute to deps).
- Stats test: fix the test to assert the new degrade-gracefully behavior (or restore raising — decide in proposal).
- Root `pytest.ini`: add `testpaths = tests` + `norecursedirs` (or `--ignore` for `assets`, `sdk/.venv`) so bare `pytest` works; add `sdk/` to sys.path in a root `conftest.py`.
- CI: consider whether root `tests/` should be a second CI job (it currently covers news/refutation/dashboard/sqx — untracked feature work).

## 4. Mock vs Real

### Current state

- `SQX_FORCE_MOCK` read in **2 places**: `sdk/quantlab/sqx/cli_wrapper.py:132-135` (`use_mock = force_mock or os.environ.get("SQX_FORCE_MOCK","").lower() in ("1","true","yes")`) and `sdk/quantlab/agents/builder_agent.py:604-606`.
- **Silent fallback**: `cli_wrapper.py:154-174` — when `sqcli_path` is falsy (no SQX found) the code writes the CFX to a temp file and dispatches to `_dispatch_mock` with **no warning to the user**. Mock also triggers silently whenever `SQX_FORCE_MOCK=1`.
- `MockSQXServer` (`sqx/mock_sqx_server.py:331`) is a threaded HTTP server on `127.0.0.1:5050` mimicking sqcli `/call?cmd=...`.
- `MockExecutor` (runner.py:72-93) is the dry-run variant used by tests.

### Options

1. **Loud warning at decision point** — after computing `use_mock` in `cli_wrapper.py` (~L135), emit a prominent `logger.warning`/stderr line: `MOCK MODE — no real SQX dispatch (SQX_FORCE_MOCK set or sqcli not found); results are simulated`. Same in `builder_agent.py:606`. Optionally surface a `mock_mode: bool` flag on `DispatchResult`.
2. **Hard fail in production** — in `QUANTLAB_ENV=production` (Dockerfile `runtime` target sets it, L152), raise/exit when mock would be used without explicit `SQX_FORCE_MOCK`.

### Recommendation

Option 1 everywhere the fallback happens (cli_wrapper + builder_agent), plus Option 2 gated on `QUANTLAB_ENV=production`. Minimal, low-risk, high-clarity change. Tests asserting the current silent behavior will need `caplog`-level updates.

## 5. License

### Current state

- `sdk/quantlab/pipeline/license.py` (92 lines): `LicenseStatus` enum, `LicenseInfo` dataclass, `LicenseManager.check()` runs `sqcli -license action=info` via an injected `Executor` then `_parse_info()` (L64-79) does **case-insensitive substring heuristics** on `licensed`/`trial`/`expired`; `activate(code)` runs `-license action=update code=<code>`.
- **Not integrated anywhere** — only re-exported at `pipeline/__init__.py:54`. Zero callers (verified via grep).
- Parser docstring explicitly says "replace it when the exact sqcli output format is known" — the real sqcli output format is unverified.

### Realistic minimal integration

- Hook `LicenseManager.check()` into `dispatch_campaign()` (`cli_wrapper.py`) **only on the real path** (when `use_mock` is False), as a pre-flight next to `builder_agent._ensure_data` (L595-597) or at `cmd_pipeline_run`/`cmd_campaign_run` start.
- Behavior: if status is not `LICENSED` → log warning with `detail`; **block only** when `QUANTLAB_ENV=production`. Mock path skips the check entirely.
- Optional offline override: `SQX_LICENSE` env (value passed through) for CI/dev; keep heuristics but always log raw sqcli output for diagnosis.
- Effort: Low-Medium. Real validation against actual sqcli output format is a separate, higher-effort item (needs an SQX install to capture real `-license action=info` text).

## 6. Docker / CI

### Current state

**`docker-compose.yml` (167 lines)** — verified defects:
- L10 `context: ..` and L47 `context: ../assets/...` — wrong; compose lives at repo root, so contexts resolve outside the repo.
- L44 + L49 duplicate `container_name` in `sqx-daemon`; L66-67 + L80-87 **duplicate `deploy:` blocks** for the same service (two resources limits).
- L47 `dockerfile: ./Dockerfile.sqx` — **no Dockerfile.sqx exists anywhere** (root, docker/, assets/ checked).
- L100 `./nginx.conf` → file is at **`docker/nginx.conf`** (exists). L101 `./certs` → **no certs/ dir anywhere**. L125 `./init-schema.sql` → file is at **`docker/init-schema.sql`**. L63 `./data/sqx` → **no data/ dir**.
- postgres/redis/nginx are aspirational ("future" per comments) — the stack is untestable as written.

**`Dockerfile`** — L101 `COPY sdk/pyproject.toml sdk/poetry.lock* ./` (no lockfile → copies nothing), L102 `poetry install --only=main` (no `[tool.poetry]` → fails), L105 `COPY sdk/quantlab ./quantlab` (no PYTHONPATH in base/runtime), L111 `pip install -e .` (no setup.py/build-system → fails), L122/L157 broken CMD (see §1).

**CI `.github/workflows/ci.yml`** (262 lines, 5 jobs):
- `lint`/`test`/`integration`: `poetry install --with dev` — `--with` needs a poetry group; pyproject uses PEP 621 extras → fails; `mypy quantlab --strict` likely fails on the codebase.
- `docs`: `poetry install --with docs` — **no `docs` extra/group exists** (only dev/reporting/dashboard) → fails; then `mkdocs build` — **no mkdocs.yml** anywhere.
- `test`: `pytest tests/` runs **without `--cov`** but `codecov` upload expects `sdk/coverage.xml` → never generated.
- `publish`: `poetry build` — no `[build-system]` → fails.
- `docker`: builds root-context `Dockerfile` → fails per above.

### Minimal fixes

- Compose: point nginx/postgres volumes at `./docker/nginx.conf` + `./docker/init-schema.sql`, drop nginx/certs (or add a `certs/` dir + generate self-signed), drop `data/sqx` mount (or mkdir + gitkeep), set `context: .`, dedupe `container_name`/`deploy`, delete the `Dockerfile.sqx` build block until a real SQX image exists.
- CI: replace poetry with `pip install -e "sdk[dev]"` (or uv); add `--cov --cov-report=xml:coverage.xml` to the pytest run (note `testpaths=["tests"]` relative to sdk/ is correct); fix or delete the `docs` job (add `docs` extra + mkdocs.yml, or remove); add `[build-system]` to enable `poetry build`/PyPI, or drop the publish job.
- Effort: Medium for compose+CI; Dockerfile is part of the same fix as §1.

## 7. Dashboard

### Current state

`sdk/quantlab/dashboard/` is substantial, coherent WIP — **salvageable**:
- `app.py` (285 lines): Flask factory `create_app()` + `DashboardServer` (threaded, start/stop/wait).
- **8 API routes**: `GET /api/health` (works, hardcoded), `GET /api/campaigns`, `GET /api/campaigns/<id>`, `GET /api/pipeline`, `GET /api/pipeline/<id>`, `GET /api/stats` (all shell out via `CliRunner` to the **real sqcli** binary with ad-hoc commands `campaign list --json`, `campaign show`, `pipeline show`, `stats summary` — no contract, unverifiable without SQX), `POST /api/reports/generate` (calls `ReportGenerator.generate(...)` with **empty `trades=[]`, `equity=[]`, `statistics={}`** → produces an empty report, L187-196), plus 4 HTML routes.
- `app.py:62` **hardcodes** `sqcli_path = "/home/ogzuz/Proyectos/QuantLab AI/assets/SQX_144_2953_linux_20260601/sqcli"` — the binary exists on this machine but the path is machine-specific; compose already passes `QUANTLAB_SQX_PATH` (compose L20) which the app ignores.
- Templates (4: base, campaign_list, campaign_detail, pipeline_monitor, stats_dashboard) + `static/` (16 CSS + 14 JS files incl. CampaignList.js 9.7K, PipelineMonitor.js 12.2K, StatsDashboard.js 21.5K). Separate `components/ pages/ stores/` source dirs mirror static/ — vanilla JS, **no package.json, no build step** (served as-is).
- `cli/dashboard_commands.py`: `dashboard start` works (blocks on Ctrl+C), `dashboard stop`/`status` are **stubs** ("not yet implemented", L123-135).

### Scoping options

1. **Define a minimal API surface backed by real code paths**: replace sqcli ad-hoc shells with (a) Knowledge Lake queries (campaigns/status), (b) `report generate` CLI/`ReportGenerator` fed from real `export_paths` (fix empty-data bug), (c) read sqcli path from `QUANTLAB_SQX_PATH`/env with a sane default; implement stop/status via PID file.
2. **Ship as-is with a "WIP" marker** and fix only the hardcoded path + empty-report bug.

### Recommendation

Option 1 (minimal surface, ~6 endpoints) — the assets/templates are worth keeping; the API layer is the only broken part. Fix path resolution first (env-driven). Tests: `sdk/tests/dashboard/` (22 files, mostly static-asset tests) + root `tests/dashboard/` (7 files incl. `test_api.py`) exist but are untracked.

## 8. Junk Files

| Path | Content (verified) | Git state | Verdict |
|---|---|---|---|
| `=3.0` (1.0K) | pip PEP 668 `externally-managed-environment` error (from typo'd `pip install flask=3.0`) | **Untracked**; already in `.gitignore` "# Stray junk" | Junk — delete |
| `=5.18` (721B) | pip output "Successfully installed narwhals-2.24.0 plotly-6.9.0" (typo'd `pip install plotly=5.18`) | **Tracked** | Junk — `git rm =5.18` |
| `Save location: /` (dir) | `Save location: /tmp/tmp.yXHLELKR0d/sdk/quantlab/...` — pip-download output captured as a path; contains tracked copies of `pipeline/*.py`, `phase4/stages/__init__.py` etc. | **Tracked directory** (`git ls-files` shows entries) | Junk — `git rm -r "Save location: /"` |

Also root `_run_campaign.py` is gitignored as stray junk; `notifications.jsonl` is gitignored.

**Repo-size note**: `assets/SQX_144_2953_linux_20260601.zip` (1224.5M) is **tracked**, plus the expanded `assets/SQX_.../` dir (≈4.4G working tree); `.git` is **7.4G** (audit said 2.42 GiB — it has grown). Removing the zip from tracking (move to a release artifact / LFS / `.dockerignore` already ignores `*.zip` for builds) is the biggest hygiene win.

## Cross-cutting

- `STATE.md` is stale (2026-07-23: "Rama main (limpia)", 630 tests) — update or delete as part of this change.
- Openspec convention is active (`openspec/config.yaml`, `schema: spec-driven`); untracked specs exist for dashboard-api, dashboard-ui, refutation-layer, quantlab-installer, config-wizard, autonomous-monitor — the proposal should reconcile with them.
- Untracked feature work (29 entries): `installer/` (go.sum + 10.6M binary, **no go.mod, no .go source** — unbuildable skeleton), `sdd/`, `openspec/`, `sdk/quantlab/agents/refutation/`, `sdk/quantlab/dashboard/`, `sdk/quantlab/cli/dashboard_commands.py`, duplicated test files (e.g. `test_refutation_layer.py` 35.8K in both trees). Proposal must decide: commit, finish, or delete each.

## Ready for Proposal

Yes — with these corrected facts vs. the audit:
1. News-test failures are **unimplemented feature (RED TDD)**, not missing deps. Missing deps = exactly `mcp`, `openai`, `feedparser`, `duckduckgo-search` (bs4/yfinance/datareader ARE installed).
2. `sdk/tests/test_guardian/` fails **collection** (8 errors, `sdk.quantlab` import path), not assertion failures.
3. `=5.18` and `Save location: /` are **tracked junk** requiring `git rm`; `=3.0` is untracked/ignored.
4. Docker/CI fixes are a coherent package with §1 (entrypoint + build-system + Dockerfile) — propose as one change or two chained slices.
