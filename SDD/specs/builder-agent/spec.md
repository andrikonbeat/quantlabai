# Builder Agent Specification

## Purpose

Extends BuilderAgent with parameter justification matrix generation and unified execution substrate handoff.

## Requirements

### Requirement: Parameter Matrix Generation

The system MUST make BuilderAgent generate a parameter_matrix.json for every build run. The matrix SHALL be derived from BuildConfig fields and MUST include rationale for each non-default value. The matrix MUST be stored in Knowledge Lake at `parameter-matrix/{run_id}/parameter_matrix.json`.

#### Scenario: Build with defaults produces matrix

- GIVEN a BuildConfig with mostly default values
- WHEN BuilderAgent completes
- THEN parameter_matrix.json contains all parameters
- AND default values have rationale "using SQX default"

#### Scenario: Manual override requires justification

- GIVEN a BuildConfig with a manually overridden parameter
- WHEN BuilderAgent generates the matrix
- THEN the overridden parameter has a non-empty rationale
- AND the source is marked manual

#### Scenario: Missing rationale blocks advancement

- GIVEN a matrix entry with empty rationale
- WHEN the matrix is validated
- THEN a ParameterMatrixError is raised
- AND the run is blocked from advancing

### Requirement: Unified Execution Handoff

The system MUST hand off completed builds to the unified execution substrate rather than dispatching directly. The handoff SHALL include the CFX archive path, phase type, checkpoint metadata, and the monitoring hooks `llm_config`, `on_watcher_event`, `on_llm_verdict`, `confirm_stop`, and `gate_event_dir`.

#### Scenario: Build hands off to substrate

- GIVEN a completed build with CFX archive
- WHEN BuilderAgent finishes
- THEN the substrate receives the CFX path and phase=build
- AND a checkpoint is created for resume capability

#### Scenario: Handoff failure preserves build artifact

- GIVEN substrate handoff fails
- WHEN BuilderAgent detects the failure
- THEN the CFX archive remains in Knowledge Lake
- AND the campaign enters HOLD for human review

#### Scenario: Monitoring hooks passed through handoff

- GIVEN a dispatch with monitoring configured
- WHEN BuilderAgent hands off to the substrate
- THEN `llm_config`, `on_watcher_event`, `on_llm_verdict`, `confirm_stop`, and `gate_event_dir` are passed through
- AND the substrate wires them into the monitor stage
