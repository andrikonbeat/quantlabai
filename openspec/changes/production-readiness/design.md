# Design: Production Readiness

## Technical Approach

Slice 1 (Foundation): installable + testable — `[build-system]`, `[project.scripts]`, `cli/__main__.py`, `api` subcommand reusing Flask `DashboardServer`, uv lockfile, root-canonical pytest, guardian/stats fixes, Docker/CI/compose repair, junk + zip removal. Slice 2 (Behavior): loud mock, production hard-fail, license guard, env-driven dashboard API on Knowledge Lake, PID stop/status, news providers. Reuse `cli_entry`, `DashboardServer`, `KnowledgeStore`, `LicenseManager`, guarded news providers.

## Architecture Decisions

| # | Chosen | Alternatives | Rationale |
|---|---|---|---|
| D1 CLI | `[project.scripts] quantlab = quantlab.cli.main:cli_entry` + `cli/__main__.py` → `main()` | Dockerfile-only CMD fix | One fix covers `quantlab`, `python -m quantlab.cli`, both CMDs (CLI-01/02) |
| D2 `api` | Subparser → `DashboardServer(ServerConfig(host="0.0.0.0", port=args.port))`, blocks till Ctrl+C | New FastAPI; wrap `dashboard start` | Only server in codebase; zero new server code (CLI-03) |
| D3 Build | setuptools, flat-layout discovery | hatchling; poetry | Lowest risk vs `pip install -e`; PEP 621 present |
| D4 Deps | Declared (L17/20/22/23); `uv sync`/`pip install -e "sdk[dev]"`; `uv lock` | pip-tools | README says uv; mcp bridge resolves |
| D5 Tests | Root canonical: `testpaths = tests sdk/tests`; `norecursedirs = assets sdk/.venv .venv venv .git build dist __pycache__ *.egg-info`; root `conftest.py` adds `sdk/` | CI on sdk/tests only | TST-01/02; guardian imports fixed (8 files); stats test → empty+warning |
| D6 Mock | `mock_mode_guard()` (cli_wrapper L132-135, builder_agent L604-606): warn logger+stderr; `QUANTLAB_ENV=production` + mock w/o `SQX_FORCE_MOCK` → raise | Silent fallback | MOK-01/02; production never silently simulates |
| D7 License | Real-path pre-flight `check()`; `SQX_LICENSE` short-circuits; raw output logged; production+non-LICENSED → raise; dev → warn; mock skips | Heuristics only | LIC guard; CI unblocked; no format parsing |
| D8 Dashboard | Path config→`SQX_INSTALL_PATH`→default (replaces app.py:62); endpoints on `KnowledgeStore`; stats empty-safe; report real data (fix L187-196); PID file `{pid,started_at}`: start writes, stop SIGTERM+remove, status uptime | ad-hoc sqcli shells; psutil | DSH-01/02; no psutil; liveness `os.kill(pid,0)` |
| D9 News | `_web_search/_rss_news=None`; lazy singletons, ImportError→None; `fetch_data` merges web+RSS (ticker-scoped, degrade); `build_prompt` URL/article, omit URL line if absent | Delete 17 RED tests | NWS-01/02/03; providers exist, guarded |
| D10 Zip | `git rm --cached`; `.gitignore assets/SQX_*.zip`; chain in `_resolve_sqx_install_path`; missing → clear error/warn | LFS | HGN-02; no test references it |

## Data Flow

    CLI → main() → api/dashboard → DashboardServer → Flask → KnowledgeStore → JSON
    run → dispatch_campaign → {license guard → mock guard} → real|mock
    stop/status → PID file (os.kill)

## File Changes

| File | Action | Changes |
|---|---|---|
| `sdk/quantlab/cli/__main__.py` | Create | `sys.exit(main())` |
| `sdk/quantlab/cli/main.py` | Modify | `api` subparser + `cmd_api` |
| `sdk/pyproject.toml` | Modify | `[build-system]`, `[project.scripts]` |
| `sdk/uv.lock` | Create | `uv lock` |
| `pytest.ini`; root `conftest.py` | Mod/Create | testpaths/norecursedirs; sys.path |
| `sdk/tests/test_guardian/*.py` (8) | Modify | import prefix |
| `sdk/tests/test_pr3_statistics_agent.py` | Modify | L427 → degrade assert |
| `Dockerfile` | Modify | drop poetry; `pip install -e .`; `PYTHONPATH=/app`; CMD `["quantlab","api"]` L122/157 |
| `docker-compose.yml` | Modify | 9 defects: contexts L10/47; dedupe container_name L44/49, deploy L66/80; `docker/` paths; drop certs/`data/sqx`; delete `Dockerfile.sqx` block; `SQX_INSTALL_PATH` |
| `.github/workflows/ci.yml` | Modify | `pip install -e "sdk[dev]"`; `pytest --cov --cov-report=xml:coverage.xml`; remove phantom docs job |
| junk: `=5.18`, `Save location: /`, `installer/`, `=3.0`, dup tests | Delete | `git rm` tracked; untracked deleted; HGN-03 separate commits |
| `STATE.md` | Mod/Del | refresh or remove |
| `assets/SQX_...zip` | Delete | `git rm --cached` + ignore |
| `sdk/quantlab/sqx/cli_wrapper.py` | Modify | `mock_mode_guard()` + license hook |
| `sdk/quantlab/agents/builder_agent.py` | Modify | reuse guard L604-606 |
| `sdk/quantlab/pipeline/license.py` | Modify | `SQX_LICENSE` override, raw log |
| `sdk/quantlab/dashboard/app.py` | Modify | path; real endpoints; report fix |
| `sdk/quantlab/cli/dashboard_commands.py` | Modify | PID start/stop/status |
| `sdk/quantlab/agents/llm_research_agent.py` | Modify | D9 (4 methods) |
| `sdk/quantlab/agents/prompts.py` | Modify | news template URL line |
| `sdd/`, `openspec/`, `refutation/` | Commit | own commits (HGN-03) |

## Interfaces

- `cmd_api(args) -> int`: `DashboardServer(host="0.0.0.0", port)`; Ctrl+C → 0.
- `mock_mode_guard(*, force_mock) -> None`: warn on mock; raise in production w/o `SQX_FORCE_MOCK`.
- License: `check()` + `SQX_LICENSE` short-circuit; `LicenseError` in production when not LICENSED.
- PID: `{pid, started_at}`; status → `{running, pid?, uptime_s?}`.
- News keys: `title, url, summary, source`; merged `news`, failure-tolerant.

## Testing Strategy

| Layer | What | How |
|---|---|---|
| Unit | `api` boots; `--help` 0; mock warn/raise matrix; license override; news (17); stats degrade; guardian collects | root pytest; RED-first for mock/license/PID |
| Integration | KnowledgeStore endpoints (empty-safe, 404); report non-empty; PID lifecycle | `tests/dashboard/`, `tests/sqx/` |
| E2E | fresh `uv sync` → `quantlab` on PATH; compose config; build + health 200 | CI + manual |

## Threat Matrix

All five rows **N/A** — no git/PR automation, docs-as-executable, or commit/push-state handling (git ops are one-off cleanup). Process boundary (non-VCS): PID os.kill + sqcli spawn — RED tests: missing PID → "not running"; stale PID → removed; SIGTERM removes file; `SQX_FORCE_MOCK` honored in production. Carried to tasks unchanged.

## Migration / Rollout

No data migration. `QUANTLAB_ENV` unset → dev semantics preserved. Slice 1 before Slice 2; every commit revertible; Docker CMD switches to `quantlab api` only after `api` lands.

## Open Questions

- [ ] nginx `certs/`: drop nginx or commit self-signed? (CID-04 allows either)
- [ ] Exact root pass count post-fix; STATE.md uses measured value.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Packaging breaks hand-rolled venv | Verify fresh `uv sync` AND `pip install -e "sdk[dev]"` |
| Deletions lose WIP | Only verified junk; reflog recoverable |
| Zip removal breaks refs | Grep-verified none; chain + clear error |
| CI divergence | testpaths includes both trees; root pytest + cov |
| `api` scope creep | Wraps dashboard only |
| Hard-fail breaks dev | Gated strictly on `QUANTLAB_ENV=production` |
