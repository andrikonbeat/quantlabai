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

The system MUST provide a `CrossChecksAutomaticRetest` model with typed fields for `use`, `retest_with_higher_precision`, `monte_carlo_retest`, `monte_carlo_manipulation`, `retest_on_additional_markets`, `walk_forward_optimization`, `walk_forward_matrix`, and `opt_profile_sys_param_permutation`.

#### Scenario: AutomaticRetest model parses nested elements
- GIVEN CrossChecks XML containing `<RetestWithHigherPrecision><Use>1</Use></RetestWithHigherPrecision>`
- WHEN the reader populates the typed model
- THEN `retest_with_higher_precision.use` is `True` and the parsed subtree is removed from `raw_xml`

#### Scenario: Unknown AutomaticRetest elements preserved
- GIVEN CrossChecks XML with an unrecognized `<FutureElement>` inside AutomaticRetest
- WHEN the reader populates the typed model
- THEN `FutureElement` remains in `raw_xml` and the typed model is still valid

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

### Requirement: Dialect Round-Trip Fidelity

Typed access and lossless serialization are both required: because the models deliberately do not
model every nested element, a parsed element MUST retain its original markup and MUST be
re-serialized from that markup rather than rebuilt from typed fields.

#### Scenario: Unmodeled inner content survives a round-trip
- GIVEN AutomaticRetest XML whose `<MonteCarloRetest>` contains `<Methods>`, and whose
  `<WalkForwardOptimization>` contains `<Param1>`/`<Param2>` and `<OptimizeExitTypes>`
- WHEN the config is parsed with `from_xml()` and serialized with `to_xml()`
- THEN the `<Methods>`, `<Param1>`, `<Param2>` and `<OptimizeExitTypes>` content is present in the
  output, because the sub-model's `raw_xml` is re-emitted verbatim

#### Scenario: Recognized elements are serialized exactly once
- GIVEN AutomaticRetest XML containing any element the parser recognizes
- WHEN the config is parsed and serialized
- THEN the element appears exactly once in the output, never from both its typed sub-model and
  `raw_xml`, because the routing set and the parser are kept in sync

#### Scenario: Confidence level is read in both spellings
- GIVEN Generic CrossChecks XML using either `<ConfidenceLevel value="0.95"/>` or
  `<ConfidenceLevel>0.95</ConfidenceLevel>`
- WHEN the reader populates the typed model
- THEN `confidence_level` reflects the source value in both cases, and serialization preserves the
  source form rather than rewriting the dialect

#### Scenario: Monte Carlo run count round-trips
- GIVEN a Generic CrossChecks config with a non-default `mc_runs`
- WHEN the config is serialized and re-parsed
- THEN `mc_runs` is unchanged, because the serializer writes the attribute spelling the parser reads
