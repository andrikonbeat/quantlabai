# Parameter Justification Matrix Specification

## Purpose

Generates a pedagogical parameter justification matrix (parameter_matrix.json) for every SQX builder/retester/optimizer configuration, documenting why each parameter value was chosen.

## Requirements

### Requirement: Matrix Generation

The system MUST generate a parameter_matrix.json for every builder, retester, and optimizer run. The matrix MUST include: parameter name, chosen value, rationale, source (default/manual/optimized), and confidence score. The matrix SHALL be stored in Knowledge Lake at `parameter-matrix/{run_id}/parameter_matrix.json`.

#### Scenario: Builder run produces matrix

- GIVEN a builder configuration with 12 parameters
- WHEN the builder completes
- THEN parameter_matrix.json contains 12 entries
- AND each entry has name, value, rationale, source, confidence

#### Scenario: Optimizer run produces matrix

- GIVEN an optimizer run over 3 parameters
- WHEN optimization completes
- THEN parameter_matrix.json contains 3 entries with source=optimized
- AND each rationale references the optimization objective

#### Scenario: Matrix validation fails on missing rationale

- GIVEN a matrix entry with empty rationale
- WHEN the matrix is validated
- THEN a ParameterMatrixError is raised
- AND the run is blocked from advancing

### Requirement: Matrix Reviewability

The system MUST produce the matrix in human-readable JSON format. Each entry SHALL include the SQX parameter tab name and a cross-reference to the SQX documentation when available.

#### Scenario: Matrix includes SQX tab reference

- GIVEN a parameter from the "Money Management" tab
- WHEN the matrix is generated
- THEN the entry includes tab="Money Management"
- AND a doc URL is included when available

#### Scenario: Matrix is reviewable without SQX

- GIVEN a parameter_matrix.json without SQX installed
- WHEN a human reviews the matrix
- THEN all rationales are self-contained
- AND no external lookup is required

### Requirement: Matrix Rationale Sources the Educational Dataset

The matrix MUST source each parameter's rationale from the shared educational dataset emitted by `parameter-educational-table` when a record exists for that parameter. Each matrix entry SHALL reference the dataset record by parameter name and tab. When no dataset record exists, the entry MUST fall back to the existing rationale sources (manual/optimized) and MUST NOT invent KB-sourced text.

#### Scenario: Dataset record drives rationale

- GIVEN a parameter with a record in the educational dataset (e.g., Maximum Trades Per Day)
- WHEN the matrix entry is generated
- THEN the rationale references dataset fields (what_it_does, quant role, small-account recommendation)
- AND the entry includes the parameter name and tab key

#### Scenario: No dataset record falls back gracefully

- GIVEN a configured parameter absent from the educational dataset
- WHEN the matrix entry is generated
- THEN the rationale uses manual or optimized sources only
- AND generation is not blocked by the missing record

#### Scenario: Dataset regenerates without breaking the contract

- GIVEN the educational dataset regenerated with unchanged inputs
- WHEN the matrix is generated against the new dataset
- THEN entries remain valid under the same data contract
- AND rationale content is unchanged for unchanged parameters
