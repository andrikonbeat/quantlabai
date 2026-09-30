# Apply Progress: CrossChecks Full Parameter Catalog

## Status

- Phase 1 (KB schema): ✅ complete — 10 YAML files extended with `xml_path`, `element_name`, `type`, `default`, `range`
- Phase 2 (SDK models): ✅ complete — `WhatIfConfig` + `MonteCarloRetest.methods` typed models, dual-output `summary()`
- Phase 3 (Builder mapping + version drift): ✅ complete
- Phase 4 (Testing + verification): ✅ complete — 169 passed (focused), full suite baseline maintained
- Phase 5 (Cleanup): ✅ complete — docstrings updated, no scaffolding, design alignment verified

## PR3 Work Units Completed (this session)

| Task | Evidence |
|------|----------|
| 3.1 RED test | `test_wf_acceptance_threshold_pct` in `tests/phase4/test_project_builder.py` (asserts `<Conditions thresholdPct="90">`) |
| 3.2 GREEN map | 114 entries in `_BUILD_CONFIG_MAP` in `sdk/quantlab/sqx/project_builder.py` (exceeds ~80+ target), plus `update(...)` with crosscheck-scoped entries |
| 3.3 Helper | `_apply_acceptance_settings()` addresses a leaf by tab scope, never document-wide; missing scope preserves XML + logs |
| 3.4 RED test | `invalidate_on_version_drift` tests in `tests/knowledge/test_crosschecks_schema.py` (lines 334–373): drift to `needs_review`, `blocked=False` |
| 3.5 GREEN | `invalidate_on_version_drift()` in `sdk/quantlab/knowledge/kb/store.py` — warns, never blocks |
| 4.2 Integration | `BuildConfig(wf_acceptance_threshold_pct=...)` → `<Conditions thresholdPct="...">` ✅ |
| 4.3 Round-trip | `test_whatif_method_params_roundtrip` + `test_mc_methods_survive_full_roundtrip` in `tests/cfx/test_crosschecks_models.py` ✅ |
| 4.4 Suite | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/phase4/test_project_builder.py tests/cfx/test_crosschecks_models.py tests/knowledge/test_crosschecks_schema.py sdk/tests/test_kb.py --tb=short` → **169 passed, 1 warning** |

## Verification Results

- Focused PR3 run: 124 passed (`project_builder` + `crosschecks_models`)
- Extended PR3 run (incl. KB schema + store): 169 passed
- Evidence tests prove mappings hit real XML: scopes resolve in `default-project.sqx-template`, leaves match inside their scope; `so_use` verified against real saved config `DJ CFD H1.cfx`

## Rollback Boundary

- PR3: revert `sdk/quantlab/sqx/project_builder.py` map entries + `_apply_acceptance_settings` helper; `BuildConfig` fields remain
- No commits created — all changes in working tree (direct route)

---

# Follow-up Pass: Cross-Tab Corruption Fix (direct implementation)

## Status

Phase 3–5 were already implemented and green (157 focused / 821 broader). This pass
re-audited the 15 **pre-catalog** entries that `_CROSSCHECK_FIELD_SPECS` never
covered, against the real evidence tree, and found they were still document-wide
regexes. Five produced silent cross-tab corruption.

## Defects Found and Fixed

| # | Defect | Evidence | Fix |
|---|--------|----------|-----|
| 1 | `wf_max_tests` rewrote `<MaxTests>` in **all three** tabs | template: WFO=100, WFM=100, PSPP=1000 | moved to `_settings_scope(_WFO)` |
| 2 | `wf_period` / `wf_optimization` leaked into WalkForwardMatrix | template declares `<WalkForward period="10" optimization="15">` in both tabs | scoped to WFO settings |
| 3 | `wf_optimize_periods` / `wf_optimize_exit_types` leaked into WFM | same | scoped to WFO settings |
| 4 | `wf_acceptance_threshold_pct` rewrote WFM's `thresholdPct` | both tabs declare `<Conditions thresholdPct="80">` | scoped to WFO acceptance |
| 5 | `rc_spread` rewrote the **project's main chart** spread | template has `<Chart symbol="GBPUSD…" spread="3">` in the root Setup *and* `<Chart symbol="EURUSD…" spread="2">` in RC | scoped to RC settings |
| 6 | `wf_acceptance_min_conditions` / `_min_markets` wrote into the RC tab | WFO declares no `MinConditions`/`MinMarkets`; only RC does | scoped to WFO acceptance (now inert + logged) |

## Fields Found Inert (not defects — evidence mismatch)

`wf_acceptance_pf_min` and `rc_pf_min` target a `minValue` attribute on
`<Column-Value>`. SQX 144.2953 **never emits it**: checked across `Build-Task1.xml`,
2 saved configs and 123 sampled real project configs — 0 occurrences on any
`Column-Value` (`minValue` only ever appears on strategy `<Param>` nodes). The PF
minimums actually live in the Condition tree's `<Numeric-Value>`, which this change
keeps as `raw_xml` by design.

These two fields previously "passed" a test that fed hand-written XML carrying the
nonexistent attribute. They are now registered as explicitly inert
(`TestCrosscheckMappingsHaveEvidence._INERT`), asserted as no-ops on real XML, and
kept in the spec table so the map/field parity invariant still holds.

## Coverage Added

`WalkForwardMatrix` declares its own copy of five WFO Settings leaves
(`period`, `optimization`, `OptimizePeriods`, `OptimizeExitTypes`, `MaxTests`)
that had **no** field. Without them the matrix settings were only reachable by
letting WFO's values leak across — which the isolation tests now forbid. Added as
`wfm_period`, `wfm_optimization`, `wfm_optimize_periods`,
`wfm_optimize_exit_types`, `wfm_max_tests`.

## Verification

- Focused: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/phase4/test_project_builder.py tests/knowledge/test_crosschecks_schema.py tests/cfx/test_crosschecks_models.py` → **157 passed**
- Broader: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/phase4 tests/cfx` → **821 passed**
- `tests/agents` + `sdk/tests`: 5 failures, all **pre-existing** — confirmed identical with this pass's changes `git stash`ed (research-agent F1 warnings, knowledge-store layout). Not touched.
  > **CORRECTED at archive 2026-09-30 (was S-1 in the verify report).** This claim is stale. An independent run of `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/agents sdk/tests` gave **1781 passed, 0 failed, exit 0**. The 5 failures no longer exist. Do not discount a real regression on this path as "known pre-existing" — re-run it. The row is preserved above as a record of what was believed when written; this annotation is the current state.
- Catalog audit: all 112 specs re-resolved against `Build-Task1.xml`; every scope and leaf matches except the 4 explicitly inert entries plus `so_use` (evidence lives in the saved config, asserted separately).

## Deferred Follow-ups

- Acceptance `Condition` trees stay `raw_xml` per the design decision. Callers who
  need PF minimums must go through `CrossChecksConfig`, not `BuildConfig`.
- `wf_acceptance_min_conditions` / `wf_acceptance_min_markets` remain in `BuildConfig`
  for API compatibility but can never write; consider deprecating them once no
  caller sets them.
- `WalkForwardMatrix` acceptance `Condition` list and `WhatIf` per-method day/hour/
  month selections (24 `H0..H23`, 12 months, 7 weekdays) are still `raw_xml`.

---

# Archive Corrections (2026-09-30)

Added at archive time when the final state of this change was re-derived from the
artifacts rather than from this log. The rows above are preserved as a record of
what was believed when written; the table below is the current state. Nothing here
was rewritten in place except the `tests/agents sdk/tests` claim, which was
annotated because a stale "pre-existing" note on a live test path invites a
reader to discount a real regression.

| Stale claim | Where | State at close |
|-------------|-------|----------------|
| "`tests/agents` + `sdk/tests`: 5 failures, all pre-existing" | L84 (annotated in place above) | **1781 passed, 0 failed**, exit 0. Corrected. |
| "3.3 Helper — `_apply_acceptance_settings()` addresses a leaf by tab scope" | L17 | The helper was **removed** (tasks 3.3 / 5.2 / 6.11): `_CROSSCHECK_FIELD_SPECS` already expresses tab scoping, so it reduced to a one-line wrapper with no production caller. Verified: `hasattr(project_builder, "_apply_acceptance_settings") == False`. |
| "3.2 GREEN map — 114 entries in `_BUILD_CONFIG_MAP`" | L16 | **213** entries, matching 213 `BuildConfig` fields exactly (0 unmapped, 0 extra). |
| "3.3 Helper" rollback boundary still names the removed helper | L32 | Revert `project_builder.py` map entries and `_CROSSCHECK_FIELD_SPECS`; `BuildConfig` fields remain. |
| "Phase 4 … 169 passed (focused), full suite baseline maintained" | L8 | Historical snapshot of the Phase 3–5 pass. Final gate evidence: **854 passed** (`tests/phase4 tests/cfx`), 1781 passed (`tests/agents sdk/tests`), whole tree 2662 passed / 9 skipped / 1 pre-existing flake. |
| `design.md` "File Changes" lists `sdk/tests/test_cfx.py` (modify) and `sdk/tests/sqx/test_project_builder.py` (create) | `design.md` L39–40 | Neither file exists. Real test homes: `tests/cfx/test_crosschecks_models.py`, `tests/cfx/test_reader_crosschecks.py`, `tests/phase4/test_project_builder.py`, `tests/knowledge/test_crosschecks_schema.py`. Task 5.3 verified the *decisions*, not this table. |
| `design.md` "E2E | Summary contract" testing layer | `design.md` L85 | Realised as a unit test. No E2E layer exists in this project; SUGGESTION-level only. |
| `spec.md` enumerated 8 robustness tabs | `spec.md` L6 / L28 / L65 | **9** — `SequentialOptimization` is the 9th child of the real `<CrossChecks>`. Corrected in the delta and in the merged main spec at archive time. |

Full detail, including the four carried-forward warnings (W-1 … W-4) and the fact
that this is the change's second archive, is in `archive-report.md`.
