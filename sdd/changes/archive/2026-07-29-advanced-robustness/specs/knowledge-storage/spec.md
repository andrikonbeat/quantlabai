# Delta for knowledge-storage

## ADDED Requirements

### Requirement: KnowledgeStore Health Check

The system MUST expose a `health_check()` method on `KnowledgeStore` that returns `HealthStatus` by writing and reading a probe record.

#### Scenario: Healthy store

- GIVEN a writable KnowledgeStore
- WHEN `await store.health_check()` is called
- THEN a probe record is written and read back
- AND `HealthStatus.HEALTHY` is returned

#### Scenario: Unwritable store

- GIVEN a read-only KnowledgeStore
- WHEN `await store.health_check()` is called
- THEN `HealthStatus.UNHEALTHY` is returned with reason `write_failed`

### Requirement: Write Buffering When Circuit Open

The system MUST buffer writes when the circuit breaker is OPEN instead of raising an error. Buffered writes are replayed when the circuit transitions to CLOSED.

#### Scenario: Write buffered while circuit open

- GIVEN the KnowledgeStore circuit breaker is OPEN
- WHEN a write operation is requested
- THEN the write is queued in a buffer (not rejected)
- AND the caller receives acknowledgment that the write is pending

#### Scenario: Buffered writes replayed on recovery

- GIVEN 3 writes buffered while circuit was OPEN
- WHEN the circuit transitions to CLOSED
- THEN all 3 buffered writes are replayed in order
- AND the buffer is cleared

#### Scenario: Bounded buffer eviction

- GIVEN the buffer at max capacity (default 1000 entries)
- WHEN a new write is buffered
- THEN the oldest buffered write is evicted
- AND the new write is appended

## MODIFIED Requirements

### Requirement: Metadata Indexing

The system MUST maintain a metadata index (`knowledge/index.yaml`) tracking top-level files per directory, creation timestamps, file sizes, and content hashes. The index MUST be human-readable YAML. The system MUST also expose `health_check()` as defined in the ADDED requirements.

(Previously: index.yaml only; no health reporting capability)

#### Scenario: Index updates after file addition (unchanged)

- GIVEN an initialized Knowledge Lake with an index
- WHEN a file is added to `raw/` and the index is updated
- THEN the index contains the new file's path, size, and SHA-256 hash

#### Scenario: Corrupted index is recoverable (unchanged)

- GIVEN a Knowledge Lake with a corrupted `index.yaml`
- WHEN the system attempts to read the index
- THEN the corruption is detected and a new index is rebuilt from the filesystem state