# Tasks: Advanced Robustness

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1100 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | CircuitBreaker + RetryPolicy | PR 1 | `pytest -q -k "circuit_breaker or retry_policy"` | N/A (unit) | Revert `sdk/quantlab/robustness/circuit_breaker.py` and `retry_policy.py` |
| 2 | ResilientNotifier + KnowledgeStoreHealthCheck | PR 2 | `pytest -q -k "resilient_notifier or knowledge_health"` | N/A (unit) | Revert `sdk/quantlab/robustness/resilient_notifier.py` and `knowledge_health.py` |
| 3 | LLMCircuitBreaker + agent integrations | PR 3 | `pytest -q -k "llm_circuit_breaker or llm_research"` | N/A (integration) | Revert `llm_circuit_breaker.py` and agent/store/monitor mods |
| 4 | Full test suite | PR 4 | `pytest tests/ -q --tb=short` | `python3 -m pytest tests/ -q --tb=short` | Revert all new test files |

## Phase 1: Foundation

- [x] 1.1 Create `sdk/quantlab/robustness/__init__.py` with package exports
- [x] 1.2 Create `sdk/quantlab/robustness/circuit_breaker.py` — `CircuitBreaker` (CLOSED/OPEN/HALF_OPEN), async `call()`, configurable `failure_threshold` (5), `recovery_timeout` (30s), `half_open_max_calls` (1)
- [x] 1.3 Create `sdk/quantlab/robustness/retry_policy.py` — `RetryPolicy` (max_retries=3, base_delay=1s, max_delay=60s, jitter=True), async `retry()`, exponential backoff with jitter
- [x] 1.4 Unit test: CircuitBreaker state transitions (CLOSED→OPEN→HALF_OPEN→CLOSED, custom thresholds, async call())
- [x] 1.5 Unit test: RetryPolicy backoff timing + max_retries exhaustion

## Phase 2: Notification & Health

- [x] 2.1 Create `sdk/quantlab/robustness/resilient_notifier.py` — `ResilientNotifier` wrapping any `Notifier`, retry via `RetryPolicy`, bounded JSONL queue (max 1000), `flush()`
- [x] 2.2 Create `sdk/quantlab/robustness/knowledge_health.py` — `KnowledgeStoreHealthCheck` async `check()`, TTL-cached status (60s), probe record cleanup
- [x] 2.3 Unit test: ResilientNotifier retry + queue eviction
- [x] 2.4 Unit test: KnowledgeStoreHealthCheck probe + result

## Phase 3: LLM Integration & Agent Wiring

- [ ] 3.1 Create `sdk/quantlab/robustness/llm_circuit_breaker.py` — `LLMCircuitBreaker` wrapping `call_llm()`, configurable threshold, fallback guard
- [ ] 3.2 Modify `sdk/quantlab/agents/llm_research_agent.py` — wrap `call_llm()` with `LLMCircuitBreaker`, skip LLM when OPEN, log warning
- [ ] 3.3 Modify `sdk/quantlab/knowledge/store.py` — add `health_check()`, write buffering when circuit OPEN, bounded buffer with eviction
- [ ] 3.4 Modify `sdk/quantlab/agents/autonomous_monitor.py` — integrate `KnowledgeStoreHealthCheck` into heartbeat, `STORE_UNHEALTHY` alert, `store_health` in status
- [ ] 3.5 Modify `sdk/quantlab/gates/notifiers.py` — add `ResilientNotifier` import/export

## Phase 4: Testing

- [x] 4.1 Write unit tests: `CircuitBreaker` state transitions (CLOSED→OPEN→HALF_OPEN→CLOSED, custom thresholds, async `call()`) — added recovery-specific tests (timeout reset, multiple cycles, HALF_OPEN→OPEN timer reset)
- [x] 4.2 Write unit tests: `RetryPolicy` backoff progression, jitter range, max_delay cap, async `retry()` — added jitter distribution, max_delay edge cases, zero max_retries, custom max_retries override, exception type preservation
- [x] 4.3 Write unit tests: `ResilientNotifier` retry success, queue eviction, JSONL persistence, `flush()` — added mixed success/failure queue tests, partial flush failures, queue_size tracking
- [x] 4.4 Write unit tests: `KnowledgeStoreHealthCheck` healthy/unhealthy/unreadable paths, TTL caching, probe cleanup — added unreadable store, TTL boundary, probe content verification, multiple check deduplication
- [x] 4.5 Write unit tests: `LLMCircuitBreaker` short-circuit on OPEN, fallback chain preservation, custom threshold — added fallback chain preservation, parse error recording, rate-limit error recording, HALF_OPEN probe success/failure
- [x] 4.6 Write unit tests: `KnowledgeStore` write buffering when circuit OPEN — expanded with comprehensive buffering tests (buffered write, replay on close, FIFO eviction, health_check replay, multiple writes in order, failed replay re-buffering)
- [x] 4.7 E2E test: full robustness pipeline (circuit breaker → retry → dispatch → buffer) — created `test_robustness_pipeline.py` with 6 E2E tests covering full pipeline coordination, retry exhaustion recovery, buffer flush on health check, persistence across restarts, circuit short-circuit, and all-components-integrated scenario
