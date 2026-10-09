# Circuit Breaker Specification

## Purpose

General circuit breaker for protecting async I/O calls from cascading failures. Tracks failure counts across CLOSED/OPEN/HALF_OPEN states.

## Requirements

### Requirement: CircuitBreaker States

The system MUST implement a `CircuitBreaker` class with three states: `CLOSED`, `OPEN`, `HALF_OPEN`.

| State | Behavior |
|-------|----------|
| CLOSED | Calls pass through normally; failures increment counter |
| OPEN | Calls fail immediately without invoking the target |
| HALF_OPEN | A single probe call is allowed; success closes the circuit, failure re-opens |

#### Scenario: CLOSED → OPEN transition

- GIVEN circuit breaker in CLOSED state
- WHEN consecutive failures reach the configured threshold (default 5)
- THEN circuit transitions to OPEN
- AND subsequent calls fail immediately with `CircuitOpenError`

#### Scenario: OPEN → HALF_OPEN transition

- GIVEN circuit breaker in OPEN state
- WHEN recovery timeout elapses (default 30s)
- THEN circuit transitions to HALF_OPEN
- AND the next call is allowed through as a probe

#### Scenario: HALF_OPEN → CLOSED transition

- GIVEN circuit breaker in HALF_OPEN state
- WHEN the probe call succeeds
- THEN circuit transitions to CLOSED
- AND failure counter resets to 0

#### Scenario: HALF_OPEN → OPEN transition

- GIVEN circuit breaker in HALF_OPEN state
- WHEN the probe call fails
- THEN circuit transitions back to OPEN
- AND recovery timeout resets

### Requirement: Configurable Thresholds

The system SHALL allow configuration of `failure_threshold` (default 5), `recovery_timeout` (default 30s), and `half_open_max_calls` (default 1).

#### Scenario: Custom threshold

- GIVEN `failure_threshold=3`
- WHEN 3 consecutive calls fail
- THEN circuit opens

### Requirement: Async Support

The circuit breaker MUST support async call wrapping via `async with breaker:` or `await breaker.call(coro)`.

#### Scenario: Async call wrapping

- GIVEN an async coroutine `fetch_data()`
- WHEN `await breaker.call(fetch_data())` is called in CLOSED state
- THEN the coroutine executes normally and returns its result
