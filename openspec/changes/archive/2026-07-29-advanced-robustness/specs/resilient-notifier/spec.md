# Resilient Notifier Specification

## Purpose

Wrapper that applies RetryPolicy and persistent queue to existing Notifier adapters, preventing notification loss on transient failures.

## Requirements

### Requirement: ResilientNotifier Wrapper

The system MUST provide a `ResilientNotifier` class that wraps any `Notifier` instance and applies a `RetryPolicy` to each `send()` call.

#### Scenario: Happy path — notification succeeds

- GIVEN a `ResilientNotifier` wrapping a `SlackNotifier`
- WHEN `send(alert)` is called
- THEN the underlying notifier's `send()` is invoked once
- AND the alert is delivered

#### Scenario: Transient failure — retry succeeds

- GIVEN a `ResilientNotifier` wrapping a `SlackNotifier` with `max_retries=3`
- WHEN `send(alert)` is called and the notifier fails twice then succeeds
- THEN the alert is delivered on the 3rd attempt
- AND no notification is lost

### Requirement: Bounded Queue for Failed Notifications

The system MUST queue notifications that fail after all retry attempts into a bounded in-memory queue (default max 1000). Oldest entries are evicted when the queue is full.

#### Scenario: Queue eviction under sustained outage

- GIVEN a queue at max capacity (1000 entries)
- WHEN a notification fails all retries
- THEN the oldest queued notification is evicted
- AND the new failure is appended

### Requirement: Persistent Queue

The system SHALL persist queued notifications to a local file (JSONL) so they survive process restarts.

#### Scenario: Queue survives restart

- GIVEN 5 notifications in the persistent queue
- WHEN the process restarts
- THEN the 5 notifications are loaded from the queue file
- AND `flush()` attempts to deliver them

### Requirement: Flush Mechanism

The system MUST provide a `flush()` method that retries all queued notifications.

#### Scenario: Flush delivers queued alerts

- GIVEN 3 notifications in the queue after an outage
- WHEN `flush()` is called
- THEN all 3 are retried for delivery
- AND successful ones are removed from the queue
