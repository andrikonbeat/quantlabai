# Archive Report: production-readiness

**Archived**: 2026-08-02
**Mode**: hybrid (openspec filesystem + Engram)
**Change**: production-readiness
**Archive status**: **INTENTIONAL-WITH-WARNINGS** — documented deferrals and carry-forward warnings explicitly waived by the orchestrator (see §Waivers). Not a clean close; all waivers recorded below.

## Summary

Production-readiness made QuantLab AI installable, testable, and deployable: console script + module entrypoint + `api` subcommand, declared deps, canonical root test tree, Docker/CI/compose repair, junk + SQX-zip removal, loud-mock + production hard-fail, env-based license guard, Knowledge-Lake-backed dashboard API, and guarded news providers. Implemented across Slice 1 (T1–T13), Slice 2 (T14–T25), and one correction batch (C1–C8, commit `8cd7769` + docs `8a11aa3`) that resolved all 8 PARTIAL S2 verify findings. Verified PASS WITH WARNINGS (human) — machine envelope `fail` is the correct routing truth (canonical command exits 1 due to 14 pre-existing out-of-scope failures).

## Final State (per Final-State Authority hierarchy)

The archive records the state of the change AT CLOSE. Authoritative sources, most authoritative first: native review authority (none exists — see §Review Gate) → persisted tasks artifact → orchestrator launch-prompt final-state facts → intermediate snapshots (`verify-report`, `apply-progress`). Final numbers below are carried from the orchestrator's close facts and the final correction-batch run (2026-08-02), not from intermediate snapshots.

- **Tasks**: 32 `[x]` (24 original T1–T25 minus T3 + 8 correction C1–C8), 1 `[ ]` (T3 `uv.lock` — documented deferral, see §Task Completion Gate).
- **Canonical suite (2026-08-02, final)**: **2641 passed / 14 failed / 3 skipped (2658 collected, 0 errors)**. The 14 failures are all pre-existing and out-of-scope: `tests/robustness/*` (12), `tests/phase5/test_pipeline_registry.py` (1), `tests/cfx/test_reader.py` (1). Zero Slice-1 regressions, zero Slice-2 regressions, zero correction-batch regressions.
- **Slice-2 compliance**: 42/42 scenarios COMPLIANT after the correction batch (per `verify-report` #697, 2026-08-02 — confirmed by launch-prompt facts 2 and 6; the 8 PARTIAL rows it originally recorded are resolved).
- **Build**: `sdk/.venv/bin/quantlab --help` exit 0 (console script stable).
- **Machine envelope**: `verdict: fail` REQUIRED and CORRECT because the canonical command exits 1 (14 pre-existing failures) — validator-enforced routing truth, not a change defect. Human verdict: **PASS WITH WARNINGS**. Report persistable; change complete.

## Task Completion Gate

Checked the persisted tasks artifact (`openspec/changes/production-readiness/tasks.md`) before any sync: **32 `[x]`, 1 `[ ]` (T3)**.

- T3 (`uv lock` → commit `sdk/uv.lock`, CLI-04) remains unchecked **by design**: no `uv` binary available in the environment; deps installed and verified via `pip install -e "sdk[dev]"` instead. Documented in tasks.md, apply-progress.md (S1 batch, `⚠️ DEFERRED`), STATE.md, and verify-report WARNING-7.
- **Exceptional reconciliation**: the orchestrator's launch prompt explicitly instructs archiving with T3 deferred and waives it as a documented warning. This is a genuine deferral of a generated artifact, not a stale checkbox for completed work — recorded per the skill's intentional-with-warnings path. No other unchecked tasks exist.

## Review Gate

**`disabled/unmanaged`** — no native review receipt artifacts exist for this change (no `review/` directory in the change folder, no review transaction/ledger/receipt topics in Engram). No `review start` was ever issued for this change, so no terminal receipt can exist; demanding one would be a deadlock. The kill switch is off and no review governs this change. Verification authority therefore rests on the persisted verify-report (#697) plus orchestrator close facts.

## Specs Synced

The change's delta spec is a single flat `spec.md` (9 domain sections, per this repo's convention). Each section was synced to its domain's main spec:

| Domain | Action | Details |
|--------|--------|---------|
| cli-entrypoint | **Created** | `openspec/specs/cli-entrypoint/spec.md` — CLI-01..CLI-04 (4 requirements, 8 scenarios) |
| packaging-deps | **Created** | `openspec/specs/packaging-deps/spec.md` — DEP-01 (1 requirement, 2 scenarios) |
| test-suite | **Created** | `openspec/specs/test-suite/spec.md` — TST-01..TST-04 (4 requirements, 6 scenarios) |
| ci-docker | **Created** | `openspec/specs/ci-docker/spec.md` — CID-01..CID-04 (4 requirements, 4 scenarios) |
| dashboard-api | **Updated** | Replaced 6 MODIFIED requirements in place (Flask port binding, campaigns list, campaign detail, pipeline, stats, reports); preserved `GET /api/health` + error envelope unchanged; appended ADDED DSH-01, DSH-02 |
| sqx-cli-wrapper | **Updated** | Appended ADDED MOK-01, MOK-02 (2 requirements, 4 scenarios); all 7 pre-existing requirements preserved untouched |
| license-manager | **Updated** | Replaced MODIFIED "Startup Guard" (now env-gated pre-flight, 4 scenarios); appended ADDED LIC-02; License Detection + License Activation preserved |
| llm-research | **Updated** | Replaced MODIFIED "Prompt Templates" (news template consumes fetched articles); appended ADDED NWS-01, NWS-02, NWS-03; all 4 pre-existing requirements preserved |
| hygiene | **Created** | `openspec/specs/hygiene/spec.md` — HGN-01..HGN-04 (4 requirements, 6 scenarios) |

Merge discipline: requirements not mentioned in the delta were preserved verbatim; MODIFIED blocks replaced full requirement text per the OpenSpec convention (delta carries the complete updated requirement incl. unchanged scenarios); no destructive removals occurred (no REMOVED/RENAMED sections in the delta).

## Source of Truth Updated

The following main specs now reflect the new behavior:
- `openspec/specs/cli-entrypoint/spec.md`
- `openspec/specs/packaging-deps/spec.md`
- `openspec/specs/test-suite/spec.md`
- `openspec/specs/ci-docker/spec.md`
- `openspec/specs/dashboard-api/spec.md`
- `openspec/specs/sqx-cli-wrapper/spec.md`
- `openspec/specs/license-manager/spec.md`
- `openspec/specs/llm-research/spec.md`
- `openspec/specs/hygiene/spec.md`

## Archive Contents

- `proposal.md` ✅
- `explore.md` ✅
- `spec.md` ✅ (flat delta spec, 9 domain sections — repo convention)
- `design.md` ✅
- `tasks.md` ✅ (32/32 complete for close; 1 documented deferral T3)
- `apply-progress.md` ✅ (S1, S2, S2b, correction-batch batches)
- `verify-report.md` ✅ (PASS WITH WARNINGS / envelope `fail`)
- `archive-report.md` ✅ (this file)

No `state.yaml` exists for this change (repo convention: phase artifacts + archive folder move serve as cycle state; consistent with prior archives). No `review/` artifacts exist (see §Review Gate).

## Verification Summary

- **Verdict**: PASS WITH WARNINGS (human) / `fail` (machine envelope — correct routing truth, see §Final State).
- **CRITICAL findings**: 0 → archive not blocked.
- **Requirements**: 33/33 · **Scenarios**: 65/65 accounted (60 COMPLIANT, 5 PARTIAL — all five PARTIAL are Slice-1 manual-verify/deferral carry-forwards waived below; 0 FAILING, 0 UNTESTED).
- **Canonical suite**: 2641 passed / 14 failed / 3 skipped (2658 collected).
- **Focused suites**: dashboard 543 passed (incl. correction), guards 21 passed, news+news-agent 32 passed, PID lifecycle 6 passed.
- **Coverage**: not configured (threshold 0) — not a gate.

## Waivers (explicitly recorded — waived by the orchestrator, NOT blockers)

1. **T3 `uv.lock` deferral** — uv binary unavailable; `pip install -e "sdk[dev]"` + console-script execution verified instead (CLI-04 acceptance satisfied via pip path). Task left `[ ]` in the archived tasks.md by design (documented deferral, not stale completion).
2. **Docker build / `docker compose config` manual-verify** (CID-03/CID-04) — no docker daemon/binary in environment; Dockerfile statically verified, compose YAML validated via `yaml.safe_load`.
3. **CI test-job suite-scope gap** (TST-01 WARNING-6a) — CI runs from `./sdk`, collecting only sdk tests (1381) vs the canonical root 2658; docs-only, unchanged.
4. **CI lacks `SQX_FORCE_MOCK=1`** (WARNING-6b) — `test_run_writes_context_artifacts` hangs against the real sqcli daemon without it; docs-only, unchanged.
5. **Root `.venv` stale** (WARNING-6c) — canonical env is `sdk/.venv`; documented in STATE.md; docs-only, unchanged.

## Known Non-Blocking Conditions (recorded, not waived as clean)

- **Flaky test (pre-existing, NOT a regression, do not block on it)**: `sdk/tests/test_pr3_pipeline_wiring.py::TestE2EAnalysisReviewerWiring::test_mock_campaign_roundtrip_analysis_to_reviewer` — unseeded random in `mock_sqx_server._generate_mock_exports`; passes ~2/3 runs; git diff for both files EMPTY across the whole change (`9aa27ea..8cd7769`); provably off-path. PASSED in the final canonical run.
- **14 pre-existing out-of-scope failures** — `tests/robustness/*` (12), `tests/phase5/test_pipeline_registry.py` (1), `tests/cfx/test_reader.py` (1). Present in baseline; zero change-slice regressions. Causes not re-derived here; recorded as pre-existing per verify-report #697.
- **Machine envelope `fail`** — correct and expected (canonical exit 1); the report is persistable and the change complete.
- **Untracked pre-existing files (out of scope, untouched, not committed)**: `sdk/tests/dashboard/*` static-asset tests, `test_mock_sqx_server.py`, `test_project_builder.py`, `tests/cli/__init__.py`, `tests/sqx/__init__.py`, `doc_dev/Quant AI Lab, Quest.md`, `knowledge/index.yaml`, `.atl/*` (registry cache). Note: the canonical run collects some of these, so a clean PR checkout collects fewer tests — pre-existing repo hygiene, out of change scope (per verify-report SUGGESTION-1/2, still open).

## Engram Observation IDs (traceability)

| Artifact | Observation ID |
|----------|---------------|
| explore | 689 |
| proposal | 690 |
| spec | 692 |
| design | 693 |
| tasks | 694 |
| apply-progress (S1+S2+correction record) | 696 |
| verify-report | 697 |
| review transaction/ledger/receipt | none (no native review) |
| archive-report | this archive (saved via mem_save, topic_key `sdd/production-readiness/archive-report`) |

## SDD Cycle Complete

The change has been fully planned, implemented, verified, corrected, and archived. Delta spec merged into 9 domain main specs (5 created, 4 updated); change folder moved to `openspec/changes/archive/2026-08-02-production-readiness/`. Ready for PR creation (PR 1 = Slice 1, PR 2 = Slice 2 + correction) or the next change.
