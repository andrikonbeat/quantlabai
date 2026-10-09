# Exploration: repo-organization-and-github-prep

## Current State

### Repository Overview
- **Location**: /home/ogzuz/Proyectos/QuantLab AI
- **Tracked files**: 10,737
- **Total size**: 12GB
- **Git status**: 89 modified/untracked files
- **Current branch**: feat/per-phase-subagent-delegation-pr5
- **GitHub repo**: https://github.com/andrikonbeat/quantlabai (EMPTY)

### Dead Code Confirmed
1. `missing.jfx` — 142B, untracked, not referenced anywhere
2. `notifications.jsonl` — 117B, untracked, referenced in code but generated at runtime
3. `.coverage` — 100KB, untracked, test coverage artifact
4. `build/compiled/` — empty directory, untracked
5. `demo_multi_agent.py` — 6.1KB, **TRACKED in git**, not referenced anywhere
6. `analysis/project_builder_config_coverage.md` — 16.6KB, untracked, not referenced anywhere

### Orphaned Infrastructure
1. `docker/nginx.conf` — 4.5KB, **TRACKED in git**, NOT referenced anywhere in active code (only in archived docs and venv files)
2. `docker/init-schema.sql` — 10.9KB, **TRACKED in git**, IS referenced in `docker-compose.yml` (line 87)

### app_movil/ State
- **Buildable**: YES — Complete Android project with `build.gradle.kts`, `settings.gradle.kts`, Gradle wrapper
- **Contents**: 15 Compose screens, Retrofit + Room, proper Android structure
- **Git status**: Mostly tracked (`quantlabai/` directory), plus untracked `quantlabai.zip:Zone.Identifier`
- **Referenced from**: NOWHERE in the main Python codebase
- **Internal refs**: Has its own `exploration.md` referencing backend integration

### Documentation Scattered at Root
- `PRD.md` — 28.9KB, **UNTRACKED**, not referenced anywhere
- `STATE.md` — 9.4KB, **TRACKED**, not referenced in code
- `exploration.md` — 15.2KB, **TRACKED**, not referenced in code
- `sdd_phase5f_i_spec_consolidated.md` — 10.3KB, **TRACKED**, not referenced in code
- `README.md` — 11.9KB, **TRACKED**, main project README
- `CHANGELOG.md` — 8.6KB, **TRACKED**

### doc_dev/ State
- `doc_dev/SQX Builder Config.md` — 24.1KB, **UNTRACKED**, **ACTIVELY USED** by `sdk/quantlab/knowledge/kb/seeder.py` as `DEFAULT_DOC_PATH`
- `doc_dev/SQX-KB Seed Validation Plan.md` — 9.1KB, **UNTRACKED**, referenced in specs and tasks
- `doc_dev/QuantLab AI.md` — 21.1KB, **UNTRACKED**, personal notes (Spanish)
- Various other Spanish personal notes (5 files total)

### .gitignore Issues
**Missing patterns:**
- `*.pyc` — Python bytecode (files not tracked, but should be ignored)
- `__pycache__/` — Python cache (not tracked)
- `.kotlin/` — Kotlin cache (not tracked)
- `.classes/` — Java classes (not tracked)
- `app_movil/**/build/` — Android build outputs (not tracked)
- `app_movil/**/.gradle/` — Gradle cache (not tracked)
- `*.Zone.Identifier` — Windows alternate data stream (not tracked, but exists untracked)
- `*.swp`, `*.swo`, `*~` — Vim swap files (not tracked)
- `.coverage` — Coverage artifact (not tracked)
- `notifications.jsonl` — Generated log (not tracked)
- `missing.jfx` — Stray file (not tracked)
- `demo_multi_agent.py` — Should be ignored but IS TRACKED
- `analysis/` — Should be ignored (directory exists, file not tracked)
- `build/` — Should be ignored (empty dir, not tracked)

**Incorrectly tracked files that should be ignored:**
- `_output/DryRunTest.cfx.xml`
- `_output/TestCampaign.cfx.json`
- `_output/portfolio-s1.cfx.json`
- `sdk/_output/DryRunTest.cfx.json`
- `sdk/_output/DryRunTest.cfx.xml`
- `demo_multi_agent.py`

### SQX Binaries
- `assets/SQX_144_2953_linux_20260601/` — 3.2GB, 201 tracked files
- This is a complete SQX distribution that should NOT be in git

### Hidden Issues
- NO merge conflict markers found
- NO broken symlinks found
- `docker-compose.yml` has no actual conflicts (false positives from comment lines)
- `openspec/changes/archive/2026-07-27-meta-guardian/verify-report.md` has `=======` in test output (not a real conflict)

### GitHub Repo State
- URL: https://github.com/andrikonbeat/quantlabai
- Status: EMPTY (no code, no README, no LICENSE)
- This is a fresh repo ready for initial push

## Affected Areas

- `.gitignore` — incomplete, missing many patterns, has tracked files that should be ignored
- `sdk/quantlab/knowledge/kb/seeder.py` — hardcoded path to `doc_dev/SQX Builder Config.md`
- `sdk/quantlab/knowledge/kb/seeding_flow.py` — hardcoded path to `doc_dev/SQX Builder Config.md`
- `sdk/quantlab/cli/sq_commands.py` — references `doc_dev/SQX Builder Config.md` in help text
- `sdk/tests/test_kb.py` — references `doc_dev/SQX Builder Config.md` in fixtures
- `docker-compose.yml` — references `./docker/init-schema.sql`
- `docker/nginx.conf` — tracked but unused
- `assets/SQX_144_2953_linux_20260601/` — 3.2GB tracked binary distribution
- Root documentation files (`PRD.md`, `STATE.md`, etc.) — scattered, should be organized

## Approaches

### Approach A: Minimal Cleanup (Low Effort)
1. Update .gitignore
2. Remove tracked generated files with `git rm --cached`
3. Move root docs to `docs/`
4. Move `doc_dev/` to `docs/sqx-builder-config/` and update code references
5. Delete dead files
6. Push to GitHub

**Pros**: Fast, low risk, addresses main issues
**Cons**: SQX binaries remain in git history (3.2GB)
**Effort**: Low

### Approach B: Full Cleanup with History Rewrite (Medium Effort)
1. All of Approach A
2. Use BFG Repo-Cleaner to remove SQX binaries from git history
3. Force push to GitHub

**Pros**: Clean repository, saves 3.2GB in history
**Cons**: Requires force push, rewrites history, coordination needed if others have cloned
**Effort**: Medium

### Approach C: Complete Restructure (High Effort)
1. All of Approach B
2. Move `app_movil/` to `apps/mobile/`
3. Reorganize entire directory structure
4. Update all imports and references

**Pros**: Perfect organization
**Cons**: High risk of breaking things, many files to update
**Effort**: High

## Recommendation

**Approach B (Full Cleanup with History Rewrite)** is recommended because:
1. The 3.2GB SQX binaries are the biggest issue and should be removed from history
2. The repository is currently only on one machine (no team coordination needed)
3. The GitHub repo is empty, so no existing history to preserve
4. This is the right time to do a full cleanup before the first public push

## Risks

1. **SQX removal from history**: HIGH risk if force push causes issues, but mitigated by empty GitHub repo
2. **Path updates for doc_dev/**: MEDIUM risk — must update seeder.py, tests, and specs
3. **Breaking app_movil/ references**: LOW risk — no references found in Python code
4. **Accidentally deleting needed files**: LOW risk — all dead files confirmed unused

## Ready for Proposal

Yes. The orchestrator should tell the user:

> The exploration is complete. The main issues are:
> 1. 3.2GB of SQX binaries tracked in git (must be removed from history)
> 2. Generated files (`_output/`, `sdk/_output/`, `demo_multi_agent.py`) tracked but should be ignored
> 3. Dead code (`missing.jfx`, `.coverage`, `analysis/`) needs deletion
> 4. `docker/nginx.conf` is tracked but unused
> 5. Documentation scattered at root should move to `docs/`
> 6. `doc_dev/` files are actively used by the KB seeder and must be moved carefully
> 7. GitHub repo is empty and ready for first push
>
> Recommended approach: Full cleanup with BFG to remove SQX from history, then push. This is safe because the GitHub repo is empty.
>
> Do you want to proceed with the proposal phase?
