# Proposal: CrossChecks Full Parameter Catalog

## Intent

Give LLM agents and human researchers one evidence-backed catalog of every SQX 144.2953 robustness-filtering parameter, so configurations reaching backtest/retest are correct instead of wasting compute.

## Background / Problem

Robustness settings span 9 CFX tabs in `Build-Task1.xml` → `<CrossChecks>`: `RetestOnAdditionalMarkets`, `WalkForwardOptimization`, `RetestWithHigherPrecision`, `MonteCarloRetest`, `WalkForwardMatrix`, `MonteCarloManipulation`, `OptProfileSysParamPermutation`, `SequentialOptimization`, `WhatIf`. Coverage today is Cross Checks only; unmodeled leaves fall through to `raw_xml`, so agents guess.

## Proposed Change

- Catalog **all 9 tabs** (~147 leaf parameters, Settings + Filtering/Acceptance), not Cross Checks alone.
- Extend `CrossChecksConfig` with `WhatIf` + `MonteCarloRetest` method leaves; `raw_xml` retained for recursive Condition trees.
- Map every parameter to `BuildConfig` / `_BUILD_CONFIG_MAP` (~80+ entries) plus a nested acceptance-settings helper.
- `summary()` returns **both** JSON and human-readable text.
- KB YAML schema gains `xml_path`, `element_name`, `section`, `type`, `range`, `evidence_ref`, `status`.
- Version drift invalidates entries to `needs_review`; consumers warn, non-strict proceeds.

## Capabilities

### New

- `crosschecks-parameter-catalog`: evidence-first catalog, builder mapping, dual summary, drift handling.

### Modified

- `sqx-parameter-kb`: REQ-201 schema gains `xml_path`/`element_name`; REQ-204/REQ-208 warn instead of blocking on `needs_review`.
- `cfx-editor`: `CrossChecks` typed coverage extends to WhatIf + MonteCarloRetest methods; dual-output `summary()`.

## Out of Scope

Typed models for Blocks/ATMs/Rankings · removing `raw_xml` fallback · UI/API surfaces beyond catalog + models · SQX versions other than 144.2953.

## User Impact

| Consumer | Gain |
|---|---|
| LLM agents | Correct values for every robustness tab; parseable JSON summary |
| Human researchers | Readable text summary; `evidence_ref` per parameter |

## Acceptance Criteria

- [ ] All 9 tabs cataloged; every entry has `evidence_ref` + `xml_path`; zero invented parameters.
- [ ] `BuildConfig(wf_acceptance_threshold_pct=80)` yields `<Conditions thresholdPct="80">`.
- [ ] `summary()` returns `{"json": dict, "text": str}`; Generic/AutomaticRetest dialects round-trip unchanged.
- [ ] Drift 144.2953 → 145.x flips entries to `needs_review`; consumers warn, non-strict proceeds.
- [ ] `SQX_FORCE_MOCK=1 python3 -m pytest -q tests/cfx/ tests/phase4/` green.

## Key Decisions

Evidence-first (`needs_review`, never invention) · all filtering tabs · dual JSON+text summary · version-isolated to 144.2953, extensible · typed scalars + `raw_xml` for Conditions.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Undocumented params (Cross Checks vs Retester) | High | `needs_review` + doc-gap markers |
| Builder regex drift vs real XML | Medium | Round-trip tests on real `.cfx` |
| Size ~900–1,200 lines | High | Chained PRs |

## Delivery Plan

Chained PRs, stacked-to-main, ≤400 changed lines/unit, strict TDD. PR1 KB schema · PR2 SDK models + summary · PR3 builder + tests.

## Rollback Plan

Revert per work unit: 10 YAML files (no code impact); model/builder changes — `raw_xml` fallback keeps backward compat, `BuildConfig` fields remain. No migration or data rollback.
