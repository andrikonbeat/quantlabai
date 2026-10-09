# Delta for compiler-pipeline

## ADDED Requirements

### Requirement: Source Code Export (REQ-601)

The system MUST provide `AsyncSQXClient.export_sourcecode(strategy_id)` that performs HTTP GET `/sourcecode/print?id={strategy_id}` and returns source code as a string, or raises `JForexStrategyNotFoundError`, `JForexConnectionError`, or `JForexServerError`.

#### Scenario: Export returns source

- GIVEN SQX server running with strategy "s1"
- WHEN `export_sourcecode("s1")` is called
- THEN HTTP GET `/sourcecode/print?id=s1` is issued
- AND a non-empty source string is returned

**Acceptance**: HTTP request matches endpoint; response body returned as string.

**Error behavior**: 404 → JForexStrategyNotFoundError; network failure → JForexConnectionError; 5xx → JForexServerError.

#### Scenario: Missing strategy raises NotFound

- GIVEN SQX has no strategy "missing"
- WHEN `export_sourcecode("missing")` is called
- THEN `JForexStrategyNotFoundError` is raised
- AND the error includes the strategy ID

**Acceptance**: Exception type and strategy ID in message.

**Error behavior**: No source returned; caller must handle absence.

#### Scenario: Server error raises ServerError

- GIVEN SQX returns HTTP 500
- WHEN `export_sourcecode("s1")` is called
- THEN `JForexServerError` is raised
- AND response body is preserved

**Acceptance**: Status code and body accessible from exception.

**Error behavior**: Caller cannot retry blindly; inspect body for drift.

### Requirement: Strategy ID Compile Wiring (REQ-602)

The system MUST accept a `strategy_id` mapping alongside `portfolio_result` in `CompileStage`, producing `compiled_strategies` with source-to-artifact mapping keyed by strategy ID.

#### Scenario: Compile with strategy ID

- GIVEN a portfolio_result with strategy_id "s1" and source path
- WHEN CompileStage runs
- THEN compiled_strategies contains artifact keyed under "s1"
- AND the source path is recorded

**Acceptance**: Output dict key matches strategy_id; source path preserved.

**Error behavior**: Missing ID falls back to filename inference with warning.

#### Scenario: Missing strategy ID falls back to filename

- GIVEN a portfolio_result with no strategy_id
- WHEN CompileStage runs
- THEN filename inference is used
- AND a compilation warning is logged

**Acceptance**: Compilation succeeds; warning emitted.

**Error behavior**: Silent fallback is forbidden; warning is mandatory.

#### Scenario: Multiple strategies compile independently

- GIVEN portfolio_result containing "s1" and "s2"
- WHEN CompileStage runs
- THEN both strategies are compiled separately
- AND compiled_strategies has distinct entries per strategy

**Acceptance**: Two artifacts produced; no cross-contamination.

**Error behavior**: Failure in one strategy does not block the other.

### Requirement: Compile Failure Artifact (REQ-603)

The system MUST emit a `compilation_failed` artifact when the fix-loop bound is exceeded, instead of silently blocking the pipeline.

#### Scenario: Fix loop exhaustion emits artifact

- GIVEN a source failing beyond max_fix_iterations
- WHEN the fix loop halts
- THEN a compilation_failed artifact is emitted
- AND the pipeline advances to error handling

**Acceptance**: Artifact exists with error history and source path.

**Error behavior**: Pipeline does not halt silently; downstream sees artifact.

#### Scenario: Partial failures do not block successful compiles

- GIVEN strategy "s1" succeeds and "s2" fails
- WHEN CompileStage completes
- THEN s1 appears in compiled_strategies
- AND s2 appears in compilation_failed artifacts
- AND the pipeline does not halt silently

**Acceptance**: Mixed results preserved in respective outputs.

**Error behavior**: Silent block is forbidden; partial success is explicit.

#### Scenario: Artifact contains error history

- GIVEN a compilation_failed artifact for strategy "s2"
- WHEN downstream reads the artifact
- THEN it contains the full error history and source path

**Acceptance**: Artifact is self-describing for retry or human review.

**Error behavior**: Incomplete error history is a defect.
