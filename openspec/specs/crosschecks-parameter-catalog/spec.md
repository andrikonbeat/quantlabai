# CrossChecks Full Parameter Catalog

## Requirements

### Requirement: Catalog Completeness
The system MUST catalog all robustness parameters in SQX 144.2953 CrossChecks/WhatIf tabs. Each entry MUST include name, tab, type, xml_path, element_name, default, range, what-it-does, how-it-works-in-SQX, quant-trading-role, status, sqx_version, and evidence_ref. `.cfx` evidence shows all 9 top-level `<CrossChecks>` children: RetestOnAdditionalMarkets, WalkForwardOptimization, RetestWithHigherPrecision, MonteCarloRetest, WalkForwardMatrix, MonteCarloManipulation, OptProfileSysParamPermutation, WhatIf, and SequentialOptimization.
(Corrected at archive 2026-09-30: the requirement previously enumerated 8 tabs and omitted SequentialOptimization, while the real `.cfx` has 9 children and the catalog ships 9 `verified` entries. The required-field list previously omitted xml_path, element_name, sqx_version and evidence_ref, which the catalog enforces and the test suite verifies.)

### Requirement: Evidence-First Extraction
The system MUST derive each entry from real CFX/template/KB evidence. Every entry MUST carry an `evidence_ref`. The system MUST NOT invent semantics; doc gaps MUST become `needs_review`.

### Requirement: Model Extension
The system MUST extend `CrossChecksConfig` typed models for missing robustness tabs: WhatIf method parameters and MonteCarloRetest method configurations. Extensions MUST preserve Generic/AutomaticRetest dialect compatibility.

### Requirement: Builder Field Mapping
The system MUST map every cataloged CrossChecks parameter to a `BuildConfig` field in `project_builder.py`. Each mapping MUST include XML regex, replacement template, and SQX tab classification. Unknown or composite parameters MUST fall back to `raw_xml` passthrough.

### Requirement: Summary Contract
The system MUST provide a `summary()` method on `CrossChecksConfig` returning both JSON dict and human-readable text. JSON MUST include dialect, enabled tabs, and typed values. Text MUST be a single-line string for log envelopes.

### Requirement: Versioning and Needs-Review
The system MUST treat `needs_review` as first-class status. On SQX version drift, the system MUST invalidate catalog entries by marking them `needs_review` and MUST NOT serve them as `verified`. Consumers MUST warn when using `needs_review` entries.

## Scenarios

### Scenario: Full tab coverage from CFX evidence
- GIVEN `project.cfx`
- WHEN the catalog is extracted
- THEN all 9 robustness tabs appear with XML structures documented

### Scenario: Evidence trace for every parameter
- GIVEN a cataloged parameter `WalkForwardOptimization.period`
- WHEN its entry is queried
- THEN `evidence_ref` points to the CFX or template XML containing the element
- AND the entry includes default, range, and quant-role from that evidence

### Scenario: Model extension preserves round-trip
- GIVEN a `CrossChecksConfig` with WhatIf and MonteCarloRetest methods populated
- WHEN `to_xml()` is called
- THEN output contains the new typed fields
- AND existing Generic/AutomaticRetest dialects round-trip unchanged

### Scenario: Builder mapping covers acceptance settings
- GIVEN `BuildConfig` with `wf_acceptance_threshold_pct=80`
- WHEN `_apply_build_config` processes it
- THEN template XML contains `<Conditions thresholdPct="80">`

### Scenario: Summary contract dual output
- GIVEN `CrossChecksConfig`
- WHEN `summary()` is called
- THEN JSON output contains `dialect`, enabled flags, and typed sub-models
- AND text output is a single readable line

### Scenario: Needs-review survives version drift
- GIVEN a verified parameter under `sqx-kb/144.2953/`
- WHEN SQX version drifts to 145.x
- THEN the parameter status becomes `needs_review`
- AND `builder_agent` receives a warning but may proceed with explicit justification

## Out of Scope
- Typed models for non-robustness CFX sections (Blocks, ATMs, Rankings)
- UI/API surface changes beyond catalog and model extensions
- Breaking removal of `raw_xml` fallback in `CrossChecksConfig`

## Acceptance Criteria
All 9 robustness tabs from CFX evidence are cataloged with evidence_refs. Every catalog entry traces to CFX, template, or KB evidence; no invented semantics. `CrossChecksConfig` extends to cover WhatIf and MonteCarloRetest method parameters. `BuildConfig` mapping covers all acceptance-settings and method parameters. `summary()` returns both JSON dict and human-readable text. `needs_review` is first-class: version drift invalidates to needs_review, consumers warn but may proceed. Unit tests cover extraction, model round-trip, builder mapping, summary contract, and version invalidation.

## Dependencies
- `sdk/quantlab/cfx/models.py` — extend `CrossChecksConfig`
- `sdk/quantlab/sqx/project_builder.py` — extend `BuildConfig` and `_BUILD_CONFIG_MAP`
- `knowledge/structured/sqx-kb/144.2953/parameters/Cross checks/` — seed/verify target
- `assets/SQX_144_2953_linux_20260601/user/projects/sqx_4fdea2e7519c/project.cfx` — primary evidence
- `sdk/quantlab/sqx/templates/default-project.sqx-template` — secondary evidence
- `openspec/specs/sq x-parameter-kb/spec.md` — KB schema and versioning contract

## Error Handling / Edge Cases
Unknown XML child: preserve in `raw_xml`, do not fail parse. Missing evidence_ref: parameter loads as `needs_review`, not `verified`. Builder mapping for unknown field: log warning, skip regex, preserve XML unchanged. Version drift without evidence: all affected params become `needs_review`; consumers block only if `strict` mode is enabled. WhatIf method params: store as raw XML sub-dicts until schema stabilizes.
