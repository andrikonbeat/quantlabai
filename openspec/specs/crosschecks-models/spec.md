# CrossChecks Models Specification

## Purpose

Define typed Pydantic models for the two production CrossChecks dialects (Generic and AutomaticRetest) in the QuantLab SDK CFX module, preserving `raw_xml` as a backward-compatible fallback for unknown elements.

## Requirements

### Requirement: CrossChecks Generic Dialect Model

The system MUST provide a `CrossChecksGeneric` model with typed fields for MonteCarlo (`mc_enabled`, `mc_runs`, `mc_percentile`), WalkForward (`wf_enabled`, `wf_cycles`), and `confidence_level`.

#### Scenario: Generic model defaults
- GIVEN no CrossChecks XML is present
- WHEN a `CrossChecksGeneric` model is instantiated
- THEN all typed fields hold documented defaults (`mc_enabled=False`, `mc_runs=100`, `mc_percentile=95`, `wf_enabled=False`, `wf_cycles=5`, `confidence_level=0.95`)

#### Scenario: Generic model parses known elements
- GIVEN CrossChecks XML containing `<MonteCarlo><Use>1</Use><Runs>200</Runs></MonteCarlo>`
- WHEN the reader populates the typed model
- THEN `mc_enabled=True` and `mc_runs=200` are set, and unrecognized siblings remain in `raw_xml`

### Requirement: CrossChecks AutomaticRetest Dialect Model

The system MUST provide a `CrossChecksAutomaticRetest` model with typed fields for `use`, `retest_with_higher_precision`, `monte_carlo_retest`, `monte_carlo_manipulation`, `retest_on_additional_markets`, `walk_forward_optimization`, `walk_forward_matrix`, `opt_profile_sys_param_permutation`, and `what_if`.
(Added by `crosschecks-full-parameter-catalog`, archived 2026-09-30. `monte_carlo_retest` gained a `methods: list[CrossChecksMethod] | None` field and `what_if` was added as a typed `WhatIfConfig`. This requirement previously enumerated 8 fields and omitted `what_if`, under-constraining the model that actually ships.)

`CrossChecksMethod` MUST expose `use`, `type` and `params`, and MUST be shared by the `WhatIfConfig` and `MonteCarloRetest` method leaves.

#### Scenario: AutomaticRetest model parses nested elements
- GIVEN CrossChecks XML containing `<RetestWithHigherPrecision><Use>1</Use></RetestWithHigherPrecision>`
- WHEN the reader populates the typed model
- THEN `retest_with_higher_precision.use` is `True` and the parsed subtree is removed from `raw_xml`

#### Scenario: Unknown AutomaticRetest elements preserved
- GIVEN CrossChecks XML with an unrecognized `<FutureElement>` inside AutomaticRetest
- WHEN the reader populates the typed model
- THEN `FutureElement` remains in `raw_xml` and the typed model is still valid

#### Scenario: WhatIf methods are parsed as typed models
- GIVEN a `<WhatIf>` element whose `<Settings><Methods>` block declares `<Method>` children with `use`, `type` and `<Params>`
- WHEN the reader populates the typed model
- THEN `what_if.use` reflects the element's `use` attribute
- AND `what_if.methods` holds one `CrossChecksMethod` per `<Method>` element with its `params` populated

#### Scenario: MonteCarloRetest methods are parsed as typed models
- GIVEN a `<MonteCarloRetest>` element declaring `<Settings><Methods>` alongside its scalar settings
- WHEN the reader populates the typed model
- THEN `monte_carlo_retest.methods` is populated with one `CrossChecksMethod` per `<Method>` element
- AND the tab's scalar settings remain independently accessible

#### Scenario: Unmodeled method sub-structures fall back to raw_xml
- GIVEN a `<WhatIf>` method whose parameters are not expressible as a typed key/value map
- WHEN the reader populates the typed model
- THEN the unmodeled structure is preserved rather than dropped, and the typed model remains valid

### Requirement: CrossChecksConfig Dialect Container

The system MUST update `CrossChecksConfig` to hold `dialect: str`, `generic: CrossChecksGeneric | None`, `automatic_retest: CrossChecksAutomaticRetest | None`, and `raw_xml: str`, preserving backward compatibility with existing `raw_xml` consumers.

#### Scenario: Dialect discriminator guides consumers
- GIVEN a `CrossChecksConfig` with `dialect="generic"`
- WHEN a consumer reads the config
- THEN `config.generic` is populated and `config.automatic_retest` is `None`

#### Scenario: Legacy raw_xml fallback remains available
- GIVEN a `CrossChecksConfig` where typed fields are `None`
- WHEN a consumer accesses `raw_xml`
- THEN the original XML string is intact for regex fallback
