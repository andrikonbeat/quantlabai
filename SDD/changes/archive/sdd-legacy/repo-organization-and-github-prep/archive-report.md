# Archive Report — repo-organization-and-github-prep

**Archived**: 2026-08-14
**Mode**: hybrid (openspec filesystem + Engram)
**Final verdict**: PASS (verify-time `fail` superseded — sole blocker HGN-08 resolved and pushed)
**Requirements compliance**: 11/11 (verify-time 9/11; HGN-08 + HGN-11 closed at archive)
**Scenario compliance**: 18/18 (verify-time 16/18; the 2 open scenarios closed at archive)
**Tasks**: 30/30 complete
**Blockers at close**: 0
**Evidence revision**: sha256 of commit `fe49a6f` = `sha256:79d58a6f839030b4f75bd7315e7e83b77f4f22f25a39c2333a4433f50cb927fe`

## Final-State Authority

This archive report records the state of the change **AT CLOSE**, not at intermediate snapshots. Sources ranked by authority:

1. **Native review authority**: `reviewGate` structurally absent — no review artifacts exist for this candidate (kill switch off; receipt-driven development does not exist for this change). Archive proceeds under ordinary repository policy.
2. **Persisted tasks artifact** (`tasks.md`): 30/30 implementation tasks checked. Task 4.3 (backup branch deletion) was reconciled at archive time: orchestrator explicitly instructed the deletion, push is verified (`git ls-remote origin` shows `main` + `feat/per-phase-subagent-delegation-pr5` both at `fe49a6f`), and branch `769a3d4` is fully contained in HEAD history (`git merge-base --is-ancestor` = yes).
3. **Explicit final-state facts from orchestrator launch prompt**: 3 PRs applied + `_run_campaign.py` runner (`dbdc70a`) + concurrent session's `ai/` rename and external SQX install layout (through `fe49a6f`); HGN-08 blocker resolved on origin (deleted in `4aa8551`, pushed via `fe49a6f`).
4. **Intermediate snapshots** (lowest rank): `verify-report` (Engram #945, file copy) recorded `verdict: fail` / 9/11 requirements at verification time (HEAD `dbdc70a`). `apply-progress` was not present in the archived artifact set; final-state facts outrank all snapshot claims.

**Contradiction recorded (not resolved silently)**: the launch prompt stated the STATE.md stale claim was "now refreshed in fe49a6f working tree". Repository evidence contradicts this: `fe49a6f` only appended SQX config lines to `docs/STATE.md`; line 5 still claimed "42 commits por delante de main / main congelado" (false — `origin/main` == `origin/feat/per-phase-subagent-delegation-pr5` == `fe49a6f`). Per HGN-11's own acceptance ("no stale or misleading claims remain in STATE.md"), the one-line refresh was applied at archive time (2026-08-14) and is included in the archive commit. HGN-11 is recorded as MET on that basis.

## Change Summary

**Change**: repo-organization-and-github-prep
**Commits (stacked, PR chains to `main` + `feat/per-phase-subagent-delegation-pr5`)**:
- PR1 (untracked triage + dead-code deletion): 9 work-unit commits, `3ff835e`…`eabc2ee` era, incl. gatekeeper corrections `d3bbe9c`, `25035be`, `4efcc58`
- PR2 (doc reorg + refs + prompt sync + STATE.md): 5 work-unit commits, incl. `45345da`, `f3c10c9`, `76b05d8`
- PR3 (gitignore/gitattributes/docker/README/LICENSE/SECURITY + remote + push): 6 work-unit commits, `39c2303`…`341f57c`
- `dbdc70a` feat(campaign): real SQX campaign runner entry point `_run_campaign.py`
- Concurrent session (post-verify): `4aa8551` (archive legacy SDD + delete tracked Zone.Identifier + clean duplicated artifacts), `aeb8ebd` (loose docs → topical folders), `c9e6bdb` + `b85ae69` (rename `AI/` → `ai/`), `fe49a6f` (finalize `ai/` rename refs + external SQX install layout)

**Concurrent-session note**: the `ai/` rename (`AI/opencode` → `ai/opencode`, refs updated in tests/configs) and the external SQX install layout (`SQX_INSTALL_PATH="$HOME/Proyectos/SQX_144_2953_linux_20260601"` env, `sdk/pyproject.toml` adjustments) are part of the final evidence revision `fe49a6f` and are included in this archive's scope.

## Requirements (11/11 MET at close)

| Req | Title | Verify-time | Close | Evidence at close |
|-----|-------|-------------|-------|-------------------|
| HGN-01 | Tracked junk removed | ✅ | ✅ | `git ls-files`: all 6 junk paths + `regime/` absent |
| HGN-02 | Untracked triage policy | ✅ | ✅ | valuable set tracked; `market_analysis_stage` + test absent; `sdk/knowledge/` gone |
| HGN-03 | Dead-code deletion | ✅ | ✅ | all 6 dead paths absent from index |
| HGN-04 | Documentation organization | ✅ | ✅ | root docs under `docs/` |
| HGN-05 | .gitignore completeness | ✅ | ✅ | all patterns ignored; stale entries removed; `_run_campaign.py` tracked (`dbdc70a`) |
| HGN-06 | Documentation reorganization | ✅ | ✅ | `doc_dev/` → `docs/sqx-builder-config/`; KB seeder 32 passed |
| HGN-07 | Docker/infra cleanup | ✅ | ✅ | compose `${SQX_PATH:-.}/infra/init-schema.sql`; nginx.conf gone |
| HGN-08 | app_movil/ hygiene | ❌ (blocker) | ✅ | `app_movil/quantlabai.zip:Zone.Identifier` deleted in `4aa8551`, pushed via `fe49a6f`; verified absent from index, `ls-tree HEAD`, disk, and `ls-remote origin` |
| HGN-09 | GitHub readiness | ✅ | ✅ | README/LICENSE/SECURITY/.gitattributes; `origin` added (SSH); `ls-remote` shows both refs at `fe49a6f` |
| HGN-10 | Prompt synchronization | ✅ | ✅ | `sync_prompts.py --check` exit 0; 16 prompts incl. guardian in repo |
| HGN-11 | STATE.md accuracy | ⚠️ (warning) | ✅ | one-line refresh applied at archive (see contradiction above) |

## Scenarios (18/18 MET at close)

All 18 delta scenarios compliant. The 2 open at verify time:
- HGN-08 "Zone.Identifier junk gone": `git ls-files | grep -i zone` → empty; `git ls-tree HEAD` → none; file absent on disk; `ls-remote origin` → both refs at `fe49a6f` (deletion pushed).
- HGN-11 "STATE.md is accurate": line 5 now reads "Rama: `feat/per-phase-subagent-delegation-pr5` — sincronizada con `origin/main` (ambas en `fe49a6f` tras el push a GitHub, 2026-08-14)".

## Verification Evidence (Final)

| Metric | Value |
|--------|-------|
| Verify-time verdict | `fail` (1 CRITICAL: HGN-08) — superseded, blocker resolved + pushed |
| Targeted new suites (final) | test_market 7p · test_analysis_agent_frame 3p · test_config 4p · adaptive_retest 6p · test_templates 67p (3 env-gated golden excluded) · contract 4p |
| KB seeder (HGN-06) | 32 passed |
| Full suite baseline (unchanged, pre-existing) | 3449 passed / 44 failed / 12 skipped / 11 errors — env-gated (missing `sqcli` binary) + pre-existing campaign-orchestrator errors, NOT blockers |
| Build | `compileall` exit 0 (verify-time) |
| git pack | 3.84 MiB; no SQX binaries tracked (`git ls-files | grep -c SQX_144` = 0) |

Remaining failures are environment-gated (`sqcli` binary absent) and pre-existing suite debt — documented in `verify-report`, unchanged by PR1–PR3 (docs/config/infra only).

## Spec Sync

**No main-spec merge performed.** This is a **legacy change** (archived under `sdd-legacy/`, flat `spec.md` delta, no `specs/{domain}/` delta layout). The `sdd-archive` spec-sync step targets standard OpenSpec delta files (`openspec/changes/{name}/specs/`), which this change does not have. The legacy delta was archived as-is per the concurrent session's archive (`4aa8551`).

**Flag**: `openspec/specs/hygiene/spec.md` (main spec, 2.1K) retains its pre-change content (superseded HGN-01…HGN-04: `=5.18`, installer skeleton, SQX zip removal). It was NOT updated by this change. If the modern spec store should reflect HGN-01…HGN-11, a follow-up sync is recommended — out of scope for this legacy archive.

## Artifacts Archived

- `proposal.md` ✅
- `exploration.md` ✅
- `spec.md` ✅ (delta, HGN-01…HGN-11)
- `design.md` ✅
- `tasks.md` ✅ (30/30 complete; 4.3 reconciled at archive)
- `verify-report.md` ✅ (committed at archive — was untracked)
- `archive-report.md` ✅ (this file)

## Engram Observation IDs Read

| Artifact | Observation ID |
|----------|---------------|
| verify-report | #945 (full content retrieved) |
| concurrency pause note (status) | #946 (full content retrieved) |

## Archive Location

`openspec/changes/archive/sdd-legacy/repo-organization-and-github-prep/`

## SDD Cycle Status

**COMPLETE** — planned, implemented (3 PRs + runner + concurrent-session work), verified, blocker resolved and pushed, archived. Legacy change; archived under `sdd-legacy/` with the flat artifact set. SDD cycle formally closed.
