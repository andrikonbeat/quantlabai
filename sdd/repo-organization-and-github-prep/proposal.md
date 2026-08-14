# Proposal: Repository Organization and GitHub Preparation

## Intent

Triage 56 untracked paths on the current feature branch (commit valuable modules, delete broken/duplicate), delete confirmed dead code, reorganize scattered docs, complete `.gitignore`/`.gitattributes`, sync prompts, and prepare for the first public push to GitHub. Non-code infrastructure change.

**No history rewrite is required.** The 3.2GB SQX binaries were never committed (`git log --all -- assets/` = 0 commits; `git ls-files assets` = 0; pack = 3.84 MiB, `.git` = 6.3MB). The old BFG approach is obsolete.

## Scope

### In Scope
- Triage untracked work: commit valuable modules, delete broken/duplicate paths
- Delete confirmed dead code (tracked and untracked)
- Delete broken module `sdk/quantlab/pipeline/stages/market_analysis_stage.py` + its test (impossible import, RED tests can never pass)
- Delete `sdk/knowledge/` (stale duplicate of root knowledge lake, 0 tracked files, no code references)
- Move root docs to `docs/`
- Move `doc_dev/` → `docs/sqx-builder-config/` and update code references
- Move `docker/init-schema.sql` → `infra/`; delete `docker/nginx.conf` (unused)
- Complete `.gitignore` (add missing patterns, remove stale entries) and add `.gitattributes`
- Sync prompts (`AI/opencode/sync_prompts.py`) and refresh `STATE.md`
- Add git remote `origin` (currently EMPTY) and push
- Delete `app_movil/quantlabai.zip:Zone.Identifier` junk, ignore `*.Zone.Identifier`

### Out of Scope
- Functional code changes
- Moving `app_movil/` to `apps/mobile/`
- Git history rewrite (BFG / filter-repo) — not needed, SQX never committed
- Full directory restructure beyond the listed moves

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- None

## Approach

Triage + cleanup + reorg + push. Since SQX binaries were never committed, no history rewrite and no force-push are needed. The repository is already under 1GB. The git remote is empty and must be added before the first push.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `.gitignore` | Modified | Add `*.pyc`, `__pycache__/`, `.kotlin/`, `.classes/`, `app_movil/**/build/`, `app_movil/**/.gradle/`, `*.Zone.Identifier`, `.coverage`, `notifications.jsonl`, `missing.jfx`; remove stale `=3.0`, `_run_campaign.py` |
| `.gitattributes` | Created | LFS rules for binary artifacts |
| `sdk/quantlab/data/market/` | Committed | Valuable untracked module |
| `sdk/quantlab/agents/adaptive_retest_agent.py` | Committed | Valuable untracked module |
| `sdk/quantlab/customproject/templates.py` | Committed | Valuable untracked module |
| `sdk/quantlab/phase4/template_registry.py` | Committed | Valuable untracked module |
| `sdk/quantlab/dashboard/tests/` | Committed | Valuable untracked tests |
| `sdk/tests/`, `tests/` (listed modules) | Committed | Valuable untracked tests |
| `PRD.md`, `doc_dev/`, `knowledge/` data dirs, `openspec/` new specs, `sdd/` | Committed | Valuable untracked docs/artifacts |
| `sdk/quantlab/pipeline/stages/market_analysis_stage.py` | Deleted | Broken — imports undefined `MarketAnalysisStage`; not in registry |
| `sdk/tests/pipeline/test_market_analysis_stage.py` | Deleted | Test of the broken module, can never pass |
| `sdk/knowledge/` | Deleted | Stale duplicate of root knowledge lake (132K, 0 tracked) |
| `sdk/quantlab/phase4/lock.py` | Deleted | Dead code |
| `sdk/quantlab/phase4/daemon_manager.py` | Deleted | Dead code |
| `sdk/quantlab/jforex/llm_agent.py` | Deleted | Dead code |
| `sdk/quantlab/knowledge/training.py` | Deleted | Dead code |
| `sdk/quantlab/agents/ops_surface.py` | Deleted | Dead code |
| `sdk/quantlab/regime/` | Deleted | Empty directory |
| `demo_multi_agent.py` | Deleted | Tracked, unreferenced |
| `.classes/missing.class` | Deleted | Untracked, unignored |
| `doc_dev/` | Moved | → `docs/sqx-builder-config/`; update KB seeder and test references |
| Root docs | Moved | `PRD.md`, `STATE.md`, `exploration.md`, `sdd_phase5f_i_spec_consolidated.md`, `CHANGELOG.md` → `docs/` |
| `docker/init-schema.sql` | Moved | → `infra/init-schema.sql`; update `docker-compose.yml` |
| `docker/nginx.conf` | Deleted | Untracked, unused |
| `AI/opencode/agents/guardian.md` | Added | Copy from live `~/.config/opencode/prompts/quantlab/` |
| `STATE.md` | Modified | Refresh to current reality (branch, ahead count, resolved untracked) |
| `README.md`, `LICENSE`, `SECURITY.md` | Present | GitHub readiness files |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Valuable untracked module committed but broken | Medium | Commit only audit-verified modules; delete broken `market_analysis_stage.py`; run its test files after commit |
| Path updates break KB seeder | Medium | Update all references in `seeder.py`, `seeding_flow.py`, `sq_commands.py`, `__init__.py`, `tests/test_kb.py`; run `test_kb.py` |
| Accidental deletion of a needed file | Low | `backup/pre-cleanup` ref before deletions; verify references before deleting |
| Push to empty remote fails on first attempt | Low | Add `origin` before push; push `main` and feature branch; verify with `git ls-remote` |
| Prompt sync drift (live vs repo) | Low | `sync_prompts.py --check` gates; copy guardian prompt into repo; re-sync |

## Rollback Plan

Refresh/keep backup ref `backup/pre-cleanup` (already exists from the aborted first plan run) to current HEAD before any destructive step. Each PR is independently reversible from that ref. No history rewrite → no force-push recovery needed. If remote push is wrong, `git remote remove origin` restores the pre-push state.

## Dependencies

- Git LFS (for `.gitattributes`)
- GitHub repo `https://github.com/andrikonbeat/quantlabai` (exists, empty)

## Success Criteria

- [ ] Repository size already under 1GB (pack = 3.84 MiB) — no size target needed
- [ ] `.gitignore` complete; no tracked files matching ignore patterns
- [ ] No broken modules committed (`market_analysis_stage.py` + its test gone)
- [ ] Dead/duplicate code removed (listed files absent from `git ls-files`)
- [ ] Docs organized under `docs/`; `doc_dev/` moved with references updated
- [ ] `STATE.md` accurate (real branch, ahead count, resolved untracked)
- [ ] Prompts synced: `sync_prompts.py --check` exits 0; guardian prompt present in repo
- [ ] `README.md`, `LICENSE`, `SECURITY.md` present
- [ ] `git remote add origin https://github.com/andrikonbeat/quantlabai` succeeds; push succeeds