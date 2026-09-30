# Tasks: CrossChecks Full Parameter Catalog

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 900–1,200 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: KB schema → PR 2: SDK models → PR 3: Builder + tests |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | KB YAML schema extension with evidence_refs | PR 1 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/kb/` | N/A — pure data files | Revert 10 YAML files; no code impact |
| 2 | WhatIf + MonteCarloRetest method models + summary | PR 2 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_crosschecks_models.py` | `python3 -c "from quantlab.cfx.models import CrossChecksConfig; ..."` | Revert model changes; raw_xml fallback preserves backward compat |
| 3 | Builder ~80+ mappings + acceptance helper + version drift | PR 3 | `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/phase4/test_project_builder.py` | `python3 -c "from quantlab.sqx.project_builder import _apply_build_config; ..."` | Revert map entries and helper; BuildConfig fields remain |

## Phase 1: Foundation / KB Schema

- [x] 1.1 Extend `Walk-Forward Optimization.yaml` with `xml_path`, `element_name`, `type`, `default`, `range`
- [x] 1.2 Extend `What If simulations.yaml` with schema fields
- [x] 1.3 Extend `Monte Carlo retest methods.yaml` with schema fields
- [x] 1.4 Extend `Monte Carlo trades manipulation.yaml` with schema fields
- [x] 1.5 Extend `Higher backtest precision.yaml` with schema fields
- [x] 1.6 Extend `Backtests on additional markets.yaml` with schema fields
- [x] 1.7 Extend `Walk-Forward Matrix.yaml` with schema fields
- [x] 1.8 Extend `Opt. Profile _ Sys. Param. Permutation.yaml` with schema fields
- [x] 1.9 Extend `Sequential Optimization.yaml` with schema fields
- [x] 1.10 Verify `Cross Checks vs Retester.yaml` stays `needs_review` with doc-gap markers

## Phase 2: SDK Model Extension

- [x] 2.1 RED: Write failing test `test_whatif_method_params_roundtrip` in `tests/cfx/test_crosschecks_models.py`
- [x] 2.2 GREEN: Add `WhatIfConfig` model with `use` + typed `methods` to `sdk/quantlab/cfx/models.py`
- [x] 2.3 RED: Write failing test `test_mc_method_params_parsed` for MonteCarloRetest Methods
- [x] 2.4 GREEN: Extend `MonteCarloRetest` with `methods: list[CrossChecksMethod] | None = None` and update `_parse_automatic_retest`
- [x] 2.5 RED: Write failing test `test_summary_returns_json_and_text` for dual-output contract
- [x] 2.6 GREEN: Refactor `summary()` to return `{"json": dict, "text": str}` with enabled_tabs and typed_values
- [x] 2.7 Verify Generic/AutomaticRetest dialects round-trip unchanged

## Phase 3: Builder Mapping + Version Drift

- [x] 3.1 RED: Write failing test `test_wf_acceptance_threshold_pct_maps_to_conditions` in `tests/phase4/test_project_builder.py`
- [x] 3.2 GREEN: Add ~80+ CrossChecks entries to `_BUILD_CONFIG_MAP` in `sdk/quantlab/sqx/project_builder.py`
- [x] 3.3 ~~Add `_apply_acceptance_settings` helper for nested Settings/AcceptanceSettings XML~~ — **not needed and removed.** The conditional in the task ("only if the mapping actually needs nested handling") did not hold: `_CROSSCHECK_FIELD_SPECS` already expresses tab scoping as `{tab}/AcceptanceSettings` + `_acceptance_scope(tab)`, so the helper reduced to a one-line wrapper over `_apply_in_scope` with no production caller. Its direct tests were rewritten to drive `_apply_build_config` instead, so the same invariants are now covered on the real entry point.
- [x] 3.4 RED: Write failing test `test_version_drift_invalidates_to_needs_review`
- [x] 3.5 GREEN: Add `invalidate_on_version_drift()` to catalog loader; warn but do not block

## Phase 4: Testing + Verification

- [x] 4.1 Add catalog extraction test: every KB YAML entry has `evidence_ref` and `xml_path`
- [x] 4.2 Add integration test: `BuildConfig(wf_acceptance_threshold_pct=80)` produces `<Conditions thresholdPct="80">`
- [x] 4.3 Add round-trip test: WhatIf + MonteCarloRetest methods survive `from_xml()` → `to_xml()` → `from_xml()`
- [x] 4.4 Run full suite: `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/test_crosschecks_models.py tests/phase4/test_project_builder.py`

## Phase 6: Cross-Tab Corruption Audit (follow-up pass)

The catalog table covered 92 of 107 CrossChecks fields; the 15 pre-catalog entries
were still document-wide regexes. Auditing them against real CFX evidence found
silent cross-tab corruption. Fixed in this pass — see `apply-progress.md`.

- [x] 6.1 RED: `TestCrosscheckLegacyMappingsDoNotCorruptSiblings` — `wf_max_tests` hit WFO+WFM+PSPP, `wf_period`/`wf_optimization` hit both WFO and WFM, `rc_spread` hit the project's main chart
- [x] 6.2 GREEN: migrate all 15 legacy entries into `_CROSSCHECK_FIELD_SPECS` with tab-scoped regions; delete the inline unscoped map block
- [x] 6.3 RED: `TestCrosscheckAcceptanceCountsAreTabOwned` — `wf_acceptance_min_conditions`/`_min_markets` wrote into the RC tab
- [x] 6.4 GREEN: scope those two to WFO acceptance (inert, since WFO declares neither node)
- [x] 6.5 RED: `TestCrosscheckAcceptanceThresholdsMatchRealEvidence` — replace a fabricated `minValue` XML fixture with the real template
- [x] 6.6 GREEN: register `rc_pf_min` / `wf_acceptance_pf_min` as explicitly inert in `TestCrosscheckMappingsHaveEvidence._INERT`, with a guard that the exception list cannot grow silently
- [x] 6.7 GREEN: correct two `TestCrossChecksOverrides` tests that asserted the *buggy* behaviour (`<MinConditions>3</MinConditions>` from a WFO-scoped field)
- [x] 6.8 Add `wfm_period`, `wfm_optimization`, `wfm_optimize_periods`, `wfm_optimize_exit_types`, `wfm_max_tests` — WFM declared its own copy of five WFO Settings leaves that had no field
- [x] 6.9 Add `TestCrosscheckWalkForwardMatrixSettings` + per-tab isolation
- [x] 6.10 Verify catalog parity: 213 `BuildConfig` fields ↔ 213 `_BUILD_CONFIG_MAP` entries, no unmapped/extra
- [x] 6.11 Remove dead `_apply_acceptance_settings` helper and its shim-only tests; re-point coverage at `_apply_build_config`

## Phase 5: Cleanup

- [x] 5.1 Update docstrings in `sdk/quantlab/cfx/models.py` for new WhatIf/MonteCarlo method fields
- [x] 5.2 Remove any temporary test scaffolding after GREEN phase — dropped the fabricated `Column-Value minValue` fixture in `test_rc_pf_min` (no SQX 144.2953 artifact emits that attribute) and the dead `_apply_acceptance_settings` helper
- [x] 5.3 Verify `openspec/changes/crosschecks-full-parameter-catalog/design.md` alignment

## Not Done (deliberate, see apply-progress.md)

- Acceptance `Condition` trees stay `raw_xml` per the design decision. PF minimums
  are therefore unreachable through `BuildConfig`; callers use `CrossChecksConfig`.
- `wf_acceptance_min_conditions` / `wf_acceptance_min_markets` remain in
  `BuildConfig` for API compatibility but can never write. Deprecate once unused.
- `WhatIf` per-method day/hour/month selections (7 weekdays + 24 hours + 12 months),
  `WalkForwardMatrix` acceptance conditions, and `MonteCarloManipulation` internals
  remain `raw_xml`. They need a typed list/dict shape, which is an API decision.
