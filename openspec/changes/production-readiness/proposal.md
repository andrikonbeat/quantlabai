# Proposal: Production Readiness

## Intent

Make QuantLab AI production-usable: installable, testable, deployable. Today: broken Docker CMD, 18 red tests, 4 missing deps, poetry/uv/pip mismatch, silent mock, unvalidated license, tracked junk.

## Scope

### Slice 1 — Foundation
- Entrypoint: `cli/__main__.py`, `api` subcommand, `[project.scripts]`, `[build-system]`, lockfile
- Deps: mcp, openai, feedparser, duckduckgo-search
- Docker/CI: build-system install, PYTHONPATH, CMD; compose fixes (contexts, dedupe, `docker/` paths); `pip install -e "sdk[dev]"`, coverage.xml, docs job
- Tests: pytest.ini testpaths, guardian imports, stats, news
- Junk: git rm =5.18, "Save location: /", =3.0, installer skeleton, dup tests; refresh STATE.md

### Slice 2 — Behavior hardening
- Dashboard: env-driven sqcli path, ~6 real-code endpoints, PID stop/status
- Mock: loud warning; production hard-fail without SQX_FORCE_MOCK
- License: check() on real dispatch; block in production only; SQX_LICENSE override; log raw output

### Out of Scope
Installer impl | refutation completion | poetry migration | SQX zip history removal | real license validation | config-wizard/autonomous-monitor

## Capabilities

**New**: `cli-entrypoint` (script, `__main__`, `api`)
**Modified**: `dashboard-api` (env/real endpoints) | `sqx-cli-wrapper` (mock loudness) | `license-manager` (guard) | `llm-research` (Q2)

## Approach

- Entrypoint: proper fix (Option 1), not Option 2
- Lockfile via uv; news: 4 methods via guarded providers (default) or delete
- Stats: assert graceful-degrade + warning; guardian: fix imports; rest minimal

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/` (quantlab, pyproject.toml, pytest.ini) | Modified | entrypoint, api, stop/status, mock, license, deps, testpaths |
| `Dockerfile`, `docker-compose.yml`, `ci.yml` | Modified | install, CMD, contexts, coverage |
| `=5.18`, `Save location: /`, `=3.0` | Removed | junk |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Packaging breaks hand-rolled venv | Med | Verify fresh uv sync in clean venv |
| Deletions lose WIP | Med | Triage 29 entries; delete only verified junk |

## Rollback Plan

Per-slice commits → git revert; junk recoverable via reflog; keep old CMD until verified.

## Dependencies

uv or pip-tools; Docker daemon; Q1–5 answers.

## Success Criteria

- [ ] `quantlab api` boots server
- [ ] Fresh uv sync; console script works
- [ ] CI green; coverage.xml generated
- [ ] Bare pytest: ~1315 pass / 0 fail
- [ ] compose config + docker build valid
- [ ] Mock warns; production hard-fails
- [ ] License active on real dispatch; junk gone

## Proposal Question Round — RESOLVED (user, 2026-07-31)

1. SQX zip: **remove from repo** — `git rm --cached` + external volume; runtime resolves via config → `SQX_INSTALL_PATH` → default. No LFS.
2. News: **implement the 4 methods** — `get_web_search`, `get_rss_news`, `fetch_data`, `build_prompt` with guarded providers; make the 17 RED tests green.
3. Dashboard: **minimal real API** — env-driven sqcli path, ~6 real-code endpoints, PID stop/status.
4. License: **env-based minimal** — `check()` on real dispatch blocks in production without `SQX_LICENSE`; no real-format parsing.
5. Untracked triage: **as proposed** — delete installer skeleton + duplicated tests + tracked junk (`=5.18`, `Save location: /`); commit specs + refutation in own commits.
