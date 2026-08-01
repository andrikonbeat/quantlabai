# Knowledge Store Health Check Specification

## Purpose

Async health check verifying KnowledgeStore writability and readability via a probe record, providing status for the monitoring agent.

## Requirements

### Requirement: KnowledgeStoreHealthCheck

The system MUST provide a `KnowledgeStoreHealthCheck` class with an async `check()` method that writes a probe record, reads it back, and verifies integrity.

#### Scenario: Healthy store

- GIVEN a writable and readable KnowledgeStore
- WHEN `await health_check.check()` is called
- THEN a probe record is written to the store
- AND the same record is read back
- AND `check()` returns `HealthStatus.HEALTHY`

#### Scenario: Unwritable store

- GIVEN a KnowledgeStore with a read-only filesystem
- WHEN `await health_check.check()` is called
- THEN the write probe fails
- AND `check()` returns `HealthStatus.UNHEALTHY` with reason `write_failed`

#### Scenario: Unreadable store

- GIVEN a KnowledgeStore where the probe file exists but cannot be read
- WHEN `await health_check.check()` is called
- THEN the read probe fails
- AND `check()` returns `HealthStatus.UNHEALTHY` with reason `read_failed`

### Requirement: Health Status TTL

The system SHALL cache health status with a configurable TTL (default 60s) to avoid repeated I/O on every check call.

#### Scenario: Cached status within TTL

- GIVEN a health check that returned HEALTHY 30s ago (TTL=60s)
- WHEN `check()` is called again
- THEN the cached status is returned without I/O

#### Scenario: Stale cache expired

- GIVEN a health check that returned HEALTHY 90s ago (TTL=60s)
- WHEN `check()` is called again
- THEN a new probe write/read is performed

### Requirement: Probe Record Cleanup

The system MUST clean up probe records after a successful check.

#### Scenario: Probe record removed

- GIVEN a successful health check
- WHEN `check()` completes
- THEN the probe record is deleted from the store
