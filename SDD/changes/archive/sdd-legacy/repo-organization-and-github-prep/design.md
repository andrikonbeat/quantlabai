# Design: Repository Organization and GitHub Preparation

## Technical Approach

Six-step atomic sequence: (1) commit valuable untracked modules, (2) delete broken/dead/duplicate paths, (3) move docs and update path references, (4) `.gitignore`/`.gitattributes`, (5) sync prompts and refresh `STATE.md`, (6) add remote and push. Every step is independently verifiable and independently reversible from `backup/pre-cleanup`. No functional code changes, no history rewrite.

## Architecture Decisions

### Decision: No history rewrite (BFG obsolete)

**Choice**: Skip BFG and `git filter-repo` entirely.  
**Alternatives considered**: BFG Repo-Cleaner, `git filter-repo` (original plan).  
**Rationale**: Audit proved the 3.2GB SQX binaries were never committed — `git log --all -- assets/` = 0 commits, `git ls-files assets` = 0, pack = 3.84 MiB, `.git` = 6.3MB. There is no history to rewrite and no force-push to the empty remote is needed. A rewrite would be pure risk with zero benefit.

### Decision: Triage untracked work — conserve valuable, delete broken/duplicate

**Choice**: Commit the audit-verified valuable modules; delete broken and duplicate paths.  
**Alternatives considered**: Commit everything, delete everything.  
**Rationale**: The 56 untracked paths are a mix of valuable, working code (market data providers, adaptive retest agent, custom templates, template registry, their tests) and broken/duplicate artifacts (`market_analysis_stage.py` imports `MarketAnalysisStage` from `agent_stages.py` which does not define it, is not in the registry, and has RED tests that can never pass; `sdk/knowledge/` duplicates the root knowledge lake with 0 tracked files). Committing broken code would poison the first public push.

### Decision: Delete `sdk/quantlab/pipeline/stages/market_analysis_stage.py` and its test

**Choice**: Delete the module and `sdk/tests/pipeline/test_market_analysis_stage.py`.  
**Alternatives considered**: Fix the import, register the stage.  
**Rationale**: The referenced base class does not exist and the stage is not in the registry. Fixing it is a functional change outside this planning refresh; deletion is the correct hygiene action. This supersedes the audit's ambiguous listing of the test under both valuable and broken — the explicit decision is delete.

### Decision: `docs/sqx-builder-config/` over `docs/reference/`

**Choice**: Move `doc_dev/` → `docs/sqx-builder-config/`.  
**Alternatives considered**: `docs/reference/`, `docs/builder-config/`.  
**Rationale**: Preserves the semantic "SQX Builder Config" name that appears in `DEFAULT_DOC_PATH`, help text, and docstrings. Shorter than `builder-config` and more specific than `reference`.

### Decision: Delete `docker/nginx.conf` rather than move to `infra/`

**Choice**: Delete untracked, unused `docker/nginx.conf`.  
**Alternatives considered**: Move to `infra/nginx.conf`.  
**Rationale**: Exploration confirmed zero references in active code. Moving unused files adds noise. Recoverable from `backup/pre-cleanup` if ever needed.

### Decision: Move `docker/init-schema.sql` → `infra/init-schema.sql`

**Choice**: Move to `infra/` (new directory).  
**Alternatives considered**: Delete, leave in `docker/`.  
**Rationale**: Actively referenced in `docker-compose.yml` (~line 87). `infra/` better reflects its role as DB initialization schema.

### Decision: Copy `guardian.md` into the repo

**Choice**: Copy live `~/.config/opencode/prompts/quantlab/guardian.md` → `AI/opencode/agents/guardian.md`.  
**Alternatives considered**: Leave it live-only.  
**Rationale**: `sync_prompts.py` manages only `campaign.md` + `phase-*.md`; `guardian.md` is non-managed and currently exists only live. Versioning it in the repo preserves it. The script's allowlist logic already treats non-managed files as never-written-never-deleted, so a repo copy is safe.

### Decision: Add remote before push

**Choice**: `git remote add origin https://github.com/andrikonbeat/quantlabai` as a dedicated step before the first push.  
**Alternatives considered**: None — `git remote -v` is empty, so a push cannot succeed without it.  
**Rationale**: The repo exists and is empty; this is a prerequisite, not an afterthought.

## Data Flow

    Untracked triage ──→ Dead/broken deletion ──→ Doc moves + reference updates
                │                                        │
                │                             .gitignore/.gitattributes
                │                                        │
                │                             Prompt sync + STATE.md refresh
                │                                        │
                │                             Remote add → push (main + feature)
                ▼

    Every step verifiable against backup/pre-cleanup.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/data/market/` (`__init__.py`, `models.py`, `providers.py`, `registry.py`) | `git add` | Valuable untracked module |
| `sdk/quantlab/agents/adaptive_retest_agent.py` | `git add` | 448 lines, valuable |
| `sdk/quantlab/customproject/templates.py` | `git add` | 446 lines, valuable |
| `sdk/quantlab/phase4/template_registry.py` | `git add` | 85 lines, valuable |
| `sdk/quantlab/dashboard/tests/test_cors.py` | `git add` | Valuable test |
| `sdk/tests/data/test_market.py` | `git add` | Valuable test |
| `sdk/tests/agents/test_analysis_agent_frame.py` | `git add` | Valuable test |
| `sdk/tests/jforex/test_config.py` | `git add` | Valuable test |
| `sdk/tests/contract/` | `git add` | Valuable contract tests |
| `tests/agents/test_adaptive_retest_agent.py` | `git add` | 494 lines, valuable |
| `tests/customproject/test_templates.py` | `git add` | 738 lines, valuable |
| `PRD.md` | `git add` then move | Valuable untracked root doc → `docs/PRD.md` |
| `doc_dev/*.md` | `git add` then move | Valuable config/personal notes → `docs/sqx-builder-config/` |
| `doc_dev/*.Zone.Identifier` | Delete | Windows ADS junk |
| `knowledge/agent-memory/`, `knowledge/structured/`, `knowledge/timeseries/` | `git add` | Data dirs (root knowledge lake already 102 tracked files) |
| `openspec/specs/<new specs>` | `git add` | New spec artifacts |
| `openspec/changes/archive/<new archives>`, `openspec/changes/compiler-deploy-demo/` | `git add` | Archived SDD artifacts |
| `sdd/repo-organization-and-github-prep/` | `git add` | This change's own artifacts |
| `sdk/quantlab/pipeline/stages/market_analysis_stage.py` | Delete | Broken — undefined import, not in registry |
| `sdk/tests/pipeline/test_market_analysis_stage.py` | Delete | Test of the broken module |
| `sdk/knowledge/` | `rm -rf` | Stale duplicate (132K, 0 tracked, unreferenced) |
| `sdk/quantlab/phase4/lock.py` | `git rm` | Dead code (155 lines) |
| `sdk/quantlab/phase4/daemon_manager.py` | `git rm` | Dead code (286 lines) |
| `sdk/quantlab/jforex/llm_agent.py` | `git rm` | Dead code (122 lines) |
| `sdk/quantlab/knowledge/training.py` | `git rm` | Dead code (152 lines) |
| `sdk/quantlab/agents/ops_surface.py` | `git rm` | Dead code (309 lines) |
| `demo_multi_agent.py` | `git rm` | Tracked, unreferenced (175 lines) |
| `sdk/quantlab/regime/` | `rmdir` | Empty directory |
| `.classes/missing.class` | Delete | Untracked, unignored |
| `doc_dev/` | Move → `docs/sqx-builder-config/` | KB seeder source docs |
| `PRD.md`, `STATE.md`, `exploration.md`, `sdd_phase5f_i_spec_consolidated.md`, `CHANGELOG.md` | Move → `docs/` | Root doc reorg |
| `docker/init-schema.sql` | Move → `infra/init-schema.sql` | Active DB init |
| `docker/nginx.conf` | Delete | Untracked, unused |
| `docker-compose.yml` | Modify (~line 87) | `${SQX_PATH}/infra/init-schema.sql` + `SQX_PATH` env |
| `AI/opencode/agents/guardian.md` | Add | Copy from live |
| `STATE.md` | Modify | Refresh to current reality |
| `.gitignore` | Modify | Add missing patterns; remove `=3.0`, `_run_campaign.py` |
| `.gitattributes` | Create | LFS rules |
| `README.md` | Keep/polish | GitHub entry point |
| `LICENSE` | Create | MIT license |
| `SECURITY.md` | Create | Security policy |
| `infra/` | Create | New directory for `init-schema.sql` |
| `docs/` | Create | New directory for root docs + doc_dev |

## Interfaces / Contracts

**`DEFAULT_DOC_PATH` constant** — single source of truth for KB seeder doc location.

```python
# sdk/quantlab/knowledge/kb/seeder.py
DEFAULT_DOC_PATH = "docs/sqx-builder-config/SQX Builder Config.md"
```

All code references (`seeder.py`, `seeding_flow.py`, `sq_commands.py`, `test_kb.py`, `__init__.py`) must resolve to this path. CLI `--doc` default inherits from `DEFAULT_DOC_PATH`; only help text string needs update.

## Path Reference Updates

| File | What to change | New value |
|------|---------------|-----------|
| `sdk/quantlab/knowledge/kb/seeder.py:28` | `DEFAULT_DOC_PATH` | `"docs/sqx-builder-config/SQX Builder Config.md"` |
| `sdk/quantlab/knowledge/kb/seeder.py:3` | Module docstring | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/quantlab/knowledge/kb/seeder.py:64` | Comment | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/quantlab/knowledge/kb/seeder.py:838` | Docstring | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/quantlab/knowledge/kb/seeder.py:902` | Docstring | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/quantlab/knowledge/kb/seeding_flow.py:4` | Module docstring | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/quantlab/knowledge/kb/seeding_flow.py:195` | Docstring | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/quantlab/knowledge/kb/__init__.py:4` | Module docstring | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/quantlab/cli/sq_commands.py:379` | Help text | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/tests/test_kb.py:6` | Module docstring | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/tests/test_kb.py:28` | Fixture comment | `docs/sqx-builder-config/SQX Builder Config.md` |
| `sdk/tests/test_kb.py:347` | Docstring | `docs/sqx-builder-config/SQX Builder Config.md` |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | KB seeder path resolution | Run `test_kb.py` after path updates; verify `DEFAULT_DOC_PATH` resolves |
| Integration | `run_seed_flow` end-to-end | Run `test_kb_seed_validation.py`; verify seed + validate pipeline |
| Unit | Newly committed modules | Run their test files after PR1: `test_market.py`, `test_analysis_agent_frame.py`, `test_config.py`, `test_adaptive_retest_agent.py`, `test_templates.py`, contract tests |
| Verification | Broken module absent | `git ls-files | grep market_analysis_stage` → empty |
| Verification | Dead code absent | `git ls-files` → listed dead paths absent |
| Verification | Prompt sync | `python3 AI/opencode/sync_prompts.py --check` → exit 0 |
| Verification | Docker compose | `docker compose config` after path updates; validate mount paths |
| Verification | Remote + push | `git ls-remote origin` shows `main` + feature branch |

## Threat Matrix

| Boundary | Minimum adversarial cases | Applicability | Design response | Planned RED tests |
|---|---|---|---|---|
| Documentation-like paths | `requirements.txt`, `CMakeLists.txt`, executable Markdown/MDX, `README.sh` | N/A — no executable document classification in this change | N/A | None |
| Git repository selection | `git -C`, relative paths, absolute paths | **Applicable** — `git add`/`git rm`/`git mv`/`git push` all require correct repo root | All git operations run from repo root via absolute `git -C <repo>` | Test: operations affect the intended repo (not cwd-dependent) |
| Commit state | staged, `commit -a`, empty index | **Applicable** — `git rm` must commit the removal; `git add` must stage untracked | Stage in dedicated commits per PR; verify `git status` clean before push | Test: untracked valuable files staged, broken files never staged |
| Push state | tracking branch, first push, empty remote, no `origin` | **Applicable** — first push to empty GitHub repo with NO remote configured | Add `origin` before push; push `main` + feature branch; verify `git ls-remote` | Test: push to fresh remote succeeds only after remote add |
| PR commands | explicit `--head`, environment prefix, composed commands | N/A — push is direct to remote; no PR automation in this change | N/A | None |

## Migration / Rollout

No runtime migration. Entire change is a three-PR repo restructure followed by a first push to an empty remote:

1. **PR 1 (cleanup)**: Triage untracked (commit valuable / delete broken+duplicate), delete dead code, fix affected tests
2. **PR 2 (reorg)**: Move docs, update path references, sync prompts, refresh `STATE.md`
3. **PR 3 (github)**: `.gitignore`/`.gitattributes`, docker moves + compose, README/LICENSE/SECURITY, remote add + push

Each PR is reviewable and reversible independently; no force-push anywhere.

## Rollback Plan

| Step | Rollback command |
|------|-----------------|
| 1. Backup | `git branch -f backup/pre-cleanup HEAD` (ref already exists from aborted first run — refresh to current state) |
| 2. PR1 triage/deletions | `git reset --hard backup/pre-cleanup` |
| 3. PR2 moves/refs | `git checkout backup/pre-cleanup -- <paths>` or full reset |
| 4. PR3 gitignore/attributes | Revert specific file edits from backup ref |
| 5. Prompt sync / STATE.md | Revert files from backup ref; re-sync prompts if needed |
| 6. Docker compose | Revert from backup ref |
| 7. Remote add + push | `git remote remove origin` (restores pre-push state); local reset to backup ref |

**Critical**: `backup/pre-cleanup` must NOT be deleted until the GitHub push is verified successful.

## Verification Checklist

- [ ] `git branch -f backup/pre-cleanup HEAD` (backup refreshed to current state)
- [ ] `git ls-files | grep market_analysis_stage` returns empty
- [ ] `git ls-files | grep -E "lock\.py|daemon_manager|llm_agent|training\.py|ops_surface|demo_multi_agent"` returns empty
- [ ] `sdk/knowledge/` and `sdk/quantlab/regime/` do not exist
- [ ] Valuable modules committed: `git ls-files | grep -E "data/market|adaptive_retest|templates\.py|template_registry"` shows paths
- [ ] Newly committed tests pass (listed test files)
- [ ] `git ls-files | grep doc_dev` returns empty (after move)
- [ ] `git ls-files | grep "docs/sqx-builder-config"` shows the moved files
- [ ] `python -c "from quantlab.knowledge.kb.seeder import DEFAULT_DOC_PATH; print(DEFAULT_DOC_PATH)"` → `docs/sqx-builder-config/SQX Builder Config.md`
- [ ] `python -m pytest sdk/tests/test_kb.py -q` passes
- [ ] `python -m pytest sdk/tests/test_kb_seed_validation.py -q` passes
- [ ] `python3 AI/opencode/sync_prompts.py --check` exits 0
- [ ] `AI/opencode/agents/guardian.md` exists and matches live
- [ ] `STATE.md` names the real branch and ahead count
- [ ] `docker compose config` validates without errors
- [ ] `.gitignore` contains the new patterns and NOT `=3.0` / `_run_campaign.py`
- [ ] `.gitattributes` exists with LFS rules
- [ ] `README.md`, `LICENSE`, `SECURITY.md` present at repo root
- [ ] `git remote add origin https://github.com/andrikonbeat/quantlabai` succeeds
- [ ] `git push` succeeds; `git ls-remote origin` shows `main` + `feat/per-phase-subagent-delegation-pr5`

## Open Questions

- [ ] Confirm `.atl/skill-registry.md` (tracked, generated registry) — keep tracked or ignore
- [ ] Confirm which branch should become GitHub default (`main` vs feature) — plan pushes both
- [ ] Confirm Spanish personal notes in `doc_dev/` move to `docs/sqx-builder-config/` unchanged