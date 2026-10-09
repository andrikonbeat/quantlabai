# Archive Report: full-campaign-flow

**Archived**: 2026-08-06
**Mode**: openspec filesystem + Engram archive report (hybrid persistence; this repo's convention)
**Change**: full-campaign-flow
**Archive status**: **CLEAN** — all 26 tasks complete, verification PASS, zero candidate-caused regressions. Delivery gate `disabled/unmanaged` by explicit maintainer decision (recorded below, not a waiver of a clean close).

## Summary

full-campaign-flow completed the QuantLab lifecycle: idea → SQX backtest → robust portfolio → compiled JForex strategy → demo deploy → archive → live-ops with a Guardian watching the demo account. Six chained PRs (stacked-to-main) delivered: custom-project generator (REQ-22..25), unified execution substrate (REQ-26..28, 42), compiler pipeline + `.jfx` routing (REQ-29..30, 39), demo deploy + human gates (REQ-31..32, 38), archive + Guardian feedback (REQ-33..34, 40..41), and mobile + orchestration (REQ-35..36, 01-M, 37, 43..44). HEAD `f1b91ec`; all 26 tasks `[x]`; verification PASS (24/24 requirements, 50/50 scenarios, 253 focused tests passed, exit 0).

## Final State (per Final-State Authority hierarchy)

Authoritative sources, most authoritative first: native review authority (none exists — see §Review Gate) → persisted tasks artifact → orchestrator launch-prompt final-state facts → intermediate snapshots (`verify-report` #745, `apply-progress` #731). Final numbers below are carried from the launch prompt's close facts and the persisted verify-report, not from intermediate snapshots.

- **Tasks**: **26/26 `[x]`**, 0 unchecked (verified in the archived `tasks.md` at close: `grep -c "\- \[ \]"` → 0).
- **Verification (final, per verify-report #745, 2026-08-06)**: **PASS** — `schema: gentle-ai.verify-result/v1`, `verdict: pass`, `blockers: 0`, `critical_findings: 0`, `requirements: 24/24`, `scenarios: 50/50`. Envelope validated: `valid: true`.
- **Focused change-coverage suites**: **253 passed / 0 failed / 4 skipped, exit 0** (`SQX_FORCE_MOCK=1 pytest tests/customproject/ tests/substrate/ tests/compiler/ tests/demo_deploy/ tests/gates/ tests/campaign_archive/ tests/guardian/ tests/pipeline/stages/ tests/campaign/ tests/agents/test_ops_surface.py -q`).
- **Build**: `python3 -m compileall -q quantlab` exit 0; full-package import check OK (ruff/mypy unavailable in environment — see §Warnings to Track).
- **Full suite (regression sweep)**: 2571 passed / 16 failed / 7 skipped / 11 errors, exit 1 (run 2: 17 failed + 11 errors, ±1 = documented flaky e2e). **All 28 failures classified PRE-EXISTING** per the four documented families — **zero regressions attributable to the change**:
  - 12 × robustness `KnowledgeStore._circuit_breaker` (`tests/robustness/*`)
  - 14 × phase4 cross-file interference (`TestCampaignOrchestrator`/`TestRunCampaignFunction`; pass in isolation)
  - 1 × cfx fixture `NQ_MULTI_TIMEFRAME.cfx` missing
  - 1 × flaky e2e `test_mock_campaign_roundtrip_analysis_to_reviewer` (intermittent, absent in one of two runs)

## Task Completion Gate

Checked the persisted tasks artifact (`openspec/changes/full-campaign-flow/tasks.md`) before any spec sync: **26 `[x]`, 0 `[ ]`**. No stale checkboxes; no exceptional reconciliation required. The one known TDD inversion (substrate task 2.5 `execute_chain`, test-after-code) is documented in apply-progress §PR-2 and its chained tests pass — completion is not in dispute.

## Review Gate

**`delivery: "disabled/unmanaged"`** — `gentle-ai review validate --gate post-apply` reports `result: invalidated`, `allowed: false`, `delivery: disabled/unmanaged`. The maintainer's global kill switch is off (`gentle-ai review mode disable`) and the native SDD dispatcher remains blocked on a stale escalated `resolve-review` authority carrying foreign OpenSpec paths, which the maintainer deliberately declined to repair. **No approved receipt exists and one MUST NOT be fabricated.** Per the archive contract, `reviewGate.delivery: disabled/unmanaged` while the kill switch is off satisfies archive delivery requirements — the native gate would refuse to produce a receipt, so demanding one is a deadlock, not a safeguard. No review transaction/ledger/receipt artifacts were read or modified; no review authority was touched, started, advanced, or repaired. The maintainer's decision is final.

## Specs Synced

The change's delta set = 7 new-capability full specs (REQ-22..36, already committed as canonical main specs in `a8d7b80`/earlier) + 8 modified-capability delta specs under `openspec/changes/full-campaign-flow/specs/`. This archive merged the 8 delta specs into their domain main specs:

| Domain | Action | Details |
|--------|--------|---------|
| campaign-orchestration → `campaign-orchestrator` | **Updated** | Replaced MODIFIED REQ-01 ("Campaign Lifecycle" → "Orchestrated Campaign Loop (REQ-01)", 14-phase loop, 2 scenarios); appended ADDED REQ-37 (Flow-Integrity Invariant, 2 scenarios). 4 pre-existing requirements preserved verbatim |
| human-gates | **Created** | `openspec/specs/human-gates/spec.md` — REQ-38 (Demo-Flow Human Gates, 4 scenarios). No main spec existed; delta promoted to full spec in house format |
| jforex-deploy | **Updated** | Appended ADDED REQ-39 (Compiled Artifact Deployment, 2 scenarios); 5 pre-existing requirements preserved |
| meta-guardian | **Updated** | Appended ADDED REQ-40 (Live Account Feed, 2 scenarios); 5 pre-existing requirements preserved |
| autonomous-monitor | **Updated** | Appended ADDED REQ-41 (Live Feed and Feedback Wiring, 2 scenarios); 9 pre-existing requirements preserved |
| campaign-monitor | **Updated** | Appended ADDED REQ-42 (Substrate-Backed Event Detection, 2 scenarios); 6 pre-existing requirements preserved |
| retester-automation | **Updated** | Appended ADDED REQ-43 (Chained Retest Task, 2 scenarios); 4 pre-existing requirements preserved |
| optimizer-automation | **Updated** | Appended ADDED REQ-44 (Chained Optimize Task, 2 scenarios); 5 pre-existing requirements preserved |

Merge discipline: requirements not mentioned in the deltas preserved verbatim; MODIFIED REQ-01 replaced its full requirement block per the OpenSpec convention (the delta carries the complete updated requirement; its 3 legacy scenarios described the pre-change 8-phase behavior and are superseded by the delta's final scenario set). No REMOVED/RENAMED sections existed; no destructive removals occurred. Scenario text preserved verbatim from the deltas so the verify-report's 50/50 scenario→test mapping stays traceable. The `config.yaml` `rules.archive` warning rule was honored: the only replace (REQ-01) is a specified MODIFIED per the delta, not a destructive removal — noted here for the record.

**config.yaml registry**: `openspec/config.yaml` contains **no change registry** (verified: git history shows config.yaml modified only by 3 setup commits, never by an archive; prior archives track closure via folder move + `archive-report.md`). No registry schema exists to update, so none was fabricated. Change tracking continues the repo convention: folder move + this report.

## Source of Truth Updated

- `openspec/specs/campaign-orchestrator/spec.md` (REQ-01, REQ-37)
- `openspec/specs/human-gates/spec.md` (REQ-38 — created)
- `openspec/specs/jforex-deploy/spec.md` (REQ-39)
- `openspec/specs/meta-guardian/spec.md` (REQ-40)
- `openspec/specs/autonomous-monitor/spec.md` (REQ-41)
- `openspec/specs/campaign-monitor/spec.md` (REQ-42)
- `openspec/specs/retester-automation/spec.md` (REQ-43)
- `openspec/specs/optimizer-automation/spec.md` (REQ-44)

(REQ-22..36 already canonical in `openspec/specs/{custom-project-generator,execution-substrate,compiler-pipeline,demo-deploy,campaign-archive,guardian-feedback,mobile-notifications}/spec.md` per commit `a8d7b80`.) All 24 requirements are now in the canonical spec set.

## Archive Contents

`openspec/changes/archive/2026-08-06-full-campaign-flow/`

- `proposal.md` ✅
- `spec.md` ✅ (flat aggregate delta, 15 domain sections)
- `specs/{campaign-orchestration,human-gates,jforex-deploy,meta-guardian,autonomous-monitor,campaign-monitor,retester-automation,optimizer-automation}/spec.md` ✅ (8 delta specs)
- `design.md` ✅
- `tasks.md` ✅ (26/26 `[x]`)
- `apply-progress.md` ✅ (PR-1..6, cumulative)
- `archive-report.md` ✅ (this file)

No `state.yaml` exists (repo convention: phase artifacts + archive move serve as cycle state). No `review/` artifacts exist (see §Review Gate).

## Verification Summary

- **Verdict**: PASS (machine envelope `valid: true`, `verdict: pass`).
- **CRITICAL findings**: 0 → archive not blocked.
- **Requirements**: 24/24 · **Scenarios**: 50/50, all COMPLIANT with passing runtime tests.
- **Focused suites**: 253 passed / 4 skipped, exit 0.
- **Full suite**: 28 pre-existing failures classified (4 families), zero regressions.
- **Coverage**: not configured (threshold 0) — not a gate.

## Known Open Questions — status at close

The three questions deferred at implementation time, resolved or carried forward as documented:

1. **CFX dialect `<Settings>` block compatibility for generated projects** — PARTIALLY RESOLVED. PR-1 validated generated archives structurally against the SQX 144/2953 sample goldens (REQ-24, `assets/SQX_144_2953_linux_20260601/`), with `RawXmlSection` as the documented workaround for the simplified `<Settings>` dialect (design §Open Questions). The remaining gap: the "Generated CFX accepted by real SQX" scenario is verified via mock sqcli probe + structural golden validation; the live-sqcli `loadconfig` E2E (`tests/customproject/test_e2e_loadconfig.py`) is **gated on a real SQX installation** (verify-report WARNING-4). **Follow-up**: run `test_e2e_loadconfig.py` against a live SQX install to close empirical acceptance.
2. **DEMO loop behavior for `demo-deploy` / demo window enforcement (REQ-31)** — RESOLVED BY IMPLEMENTATION. `phase4/demo_deploy.py` enforces the 14-business-day window as a software deadline (`DemoWindow`, `add_business_days` weekend-safe arithmetic, `reminder_at` 2 business days pre-expiry, `status()` ACTIVE/REMINDER_DUE/EXPIRED); EXPIRED blocks deployment returning `BLOCKED_EXPIRED` with `pending_gate=HUMAN_APPROVE_DEMO`, never invoking the deploy backend (fail-closed, apply-progress §PR-4). Per the exploration note and proposal scope, this is campaign-validity enforcement, not a Dukascopy renewal mechanism; semi-manual renewal reminder + human gate is the designed renewal path (out of scope: renewal automation).
3. **JDK requirement and fail-closed behavior for the compiler pipeline (REQ-29/REQ-30)** — RESOLVED BY IMPLEMENTATION. Canonical env var is `QUANTLAB_JDK_HOME` (design AD-5; no `JDK_HOME`/`JAVA_HOME` fallback — the lone `JDK_HOME` mention in design text was resolved to `QUANTLAB_JDK_HOME` at apply time). Missing/non-executable JDK raises `CompilerConfigError` before javac runs; no partial `.jfx` is produced (REQ-29 s2). The environment has no JDK, so all tests use a fake-JDK subprocess harness. **Follow-up**: real external JDK (Java 25-compatible) verification at first live deploy.
4. **`.jfx` packaging layout (design open question)** — JAR-with-classes ZIP chosen per REQ-29 wording ("package compiled classes into a .jfx archive"); SQX-native layout verification pending JForex 4 (apply-progress §PR-3 deviation). **Follow-up** (not blocking): confirm layout against JForex 4 before live demo.
5. **Live account feed transport (design open question)** — live JCloud deploy remains a local simulation (no JCloud API client in the SDK); feed is equity-only (`EquityPoint`); positions/costs are future extensions (`FeedbackSignals.cost` defaults to 0.0) (apply-progress §PR-4/§PR-5 deviations). **Follow-up**: JCloud API transport + positions/costs feed before real demo monitoring.

## Warnings to Track (verification WARNINGs, carry-forward)

1. **Review delivery gate `disabled/unmanaged`** — maintainer decision; the change closes without an approved receipt by design (see §Review Gate). Re-enabling review would revalidate from current state.
2. **REQ-24 live SQX E2E gated** — real-sqcli `loadconfig` acceptance pending a live SQX installation; structural golden validation + mock probe pass.
3. **ruff / mypy not runnable in this environment** — CI lint gate (`ruff check .`, `ruff format --check .`, `mypy quantlab --strict`) not executed here; `compileall` + import integrity substituted. CI must run the lint gate before merge.
4. **Full-suite exit 1** — 28 pre-existing failures in 4 documented families, 1:1 mapped, zero change-caused; tracked for future remediation, not this change.

## Suggestions Carried Forward (non-blocking)

1. `GateDecision.is_approved()` returns `True` for `FALLBACK` — latent quirk; future consumers must gate on `action == APPROVE` (as PR-5 did). Flagged for the notifier/orchestration consumers.
2. `portfolio_cfx` intentionally not published into `ctx.artifacts` by `PortfolioStage` (compile phase publishes `.jfx` later).
3. Repo hygiene (pre-existing, out of scope): `.atl/skill-registry*` modified and `knowledge/index.yaml` + `knowledge/timeseries/` untracked in the working tree at close; do not stash `knowledge/` when running the full suite (stash/pop collision documented in apply-progress §PR-6).

## Engram Observation IDs (traceability)

| Artifact | Observation ID |
|----------|---------------|
| exploration | 723 |
| proposal | 724 |
| spec | 725 |
| design | 727 |
| tasks | 729 |
| apply-progress (PR-1..6 cumulative) | 731 |
| verify-report | 745 |
| review transaction/ledger/receipt | none (delivery `disabled/unmanaged`; no artifacts exist, none fabricated) |
| archive-report | this archive (saved via mem_save, topic_key `sdd/full-campaign-flow/archive-report`) |

## Contradictions / Source Disagreements

None requiring adjudication. One noted discrepancy, attributed rather than resolved silently: verify-report #745 (2026-08-06, verification time) records the working tree as "2 modified skill-registry cache files outside change scope, `.atl/`"; the launch prompt states "working tree clean". At archive time the tree holds `.atl/skill-registry*` modifications + untracked `knowledge/` — consistent with the verify-report's snapshot and the pre-existing repo-hygiene family, all outside change scope. No change-scope file was left uncommitted.

## SDD Cycle Complete

The change has been fully planned, implemented, verified, and archived. Delta specs merged into 8 domain main specs (1 created, 7 updated); change folder moved to `openspec/changes/archive/2026-08-06-full-campaign-flow/`. Ready for commit + PR of the archive (`openspec/specs/*` updates + archive move) or the next change.
