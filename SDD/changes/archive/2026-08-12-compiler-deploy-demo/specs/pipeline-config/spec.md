# Delta for pipeline-config

## ADDED Requirements

### Requirement: 14-Phase Pipeline Emission (REQ-631)

`BuilderAgent.generate_pipeline_config()` MUST emit the full 14-phase pipeline: research → hypothesis → refutation → builder → config_review → dispatch → statistics → analysis → review → portfolio → compile → deploy → demo → archive.

#### Scenario: Config emits all 14 phases

- GIVEN BuilderAgent with default settings
- WHEN `generate_pipeline_config()` is called
- THEN the returned config contains all 14 phases in order
- AND each phase has a unique identifier

**Acceptance**: Phase list length is 14; order matches specification.

**Error behavior**: Missing phase raises ConfigValidationError.

#### Scenario: New phases appended after portfolio

- GIVEN an existing 8-phase config
- WHEN `generate_pipeline_config()` upgrades to 14-phase
- THEN phases 9-14 are appended after portfolio
- AND phases 1-8 are unchanged

**Acceptance**: Existing phases preserved; new phases appended.

**Error behavior**: Insertion in the middle raises ConfigValidationError.

#### Scenario: Phase identifiers are deterministic

- GIVEN two config generations for the same run
- WHEN both produce 14-phase configs
- THEN phase identifiers and order are identical
- AND configs are equal

**Acceptance**: Deterministic output enables config diffing.

**Error behavior**: Non-determinism raises ConfigDriftError in CI.

### Requirement: Additive Pipeline Config (REQ-632)

Pipeline config MUST be additive — existing 8-phase configs continue to work; new phases are appended, not inserted in the middle.

#### Scenario: Existing 8-phase config still valid

- GIVEN a saved 8-phase pipeline config
- WHEN `generate_pipeline_config()` reads it
- THEN it loads without error
- AND the original 8 phases are preserved

**Acceptance**: Backward compatibility; no migration required.

**Error behavior**: Corrupt 8-phase config raises ConfigValidationError.

#### Scenario: Migration appends missing phases

- GIVEN a 10-phase config missing compile, deploy, demo, archive
- WHEN `generate_pipeline_config()` upgrades it
- THEN the missing 4 phases are appended
- AND existing 10 phases are untouched

**Acceptance**: Upgrade is non-destructive; order is preserved.

**Error behavior**: Reordering existing phases raises ConfigValidationError.

#### Scenario: Feature flag gates 14-phase default

- GIVEN `QUANTLAB_14PHASE=0` env var set
- WHEN `generate_pipeline_config()` is called
- THEN an 8-phase config is emitted by default
- AND 14-phase is opt-in via flag or explicit request

**Acceptance**: Default behavior is backward compatible.

**Error behavior**: Invalid flag value raises ConfigurationError.
