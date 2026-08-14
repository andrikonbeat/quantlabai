# Full Campaign Lifecycle Specification

## Purpose

Defines the end-to-end campaign lifecycle spanning 14 ordered phases from research through live-ops, with human gates and envelope artifacts at each boundary.

## Requirements

### Requirement: 14-Phase Lifecycle

The system MUST execute all 14 phases in order: research → hypothesis → config → config-review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops. Each phase MUST emit an envelope artifact to Knowledge Lake before advancing. The system MUST NOT stop at optimize.

#### Scenario: Full flow completes all phases

- GIVEN a valid campaign with all 14 phases enabled
- WHEN execution starts
- THEN every phase completes in order
- AND 14 envelope artifacts are stored in Knowledge Lake

#### Scenario: Missing phase aborts at startup

- GIVEN a configuration missing the portfolio phase
- WHEN the campaign initializes
- THEN the flow-integrity assertion fails
- AND the campaign aborts before any phase runs

#### Scenario: Human gate pauses advancement

- GIVEN the pipeline reaches HUMAN_APPROVE_PORTFOLIO
- WHEN approval is pending
- THEN execution halts at the portfolio phase
- AND no downstream phases start

### Requirement: Flow Integrity Invariant

The system MUST assert at campaign start that all 14 phases are present in the correct order. The 14-phase order SHALL be segment-preserving: the loop tail is `monitor → guardian_evaluate → [retester] → [optimizer]` bound post-archive, making `live-ops` the terminal phase; `STAGE_FOR_PHASE["live-ops"]` MUST map to `"live_ops"`. If any phase is dropped, any segment is reordered, or a phase maps to the wrong stage, the system SHALL abort before execution begins.

#### Scenario: Phase drop detected at startup

- GIVEN a pipeline configuration missing the compile phase
- WHEN the campaign initializes
- THEN the flow integrity assertion fails
- AND the campaign aborts with a phase-drop error

#### Scenario: Correct order passes invariant

- GIVEN all 14 phases in the correct order with the segment-preserving loop tail
- WHEN the campaign initializes
- THEN the flow integrity assertion passes
- AND execution proceeds to the first phase

#### Scenario: Reordered segment fails validation

- GIVEN a pipeline with loop-tail segments reordered (e.g., `guardian_evaluate` before `monitor`)
- WHEN the campaign initializes
- THEN validation fails with a reorder error
- AND no phase executes

#### Scenario: Dropped loop-tail segment fails validation

- GIVEN a pipeline missing the `retester` segment of the loop tail
- WHEN the campaign initializes
- THEN validation fails with a phase-drop error
- AND the campaign aborts before execution

#### Scenario: live-ops stage is mapped

- GIVEN the canonical 14-phase pipeline
- WHEN `STAGE_FOR_PHASE["live-ops"]` is resolved
- THEN it maps to the `"live_ops"` stage
- AND the terminal phase executes on that stage

### Requirement: Phase Envelope Contract

The system MUST produce a phase envelope artifact for each completed phase. Each envelope SHALL contain: phase name, start/end timestamps, status (completed/failed/hold), artifacts produced, and next-phase gate.

#### Scenario: Envelope written after phase completion

- GIVEN a completed research phase
- WHEN the envelope is written
- THEN the envelope contains completed status
- AND artifacts list includes the research output
- AND next-phase gate is HUMAN_APPROVE_HYPOTHESIS

#### Scenario: Failed phase envelope records error

- GIVEN a retest phase that fails with SQX error
- WHEN the envelope is written
- THEN the envelope contains failed status
- AND artifacts list includes the error log
- AND next-phase gate is HOLD
