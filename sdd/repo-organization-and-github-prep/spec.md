# Delta for Hygiene

## ADDED Requirements

### Requirement: HGN-02 Untracked triage policy

The 56 untracked paths on branch `feat/per-phase-subagent-delegation-pr5` MUST be triaged: valuable modules MUST be committed, broken/duplicate paths MUST be deleted. The valuable set is: `sdk/quantlab/data/market/`, `sdk/quantlab/agents/adaptive_retest_agent.py`, `sdk/quantlab/customproject/templates.py`, `sdk/quantlab/phase4/template_registry.py`, `sdk/quantlab/dashboard/tests/`, `sdk/tests/data/test_market.py`, `sdk/tests/agents/test_analysis_agent_frame.py`, `sdk/tests/jforex/test_config.py`, `sdk/tests/contract/`, `tests/agents/test_adaptive_retest_agent.py`, `tests/customproject/test_templates.py`, `PRD.md`, `doc_dev/` (excluding `*.Zone.Identifier`), `knowledge/` data dirs (`agent-memory/`, `structured/`, `timeseries/`), `openspec/specs/` new specs, `openspec/changes/archive/` new archives, and `sdd/repo-organization-and-github-prep/`. The broken set is: `sdk/quantlab/pipeline/stages/market_analysis_stage.py` (imports undefined `MarketAnalysisStage` from `agent_stages.py`, not in registry) and its test `sdk/tests/pipeline/test_market_analysis_stage.py` (RED tests can never pass) — both MUST be deleted, not committed. `sdk/knowledge/` (132K stale duplicate, 0 tracked, no code references) MUST be deleted.

#### Scenario: Valuable modules are committed
- GIVEN the triage
- WHEN `git ls-files` is checked
- THEN `sdk/quantlab/data/market/`, `adaptive_retest_agent.py`, `templates.py`, `template_registry.py`, and the listed test files appear

#### Scenario: Broken modules are not committed
- GIVEN the triage
- WHEN `git ls-files | grep market_analysis_stage` is checked
- THEN no paths match (both the module and its test are absent)

#### Scenario: Duplicate knowledge tree is removed
- GIVEN the triage
- WHEN `git status` and `git ls-files sdk/knowledge/` are checked
- THEN `sdk/knowledge/` no longer exists and nothing under it is tracked

**Acceptance**: all 56 untracked paths resolved (committed or deleted), no broken module tracked.

(Previously: old HGN-03 "Untracked triage committed" was removed as superseded; now reinstated with the audit's revised valuable/broken classification)

### Requirement: HGN-03 Dead-code deletion

Confirmed dead code MUST be removed from tracking: `sdk/quantlab/phase4/lock.py`, `sdk/quantlab/phase4/daemon_manager.py`, `sdk/quantlab/jforex/llm_agent.py`, `sdk/quantlab/knowledge/training.py`, `sdk/quantlab/agents/ops_surface.py`, and `demo_multi_agent.py` (tracked, unreferenced). Empty directory `sdk/quantlab/regime/` and untracked `.classes/missing.class` MUST be deleted. Deletion MUST be verified against references before removal.

#### Scenario: Dead code is untracked
- GIVEN the deletion
- WHEN `git ls-files` is checked
- THEN none of the dead-code paths appear

#### Scenario: Working tree has no dead files
- GIVEN the deletion
- WHEN `git status` is checked
- THEN `sdk/quantlab/regime/` and `.classes/missing.class` do not appear

**Acceptance**: dead code gone from tree and index.

### Requirement: HGN-10 Prompt synchronization

Repo-canonical prompts under `AI/opencode/agents/` MUST be the single source of truth. `python3 AI/opencode/sync_prompts.py --check` MUST exit 0 (no drift between repo and `~/.config/opencode/prompts/quantlab/`). The `quantlab-guardian` prompt, currently present only under `~/.config/opencode/prompts/quantlab/guardian.md`, MUST be copied into the repo. The campaign prompt MUST carry the `assert_flow_segments` preflight (live copy currently lags the repo).

#### Scenario: No prompt drift
- GIVEN the sync
- WHEN `python3 AI/opencode/sync_prompts.py --check` is run
- THEN it exits 0

#### Scenario: Guardian prompt is in the repo
- GIVEN the copy
- WHEN `AI/opencode/agents/guardian.md` is checked
- THEN it exists and matches the live `guardian.md`

**Acceptance**: `--check` passes; guardian prompt versioned.

### Requirement: HGN-11 STATE.md accuracy

`STATE.md` MUST reflect current reality or be moved/refreshed. The stale claim "rama `main` limpia" is false (branch is `feat/per-phase-subagent-delegation-pr5`, 28 commits ahead of `main`, with untracked work) and MUST be corrected. The refreshed file MUST state the real branch, commit position, resolved untracked state, and test suite summary.

#### Scenario: STATE.md is accurate
- GIVEN the refresh
- WHEN the file is read
- THEN it names the real branch, the ahead count, and the resolved untracked state

**Acceptance**: no stale or misleading claims remain in `STATE.md`.

## MODIFIED Requirements

### Requirement: HGN-01 Tracked junk removed

The system MUST `git rm` tracked junk and dead code: `demo_multi_agent.py`, `sdk/quantlab/phase4/lock.py`, `sdk/quantlab/phase4/daemon_manager.py`, `sdk/quantlab/jforex/llm_agent.py`, `sdk/quantlab/knowledge/training.py`, `sdk/quantlab/agents/ops_surface.py`. Stale `.gitignore` entries `=3.0` and `_run_campaign.py` MUST be removed (files do not exist). Empty dir `sdk/quantlab/regime/` and `.classes/missing.class` MUST be deleted.

#### Scenario: Junk absent from tracking
- GIVEN the cleanup
- WHEN `git ls-files` is checked
- THEN none of the junk paths appear

**Acceptance**: junk gone.

(Previously: listed `=5.18`, `Save location: /`, `_output/`, `build/compiled/`, `analysis/` — superseded by audit findings)

### Requirement: HGN-04 Documentation organization

All root documentation MUST be organized under `docs/`. `STATE.md` MUST be accurate (see HGN-11) or be deleted. No misleading documentation MAY remain.

#### Scenario: Documentation is organized
- GIVEN the reorganization
- WHEN the root is listed
- THEN docs appear under `docs/`, not root

**Acceptance**: no stale documentation, docs organized.

(Previously: STATE.md claims not considered against the actual branch)

### Requirement: HGN-05 .gitignore completeness

The system MUST have a complete `.gitignore` covering Python bytecode (`*.pyc`, `__pycache__/`), Android build state (`app_movil/**/build/`, `app_movil/**/.gradle/`, `.kotlin/`, `.classes/`), coverage (`.coverage`), Windows ADS (`*.Zone.Identifier`), generated artifacts (`notifications.jsonl`, `missing.jfx`). Stale entries `=3.0` and `_run_campaign.py` MUST be removed. No tracked file matching an ignore pattern MAY remain.

#### Scenario: Generated files are ignored
- GIVEN the `.gitignore`
- WHEN `git status` is checked
- THEN no generated files appear

#### Scenario: Previously tracked junk is absent
- GIVEN the cleanup
- WHEN `git ls-files` is checked
- THEN `demo_multi_agent.py` is absent

**Acceptance**: `.gitignore` complete and current; no stale entries.

(Previously: also referenced `_output/`, `sdk/_output/`, `analysis/`, `build/` — those are already untracked/ignored and no longer in scope)

### Requirement: HGN-06 Documentation reorganization

Root docs (`PRD.md`, `STATE.md`, `exploration.md`, `sdd_phase5f_i_spec_consolidated.md`, `CHANGELOG.md`) MUST move to `docs/`. Active `doc_dev/` files MUST move to `docs/sqx-builder-config/` (excluding `*.Zone.Identifier` junk). References in `seeder.py`, `seeding_flow.py`, `sq_commands.py`, `__init__.py`, and `test_kb.py` MUST be updated.

#### Scenario: Root docs are organized
- GIVEN the move
- WHEN the root is listed
- THEN no docs remain except `README.md`

#### Scenario: KB seeder finds moved config
- GIVEN `doc_dev/` moved
- WHEN the seeder runs
- THEN it loads `docs/sqx-builder-config/SQX Builder Config.md`

**Acceptance**: docs moved; KB seeder resolves the new path.

### Requirement: HGN-07 Docker and infrastructure cleanup

`docker/nginx.conf` MUST be deleted (untracked, unused). `docker/init-schema.sql` MUST move to `infra/init-schema.sql`. `docker-compose.yml` (~line 87) MUST reference the new `infra/` path and resolve SQX via `${SQX_PATH}`.

#### Scenario: Compose resolves infra schema
- GIVEN the updated compose
- WHEN parsed
- THEN `init-schema.sql` resolves via `${SQX_PATH}/infra/init-schema.sql`

**Acceptance**: compose validates; schema path correct.

### Requirement: HGN-08 app_movil/ hygiene

`app_movil/` source (112 tracked files) MUST remain tracked. Build artifacts (`app_movil/**/build/`, `app_movil/**/.gradle/`) MUST be ignored. The junk file `app_movil/quantlabai.zip:Zone.Identifier` MUST be deleted and `*.Zone.Identifier` MUST be ignored.

#### Scenario: Source tracked, builds ignored
- GIVEN the rules
- WHEN `git ls-files` is checked
- THEN sources appear but no `build/` paths appear

#### Scenario: Zone.Identifier junk gone
- GIVEN the cleanup
- WHEN `git status` is checked
- THEN no `*.Zone.Identifier` file appears

**Acceptance**: sources tracked; builds and ADS junk ignored.

### Requirement: HGN-09 GitHub readiness

The repository MUST have `README.md`, `LICENSE`, `.gitattributes`, and `SECURITY.md`. The empty remote MUST be added as `origin` (`git remote add origin https://github.com/andrikonbeat/quantlabai`) BEFORE any push. `.gitattributes` MUST configure Git LFS. The first push MUST include both `main` and the current feature branch.

#### Scenario: Repo is push-ready
- GIVEN all readiness files present and remote added
- WHEN `git push` is executed
- THEN the remote accepts

**Acceptance**: remote added; push succeeds; `git ls-remote` shows both refs.

(Previously: assumed `origin` already configured)

## REMOVED Requirements

### Requirement: HGN-02 (old) SQX binaries removed from history

(Reason: Audit found the 3.2GB SQX binaries were NEVER committed — `git log --all -- assets/` = 0 commits, `git ls-files assets` = 0, pack = 3.84 MiB. No BFG history rewrite is needed; `.git` is already 6.3MB.)
(Migration: None — requirement is obsolete; size criterion already satisfied.)

### Requirement: HGN-03 (old) Untracked triage committed

(Reason: Superseded by the revised HGN-02 triage policy with the audit's valuable/broken classification.)
(Migration: None — reinstated as HGN-02 with revised content.)

## Constraints

- MUST NOT break existing tests; run the affected test files after triage
- MUST preserve `app_movil/` source tree
- MUST preserve `sdk/quantlab/knowledge/` content and references (root knowledge lake, NOT `sdk/knowledge/`)
- MUST NOT rewrite git history
- MUST NOT push before `origin` is added