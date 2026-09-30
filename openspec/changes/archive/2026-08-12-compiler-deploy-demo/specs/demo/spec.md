# Delta for demo

## ADDED Requirements

### Requirement: Demo Window State Persistence (REQ-621)

The system MUST persist `started_at`, `expires_at`, and `renewal_count` to Knowledge Lake; window state SHALL survive process restarts.

#### Scenario: Window state survives restart

- GIVEN DemoWindow started with 14-day expiry
- WHEN the process restarts and loads state
- THEN started_at, expires_at, and renewal_count are restored
- AND the remaining window is calculated from expires_at

**Acceptance**: State load within 1s; fields match pre-restart values.

**Error behavior**: Corrupt state raises StateCorruptionError and blocks pipeline.

#### Scenario: Renewal increments count

- GIVEN a window with renewal_count=0
- WHEN renewal is approved and persisted
- THEN renewal_count becomes 1
- AND expires_at is extended by 14 business days

**Acceptance**: Atomic write; count and expiry update together.

**Error behavior**: Failed write blocks renewal; state remains unchanged.

#### Scenario: Concurrent renewals serialize

- GIVEN two renewal requests simultaneously
- WHEN both attempt to persist
- THEN only one succeeds
- AND the loser reads the updated count and retries or fails

**Acceptance**: No lost updates; count is monotonically increasing.

**Error behavior**: Serialization failure raises StateCorruptionError.

### Requirement: Fail-Closed Demo Expiry (REQ-622)

Demo expiry MUST fail closed — an expired window blocks the pipeline with a `HUMAN_APPROVE_DEMO` gate.

#### Scenario: Expired window blocks pipeline

- GIVEN a demo window with expires_at in the past
- WHEN the demo stage runs
- THEN the pipeline halts with HUMAN_APPROVE_DEMO
- AND no deployment proceeds

**Acceptance**: Gate is raised before any deploy call.

**Error behavior**: Clock skew tolerance is 5 minutes; beyond that, fail closed.

#### Scenario: Active window allows deployment

- GIVEN a demo window with expires_at in the future
- WHEN the demo stage runs
- THEN the pipeline continues
- AND no gate is raised

**Acceptance**: Expiry check passes; deployment proceeds.

**Error behavior**: Near-expiry warnings are logged but do not block.

#### Scenario: Renewed window resumes deployment

- GIVEN an expired window that received HUMAN_APPROVE_DEMO
- WHEN the renewed window is loaded
- THEN the demo stage continues
- AND a new expires_at is set

**Acceptance**: Gate clearance is recorded; pipeline resumes.

**Error behavior**: Stale approval older than 1 hour requires re-approval.

### Requirement: Demo Dry-Run Default (REQ-623)

Demo dry-run mode MUST be the default; explicit opt-in is required for live deployment.

#### Scenario: Default mode is dry-run

- GIVEN DemoStage with no explicit mode
- WHEN the stage initializes
- THEN mode is dry-run
- AND no live deploy call is made

**Acceptance**: dry_run=True is the implicit default.

**Error behavior**: Setting dry_run=False without explicit opt-in raises ConfigurationError.

#### Scenario: Explicit opt-in enables live deploy

- GIVEN dry_run=False set via config
- WHEN the demo stage runs
- THEN live deploy calls proceed
- AND a confirmation log is emitted

**Acceptance**: Opt-in is logged with timestamp and user context.

**Error behavior**: Missing opt-in in production raises SafetyBlock.

#### Scenario: Dry-run produces mock result

- GIVEN dry_run=True
- WHEN the demo stage completes
- THEN a mock deployment_result is emitted
- AND no real instance is created

**Acceptance**: Mock result has same schema as real result.

**Error behavior**: Real instance creation in dry-run is a test failure.
