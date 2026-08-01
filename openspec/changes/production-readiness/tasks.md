# Tasks: Production Readiness

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1000–1100 authored (S1 ≈ 300, S2 ≈ 750; `uv.lock` generated, excluded from authored count) |
| 400-line budget risk | High (total); S1 Medium, S2 High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Slice 1 Foundation) → PR 2 (Slice 2 Behavior) |
| Delivery strategy | single-pr-default → stacked-to-main (pre-resolved) |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Chain strategy pre-resolved by user (stacked-to-main). If feature-branch-chain is preferred, say so before apply. Decision (a): DROP nginx service — self-signed `.pem` in repo violates config sensitive-file pattern (`**/*.pem`); TLS out of scope. Decision (b): STATE.md uses measured pass count.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | S1 Foundation: packaging, tests, docker/CI, junk | PR 1 | `pytest -q` (root) | fresh `uv sync` → `quantlab --help`; `docker compose config` | revert S1 commits; S2 unaffected |
| 2 | S2 Behavior: guards, license, API, news | PR 2 | `pytest tests/sqx tests/dashboard sdk/tests/agents/test_llm_agent_news.py -q` | `quantlab api` + `curl :8080/api/health`; prod hard-fail demo | revert S2 commits only |

## Phase 1 — Slice 1: SDK packaging & tests

- [x] **T1 (S1)** `sdk/pyproject.toml`: add `[build-system]` (setuptools) + `[project.scripts] quantlab = quantlab.cli.main:cli_entry` + declare mcp/openai/feedparser/duckduckgo-search deps (CLI-01/04, DEP-01) · verify: `uv sync` + `quantlab --help` exit 0 · ~18
- [x] **T2 (S1)** create `sdk/quantlab/cli/__main__.py` (`sys.exit(main())`); add `api` subparser to `sdk/quantlab/cli/main.py` → `cmd_api` boots `DashboardServer(ServerConfig(host="0.0.0.0", port))`, Ctrl+C → 0 (CLI-02/03) · verify: `python -m quantlab.cli api` + `curl :8080/api/health` 200 · ~55
- [ ] **T3 (S1)** run `uv lock` → commit `sdk/uv.lock` (CLI-04) · dep: T1 · verify: fresh `uv sync` green · ~30 (generated, excluded)
- [x] **T4 (S1)** `pytest.ini`: `testpaths = tests sdk/tests`, `norecursedirs = assets sdk/.venv .venv venv .git build dist __pycache__ *.egg-info`; root `conftest.py` adds `sdk/` to sys.path (TST-01/02) · verify: bare `pytest` collects both trees · ~20
- [ ] **T5 (S1)** fix imports in 8 `sdk/tests/test_guardian/*.py`: `sdk.quantlab...` → `quantlab...` (TST-03) · verify: `pytest sdk/tests/test_guardian -q` 0 collection errors · ~8
- [ ] **T6 (S1)** `sdk/tests/test_pr3_statistics_agent.py::test_run_missing_export_paths_raises` → assert empty stats + warning, no ValueError (TST-04) · verify: test passes · ~12

## Phase 2 — Slice 1: Deploy & hygiene

- [ ] **T7 (S1)** `Dockerfile`: remove poetry blocks (L96–102), `pip install -e .`, keep PYTHONPATH, set CMDs L122/157 to `["quantlab","api"]` (CID-03) · dep: T2 · verify: `docker build` + health 200 · ~30
- [ ] **T8 (S1)** `docker-compose.yml` fix 9 defects: contexts L10/47 → `docker/`, dedupe container_name L44/49 + deploy L66/80, drop `Dockerfile.sqx` block + `data/sqx` + `certs/`, drop nginx service (CID-04, decision a) · verify: `docker compose config` clean · ~45
- [ ] **T9 (S1)** `.github/workflows/ci.yml`: `pip install -e "sdk[dev]"`, `pytest --cov --cov-report=xml:coverage.xml`, delete phantom docs job (CID-01/02) · verify: CI green + `sdk/coverage.xml` uploaded · ~25
- [ ] **T10 (S1)** junk removal: `git rm` `=5.18`, `Save location: /`, installer skeleton (go.sum + binary), dup test files (root `test_refutation_layer.py`); delete untracked `=3.0` (HGN-01) · verify: `git ls-files` shows none · ~25
- [ ] **T11 (S1)** `git rm --cached assets/SQX_144_2953_linux_20260601.zip` + `.gitignore` `assets/SQX_*.zip` (HGN-02) · verify: zip absent from `git ls-files` · ~2
- [ ] **T12 (S1)** triage commits: `sdd/`+`openspec/` own commit; refutation (`sdk/quantlab/agents/refutation/`, tests) own commit; deletions own commits (HGN-03) · verify: `git log` shows clean groups · ~5
- [ ] **T13 (S1)** refresh `STATE.md`: current workflow, measured pass count (decision b), drop poetry/630 claims (HGN-04) · dep: T4–T6 · verify: no stale claims · ~30

## Phase 3 — Slice 2: Guards (RED-first)

- [ ] **T14 (S2)** RED: PID tests — missing PID → "not running"; stale PID → removed; SIGTERM removes file (DSH-02, threat-matrix) · `sdk/tests/dashboard/` · ~30
- [ ] **T15 (S2)** impl `sdk/quantlab/cli/dashboard_commands.py` PID start (write `{pid, started_at}`), stop (SIGTERM + remove), status (uptime via os.kill) (DSH-02) · dep: T14 · verify: T14 green · ~60
- [ ] **T16 (S2)** RED: mock guard — warn on missing sqcli; warn on `SQX_FORCE_MOCK`; prod w/o force raises; prod+force → mock + warn (MOK-01/02, threat-matrix) · `tests/sqx/` · ~70
- [ ] **T17 (S2)** impl `mock_mode_guard()` in `sdk/quantlab/sqx/cli_wrapper.py` (L132–135); reuse in `sdk/quantlab/agents/builder_agent.py` (L604–606) (MOK-01/02) · dep: T16 · verify: T16 green · ~30
- [ ] **T18 (S2)** RED: license — `SQX_LICENSE` short-circuits; raw output logged; prod unlicensed raises; dev warns; mock skips (LIC, LIC-02) · `tests/sqx/` · ~60
- [ ] **T19 (S2)** impl `sdk/quantlab/pipeline/license.py`: pre-flight `check()` on real dispatch, `SQX_LICENSE` override, raw `-license action=info` logging, prod raise / dev warn (LIC, LIC-02) · dep: T18 · verify: T18 green · ~35

## Phase 4 — Slice 2: Dashboard & news

- [ ] **T20 (S2)** `sdk/quantlab/dashboard/app.py`: replace L62 hardcode with config → `SQX_INSTALL_PATH` → default chain; unresolvable → clear "sqcli unavailable" error (DSH-01) · verify: env path used · ~20
- [ ] **T21 (S2)** RED: API tests — campaigns list/empty, detail/404, pipeline list/detail/404, stats empty-safe, report real data (DSH-MOD) · `sdk/tests/dashboard/` · ~120
- [ ] **T22 (S2)** impl `GET /api/campaigns` + `/api/campaigns/{id}` on KnowledgeStore (metrics, equity/trades/statistics/phases, 404 envelope) (DSH-MOD) · dep: T21 · verify: T21 green · ~70
- [ ] **T23 (S2)** impl `GET /api/pipeline[/{run_id}]` + `GET /api/stats` (empty-safe aggregates) (DSH-MOD) · dep: T21 · verify: T21 green · ~60
- [ ] **T24 (S2)** fix report bug: `POST /api/reports/generate` uses real export_paths data (app.py L187–196), 404 for missing campaign (DSH-MOD) · dep: T22 · verify: non-empty report · ~35
- [ ] **T25 (S2)** news: `sdk/quantlab/agents/llm_research_agent.py` — `_get_web_search`/`_get_rss_news` lazy singletons (ImportError→None), `fetch_data` merge (ticker-scoped, degrade), `build_prompt` URLs; `sdk/quantlab/agents/prompts.py` news template URL line (NWS-01/02/03) · verify: 17 tests in `sdk/tests/agents/test_llm_agent_news.py` green · ~110
