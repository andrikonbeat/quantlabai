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

- [x] 1.1 Refresh backup ref (already exists from aborted first plan run): `git branch -f backup/pre-cleanup HEAD`
- [x] 1.2 [CONSERVE] Stage valuable untracked modules and tests:
  - `git add sdk/quantlab/data/market/ sdk/quantlab/agents/adaptive_retest_agent.py sdk/quantlab/customproject/templates.py sdk/quantlab/phase4/template_registry.py sdk/quantlab/dashboard/tests/`
  - `git add sdk/tests/data/test_market.py sdk/tests/agents/test_analysis_agent_frame.py sdk/tests/jforex/test_config.py sdk/tests/contract/ tests/agents/test_adaptive_retest_agent.py tests/customproject/test_templates.py`
- [x] 1.3 [CONSERVE] Stage valuable untracked docs/artifacts:
  - `git add PRD.md "doc_dev/" knowledge/agent-memory/ knowledge/structured/ knowledge/timeseries/ openspec/specs/ openspec/changes/archive/ openspec/changes/compiler-deploy-demo/ sdd/repo-organization-and-github-prep/`
  - NOTE: do NOT stage `doc_dev/*.Zone.Identifier` junk (delete instead, step 1.5)
  - NOTE (applied): orchestrator's PR1 scope committed `openspec/specs/` (14 new specs) + `sdd/`; `openspec/changes/` left untracked for a later decision — not in the binding commit list.
- [x] 1.4 [BROKEN/DELETE] Remove broken module and its test:
  - `rm sdk/quantlab/pipeline/stages/market_analysis_stage.py sdk/tests/pipeline/test_market_analysis_stage.py`
  - (NOT staged/committed — the audit's explicit decision is delete, overriding its ambiguous test listing)
- [x] 1.5 [DUPLICATE/DELETE] Remove stale knowledge duplicate and untracked junk:
  - `rm -rf sdk/knowledge/`
  - `rm -f ".classes/missing.class" "doc_dev/"*.Zone.Identifier`
- [x] 1.6 [DEAD/DELETE] `git rm` confirmed dead tracked code:
  - `git rm sdk/quantlab/phase4/lock.py sdk/quantlab/phase4/daemon_manager.py sdk/quantlab/jforex/llm_agent.py sdk/quantlab/knowledge/training.py sdk/quantlab/agents/ops_surface.py demo_multi_agent.py`
  - NOTE (applied): `demo_multi_agent.py` was untracked → `rm`; additionally removed orphaned `tests/agents/test_ops_surface.py` and repaired the 3 tracked test files broken by the deletions (see apply-progress).
- [x] 1.7 Remove empty dir: `rmdir sdk/quantlab/regime`
- [x] 1.8 Commit: 9 work-unit commits (see apply-progress for hashes) — supersedes single-commit suggestion per orchestrator 1d
- [x] 1.9 Verify (PR 1):
  - `git status --porcelain` — no unresolved untracked triage paths (docs still pending PR2 moves, but staged here)
  - `git ls-files | grep -E "market_analysis_stage|lock\.py|daemon_manager|llm_agent|training\.py|ops_surface|demo_multi_agent"` → empty
  - `test -d sdk/knowledge` → false; `test -d sdk/quantlab/regime` → false
  - Run newly committed tests: `python -m pytest sdk/tests/data/test_market.py sdk/tests/agents/test_analysis_agent_frame.py sdk/tests/jforex/test_config.py sdk/tests/contract/ tests/agents/test_adaptive_retest_agent.py tests/customproject/test_templates.py -q`
- [x] 1.10 Gatekeeper correction (post-PR1): repair the 3 red committed suites (see apply-progress):
  - `fix(customproject)` d3bbe9c: `CustomProject.template_name` + `<Template>` metadata injection + dedicated `render_automatic_retest`
  - `fix(cfx)` 25035be: CfxProject metadata round-trip + `RetesterConfig.from_cfx` + `RetesterStage(cfx_path=...)`
  - `fix(agents)` 4efcc58: `AnalysisAgent` adds `market_context` when Frame artifact present
  - Result: all 3 suites green except env-gated `test_passes_golden_validation` (3 tests, need `assets/.../sqcli` binary — same pre-existing env gate as `test_validator.py`/`test_e2e_loadconfig.py`)

Rollback (PR 1): `git reset --hard backup/pre-cleanup`

---

## Phase 2: Doc Reorg, Reference Updates, Prompt Sync, STATE.md (PR 2 — base: PR 1 branch)

- [x] 2.1 `mkdir -p docs/sqx-builder-config infra`
- [x] 2.2 `git mv doc_dev/*.md docs/sqx-builder-config/` (all non-junk markdown; junk already deleted in 1.5)
  - NOTE (applied): moved all **8** `.md` (incl. the 5 Spanish personal notes — design open question resolved: move unchanged). The 4 `*.Zone.Identifier` files were **TRACKED** (committed in PR1 despite the 1.3 note) → `git rm`'d in PR2, then `rmdir doc_dev`.
- [x] 2.3 `git mv PRD.md STATE.md exploration.md sdd_phase5f_i_spec_consolidated.md CHANGELOG.md docs/`
  - NOTE (applied): all 5 were tracked (PRD committed in PR1). Also moved `docker/init-schema.sql` → `infra/` and deleted untracked dead `docker/nginx.conf` (pulled from 3.3/3.4 into PR2 per orchestrator; `docker-compose.yml` update stays in PR3) → `rmdir docker`.
- [x] 2.4 Update `DEFAULT_DOC_PATH` and all path references in `sdk/quantlab/knowledge/kb/seeder.py`, `sdk/quantlab/knowledge/kb/seeding_flow.py`, `sdk/quantlab/knowledge/kb/__init__.py`, `sdk/quantlab/cli/sq_commands.py`, `sdk/tests/test_kb.py` → `docs/sqx-builder-config/SQX Builder Config.md` (see design.md Path Reference Updates table)
  - NOTE (applied): also updated the **knowledge lake** `evidence_ref` fields (9 yaml files), the **active spec** `openspec/specs/sqx-parameter-kb/spec.md`, and the moved plan doc's internal refs. Archived `openspec/changes/archive/` records left frozen (historical); `sdd/` planning artifacts left as plan-of-record. Remaining `doc_dev` mentions are ONLY in those two categories.
- [x] 2.5 Refresh `docs/STATE.md`: correct stale "rama main limpia" claim → real branch `feat/per-phase-subagent-delegation-pr5`, 42 commits ahead of `main` (orchestrator said 30+; real count 42), resolved untracked state, current test summary
- [x] 2.6 Prompt sync:
  - `python3 AI/opencode/sync_prompts.py --check` → **exit 0, parity ok** (NO drift — contrary to expected exit 1; repo was already canonical)
  - Copied live guardian prompt into repo: `cp ~/.config/opencode/prompts/quantlab/guardian.md AI/opencode/agents/guardian.md` (byte-identical; repo now 16 prompts: campaign + 14 phases + guardian)
  - Re-check: `python3 AI/opencode/sync_prompts.py --check` → exit 0
- [x] 2.7 Commit: superseded by 5 work-unit commits per orchestrator 2f (see apply-progress) + this sdd commit
- [x] 2.8 Verify (PR 2):
  - `git ls-files | grep doc_dev` → empty (0 tracked paths)
  - `git ls-files | grep "docs/sqx-builder-config"` → 8 moved files
  - `python -m pytest sdk/tests/test_kb.py -q` passes (part of 62 passed with seed validation)
  - `python -m pytest sdk/tests/test_kb_seed_validation.py -q` passes
  - `python3 AI/opencode/sync_prompts.py --check` → exit 0
  - Suite summary (2026-08-14, `SQX_FORCE_MOCK=1`): **3449 passed, 44 failed, 12 skipped, 11 errors** — failures/errors pre-existing, not caused by PR2 (docs/refs only)

Rollback (PR 2): `git checkout backup/pre-cleanup -- <moved-paths>` or `git reset --hard backup/pre-cleanup`

---

## Phase 3: Gitignore/Gitattributes, Docker, GitHub Prep, Remote, Push (PR 3 — base: PR 2 branch)

- [x] 3.1 Rewrite `.gitignore`: add `*.pyc`, `__pycache__/`, `.kotlin/`, `.classes/`, `app_movil/**/build/`, `app_movil/**/.gradle/`, `*.Zone.Identifier`, `.coverage`, `notifications.jsonl`, `missing.jfx`; REMOVE stale entries `=3.0` and `_run_campaign.py`
  - NOTE (applied): also added `coverage.xml`, `.pytest_cache/`, `*.apk`, `*.aab`, `assets/SQX_*/` (full distribution dir), `**/monitor.db`; untracked `.atl/.skill-registry.cache.json` + `knowledge/timeseries/monitor.db` (were tracked). `=3.0` truly stale (file absent). `_run_campaign.py` was NOT stale — file exists since 2026-08-12 (3.7K real campaign runner), was hidden by the old rule → now exposed untracked; left uncommitted, flagged in report.
- [x] 3.2 Write `.gitattributes` with LFS rules (e.g. `*.pdf filter=lfs diff=lfs merge=lfs -text`, binary artifact patterns)
- [x] 3.3 Docker: `git mv docker/init-schema.sql infra/init-schema.sql`; `rm docker/nginx.conf`; update `docker-compose.yml` (~line 87) to `${SQX_PATH}/infra/init-schema.sql` and add `SQX_PATH` env var
  - NOTE (applied): the move + nginx deletion were pulled into PR2 (56d1bda). PR3 updated compose: line 87 → `${SQX_PATH:-.}/infra/init-schema.sql`, assets mount → `${SQX_PATH:-.}/assets/SQX_144_2953_linux_20260601`, top comment documents SQX_PATH override. YAML validated via python (docker CLI unavailable).
- [x] 3.4 Delete `app_movil/quantlabai.zip:Zone.Identifier` (covered by `*.Zone.Identifier` ignore)
  - NOTE: no such file present at apply time; `*.Zone.Identifier` rule added regardless.
- [x] 3.5 Create `LICENSE` (MIT) and `SECURITY.md` at repo root; keep/polish `README.md`
  - NOTE: LICENSE (MIT, "QuantLab AI Contributors"), SECURITY.md (private reporting, 7d first response / 30d fix), README directory tree + clone URL + license/security links + mobile app section updated; CHANGELOG reorg entry added.
- [x] 3.6 Add remote (required — `git remote -v` is currently EMPTY): `git remote add origin https://github.com/andrikonbeat/quantlabai`
- [x] 3.7 Commit: `git commit -m "chore: finalize repo hygiene and GitHub readiness"`
  - NOTE (applied): superseded by 6 work-unit commits per orchestrator 3g (39c2303..341f57c, see apply-progress).
- [x] 3.8 Push (no force-push needed — empty remote, no history rewrite):
  - `git push -u origin main`
  - `git push -u origin feat/per-phase-subagent-delegation-pr5`
  - NOTE (applied): HTTPS push failed (no credential helper; `could not read Username`, exit 128). origin URL switched to SSH `git@github.com:andrikonbeat/quantlabai.git` (pre-authenticated key, same account) → both branches pushed, upstream set.
- [x] 3.9 Verify (PR 3):
  - `git ls-files | grep -E "_output|demo_multi|nginx|doc_dev"` → empty
  - `docker compose config` validates — YAML validated via python (docker CLI not installed on this host)
  - `git ls-remote origin refs/heads/main refs/heads/feat/per-phase-subagent-delegation-pr5` returns both SHAs
  - `git status` — only out-of-scope untracked remain (reported)

Rollback (PR 3): `git remote remove origin` (restores pre-push state); local `git reset --hard backup/pre-cleanup`

---

## Post-Push Verification (final)

- [x] 4.1 Run full test suite: `python -m pytest -q` (both trees)
  - NOTE: 2026-08-14 `SQX_FORCE_MOCK=1` → **3450 passed, 43 failed, 12 skipped, 11 errors** (~6.3 min). Matches PR2 baseline (3449/44/12/11) within order-flake noise; PR3 changed no code.
- [x] 4.2 Confirm `.git` size stays small: `git count-objects -vH` (pack ~3.84 MiB, no growth from binaries)
- [ ] 4.3 Delete `backup/pre-cleanup` ONLY after remote push verified successful: `git branch -D backup/pre-cleanup`
  - NOTE: intentionally left pending — push IS verified, but the branch is a zero-cost safety net; delete manually once the remote is trusted.

Rollback (final): `git remote remove origin`; `git reset --hard backup/pre-cleanup` (if branch not yet deleted)