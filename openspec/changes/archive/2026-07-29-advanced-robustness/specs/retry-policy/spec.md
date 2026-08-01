# Retry Policy Specification

## Purpose

Configurable retry with exponential backoff, max retries, and jitter for transient I/O failures.

## Requirements

### Requirement: RetryPolicy Configuration

The system MUST provide a `RetryPolicy` class with `max_retries` (default 3), `base_delay` (default 1s), `max_delay` (default 60s), and `jitter` (default True).

#### Scenario: Default policy

- GIVEN a `RetryPolicy()` with no arguments
- WHEN a call fails
- THEN it retries up to 3 times with exponential backoff starting at 1s

### Requirement: Exponential Backoff

The system MUST apply exponential backoff: delay = min(base_delay * 2^attempt, max_delay).

#### Scenario: Backoff progression

- GIVEN `base_delay=1`, `max_delay=60`
- WHEN attempts 1, 2, 3 fail
- THEN delays are approximately 1s, 2s, 4s

### Requirement: Jitter

The system SHALL add random jitter to each backoff delay to avoid thundering herd. Jitter MUST be in range [0, delay * 0.3].

#### Scenario: Jitter applied

- GIVEN `base_delay=2`, `jitter=True`
- WHEN a retry is scheduled
- THEN the actual delay is between 2s and 2.6s

### Requirement: Max Delay Cap

The system MUST cap delay at `max_delay` regardless of exponential growth.

#### Scenario: Delay capped

- GIVEN `base_delay=1`, `max_delay=10`
- WHEN attempt 10 fails
- THEN delay is capped at 10s, not 512s

### Requirement: Async Retry

The system MUST support `await retry_policy.retry(coro)` for async coroutines.

#### Scenario: Async retry succeeds

- GIVEN a flaky async coroutine that fails twice then succeeds
- WHEN `await retry_policy.retry(coro)` is called with `max_retries=3`
- THEN the coroutine is retried and returns the successful result
