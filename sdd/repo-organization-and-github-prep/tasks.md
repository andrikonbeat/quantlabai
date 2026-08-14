# Tasks: Repository Organization and GitHub Preparation

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | PR1 ~17k nominal (bulk-commit of existing untracked artifacts; ~1.6k review-relevant deletions), PR2 ~500, PR3 ~400 |
| 400-line budget risk | High (PR1), Medium (PR2), Low (PR3) |
| Chained PRs recommended | Yes (3) |
| Suggested split | PR 1: Untracked triage + dead-code deletion → PR 2: Doc reorg + refs + prompt sync + STATE.md → PR 3: Gitignore/Gitattributes + Docker + GitHub prep + remote + push |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Commit valuable untracked; delete broken (`market_analysis_stage.py` + test), duplicate (`sdk/knowledge/`), dead code; run new tests | PR 1 | `git ls-files \| grep -E "market_analysis_stage\|lock\.py\|daemon_manager\|llm_agent\|training\.py\|ops_surface\|demo_multi_agent"` → empty; `pytest sdk/tests/data/test_market.py sdk/tests/agents/test_analysis_agent_frame.py sdk/tests/jforex/test_config.py tests/agents/test_adaptive_retest_agent.py tests/customproject/test_templates.py -q` | `git status` shows no unresolved untracked triage paths | `git reset --hard backup/pre-cleanup` |
| 2 | Move root docs + doc_dev/, update `DEFAULT_DOC_PATH` refs, sync prompts, refresh STATE.md | PR 2 | `python -m pytest sdk/tests/test_kb.py -q`; `python3 AI/opencode/sync_prompts.py --check` → exit 0 | KB seeder resolves `DEFAULT_DOC_PATH` end-to-end | `git checkout backup/pre-cleanup -- <paths>` or full reset |
| 3 | Rewrite .gitignore/.gitattributes; move init-schema.sql + compose; README/LICENSE/SECURITY; add remote; push | PR 3 | `git ls-files \| grep doc_dev` → empty; `docker compose config`; `git ls-remote origin` shows refs | First push to empty remote after `git remote add origin` | `git remote remove origin`; local `git reset --hard backup/pre-cleanup` |

---

## Phase 1: Untracked Triage + Dead Code Deletion (PR 1 — base: feature branch)

- [ ] 1.1 Refresh backup ref (already exists from aborted first plan run): `git branch -f backup/pre-cleanup HEAD`
- [ ] 1.2 [CONSERVE] Stage valuable untracked modules and tests:
  - `git add sdk/quantlab/data/market/ sdk/quantlab/agents/adaptive_retest_agent.py sdk/quantlab/customproject/templates.py sdk/quantlab/phase4/template_registry.py sdk/quantlab/dashboard/tests/`
  - `git add sdk/tests/data/test_market.py sdk/tests/agents/test_analysis_agent_frame.py sdk/tests/jforex/test_config.py sdk/tests/contract/ tests/agents/test_adaptive_retest_agent.py tests/customproject/test_templates.py`
- [ ] 1.3 [CONSERVE] Stage valuable untracked docs/artifacts:
  - `git add PRD.md "doc_dev/" knowledge/agent-memory/ knowledge/structured/ knowledge/timeseries/ openspec/specs/ openspec/changes/archive/ openspec/changes/compiler-deploy-demo/ sdd/repo-organization-and-github-prep/`
  - NOTE: do NOT stage `doc_dev/*.Zone.Identifier` junk (delete instead, step 1.5)
- [ ] 1.4 [BROKEN/DELETE] Remove broken module and its test:
  - `rm sdk/quantlab/pipeline/stages/market_analysis_stage.py sdk/tests/pipeline/test_market_analysis_stage.py`
  - (NOT staged/committed — the audit's explicit decision is delete, overriding its ambiguous test listing)
- [ ] 1.5 [DUPLICATE/DELETE] Remove stale knowledge duplicate and untracked junk:
  - `rm -rf sdk/knowledge/`
  - `rm -f ".classes/missing.class" "doc_dev/"*.Zone.Identifier`
- [ ] 1.6 [DEAD/DELETE] `git rm` confirmed dead tracked code:
  - `git rm sdk/quantlab/phase4/lock.py sdk/quantlab/phase4/daemon_manager.py sdk/quantlab/jforex/llm_agent.py sdk/quantlab/knowledge/training.py sdk/quantlab/agents/ops_surface.py demo_multi_agent.py`
- [ ] 1.7 Remove empty dir: `rmdir sdk/quantlab/regime`
- [ ] 1.8 Commit: `git commit -m "chore: triage untracked work, delete dead and broken code"`
- [ ] 1.9 Verify (PR 1):
  - `git status --porcelain` — no unresolved untracked triage paths (docs still pending PR2 moves, but staged here)
  - `git ls-files | grep -E "market_analysis_stage|lock\.py|daemon_manager|llm_agent|training\.py|ops_surface|demo_multi_agent"` → empty
  - `test -d sdk/knowledge` → false; `test -d sdk/quantlab/regime` → false
  - Run newly committed tests: `python -m pytest sdk/tests/data/test_market.py sdk/tests/agents/test_analysis_agent_frame.py sdk/tests/jforex/test_config.py sdk/tests/contract/ tests/agents/test_adaptive_retest_agent.py tests/customproject/test_templates.py -q`

Rollback (PR 1): `git reset --hard backup/pre-cleanup`

---

## Phase 2: Doc Reorg, Reference Updates, Prompt Sync, STATE.md (PR 2 — base: PR 1 branch)

- [ ] 2.1 `mkdir -p docs/sqx-builder-config infra`
- [ ] 2.2 `git mv doc_dev/*.md docs/sqx-builder-config/` (all non-junk markdown; junk already deleted in 1.5)
- [ ] 2.3 `git mv PRD.md STATE.md exploration.md sdd_phase5f_i_spec_consolidated.md CHANGELOG.md docs/`
- [ ] 2.4 Update `DEFAULT_DOC_PATH` and all path references in `sdk/quantlab/knowledge/kb/seeder.py`, `sdk/quantlab/knowledge/kb/seeding_flow.py`, `sdk/quantlab/knowledge/kb/__init__.py`, `sdk/quantlab/cli/sq_commands.py`, `sdk/tests/test_kb.py` → `docs/sqx-builder-config/SQX Builder Config.md` (see design.md Path Reference Updates table)
- [ ] 2.5 Refresh `docs/STATE.md`: correct stale "rama main limpia" claim → real branch `feat/per-phase-subagent-delegation-pr5`, 28 commits ahead of `main`, resolved untracked state, current test summary
- [ ] 2.6 Prompt sync:
  - `python3 AI/opencode/sync_prompts.py --check` (expected exit 1 on drift — campaign preflight gap)
  - Copy live guardian prompt into repo: `cp ~/.config/opencode/prompts/quantlab/guardian.md AI/opencode/agents/guardian.md`
  - Re-sync: `python3 AI/opencode/sync_prompts.py` then `python3 AI/opencode/sync_prompts.py --check` → exit 0
- [ ] 2.7 Commit: `git commit -m "docs: reorganize under docs/, sync prompts, refresh STATE.md"`
- [ ] 2.8 Verify (PR 2):
  - `git ls-files | grep doc_dev` → empty
  - `git ls-files | grep "docs/sqx-builder-config"` shows moved files
  - `python -m pytest sdk/tests/test_kb.py -q` passes
  - `python -m pytest sdk/tests/test_kb_seed_validation.py -q` passes
  - `python3 AI/opencode/sync_prompts.py --check` → exit 0

Rollback (PR 2): `git checkout backup/pre-cleanup -- <moved-paths>` or `git reset --hard backup/pre-cleanup`

---

## Phase 3: Gitignore/Gitattributes, Docker, GitHub Prep, Remote, Push (PR 3 — base: PR 2 branch)

- [ ] 3.1 Rewrite `.gitignore`: add `*.pyc`, `__pycache__/`, `.kotlin/`, `.classes/`, `app_movil/**/build/`, `app_movil/**/.gradle/`, `*.Zone.Identifier`, `.coverage`, `notifications.jsonl`, `missing.jfx`; REMOVE stale entries `=3.0` and `_run_campaign.py`
- [ ] 3.2 Write `.gitattributes` with LFS rules (e.g. `*.pdf filter=lfs diff=lfs merge=lfs -text`, binary artifact patterns)
- [ ] 3.3 Docker: `git mv docker/init-schema.sql infra/init-schema.sql`; `rm docker/nginx.conf`; update `docker-compose.yml` (~line 87) to `${SQX_PATH}/infra/init-schema.sql` and add `SQX_PATH` env var
- [ ] 3.4 Delete `app_movil/quantlabai.zip:Zone.Identifier` (covered by `*.Zone.Identifier` ignore)
- [ ] 3.5 Create `LICENSE` (MIT) and `SECURITY.md` at repo root; keep/polish `README.md`
- [ ] 3.6 Add remote (required — `git remote -v` is currently EMPTY): `git remote add origin https://github.com/andrikonbeat/quantlabai`
- [ ] 3.7 Commit: `git commit -m "chore: finalize repo hygiene and GitHub readiness"`
- [ ] 3.8 Push (no force-push needed — empty remote, no history rewrite):
  - `git push -u origin main`
  - `git push -u origin feat/per-phase-subagent-delegation-pr5`
- [ ] 3.9 Verify (PR 3):
  - `git ls-files | grep -E "_output|demo_multi|nginx|doc_dev"` → empty
  - `docker compose config` validates
  - `git ls-remote origin refs/heads/main refs/heads/feat/per-phase-subagent-delegation-pr5` returns both SHAs
  - `git status` clean

Rollback (PR 3): `git remote remove origin` (restores pre-push state); local `git reset --hard backup/pre-cleanup`

---

## Post-Push Verification (final)

- [ ] 4.1 Run full test suite: `python -m pytest -q` (both trees)
- [ ] 4.2 Confirm `.git` size stays small: `git count-objects -vH` (pack ~3.84 MiB, no growth from binaries)
- [ ] 4.3 Delete `backup/pre-cleanup` ONLY after remote push verified successful: `git branch -D backup/pre-cleanup`

Rollback (final): `git remote remove origin`; `git reset --hard backup/pre-cleanup` (if branch not yet deleted)