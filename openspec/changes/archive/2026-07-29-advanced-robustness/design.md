# Design: Advanced Robustness

## Technical Approach

Create `sdk/quantlab/robustness/` package with five modules implementing circuit breaker, retry, resilient notification, health checking, and LLM-specific circuit breaking. Integrate with existing `AsyncSQXClient` circuit breaker pattern, `Notifier` adapters, `KnowledgeStore`, `LLMResearchAgent`, and `AutonomousMonitorDaemon`. All new code is additive — no existing files are deleted, only wrapped.

## Architecture Decisions

| Decision | Tradeoff | Decision |
|----------|----------|-----------|
| New `robustness/` package vs. scattering patterns across modules | Scattering creates duplication and inconsistency | New package centralizes all patterns, enables reuse across agents and notifiers |
| `await breaker.call(coro)` API over `async with breaker:` context manager | Context manager is more Pythonic but `call()` is simpler for one-off async calls | `call()` matches the existing `AsyncSQXClient` pattern and is easier to integrate into `LLMResearchAgent.generate_config()` |
| Bounded in-memory queue + JSONL persistence for `ResilientNotifier` | Pure in-memory loses notifications on crash; pure disk is slow | Bounded queue with JSONL persistence survives restarts; eviction prevents unbounded growth |
| `KnowledgeStoreHealthCheck` as standalone class vs. method on `KnowledgeStore` | Method on `KnowledgeStore` is simpler but mixes concerns | Standalone class keeps `KnowledgeStore` focused on storage; health check is a probe concern |
| LLM circuit breaker wraps `call_llm()` not the full `generate_config()` | Wrapping full method would also block fallback on non-LLM errors | Wrapping only `call_llm()` lets the fallback chain handle parse errors and other failures normally |

## Data Flow

```
LLMResearchAgent.generate_config()
  ├─ CircuitBreaker.call(call_llm) ──→ LLM API
  │   ├─ CLOSED → proceed normally
  │   ├─ OPEN → skip LLM, fall back to ResearchAgent immediately
  │   └─ HALF_OPEN → probe call; success→CLOSED, failure→OPEN
  └─ Fallback chain (unchanged)

AutonomousMonitorDaemon._compute_cycle()
  ├─ KnowledgeStoreHealthCheck.check() (cached, TTL=60s)
  │   ├─ HEALTHY → include in heartbeat
  │   └─ UNHEALTHY → dispatch STORE_UNHEALTHY WARNING alert
  └─ KnowledgeStore writes (buffered when circuit OPEN)

ResilientNotifier.send()
  ├─ RetryPolicy.retry(underlying.send) ──→ Notifier.send()
  │   ├─ Success → return
  │   └─ Fail after max_retries → enqueue in bounded JSONL queue
  └─ flush() → retry all queued notifications
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `sdk/quantlab/robustness/__init__.py` | Create | Package init, exports all public classes |
| `sdk/quantlab/robustness/circuit_breaker.py` | Create | `CircuitBreaker` (CLOSED/OPEN/HALF_OPEN), async-safe, `call()` method |
| `sdk/quantlab/robustness/retry_policy.py` | Create | `RetryPolicy` with exponential backoff, jitter, max_delay cap |
| `sdk/quantlab/robustness/resilient_notifier.py` | Create | `ResilientNotifier` wrapping any `Notifier` with retry + bounded JSONL queue |
| `sdk/quantlab/robustness/knowledge_health.py` | Create | `KnowledgeStoreHealthCheck` async probe with TTL-cached status |
| `sdk/quantlab/robustness/llm_circuit_breaker.py` | Create | `LLMCircuitBreaker` integrated with `LLMResearchAgent` fallback chain |
| `sdk/quantlab/agents/llm_research_agent.py` | Modify | Wrap `call_llm()` with `LLMCircuitBreaker`; skip LLM call when OPEN |
| `sdk/quantlab/knowledge/store.py` | Modify | Add `health_check()` method and write buffering when circuit is OPEN |
| `sdk/quantlab/agents/autonomous_monitor.py` | Modify | Integrate `KnowledgeStoreHealthCheck` into heartbeat and alert pipeline |
| `sdk/quantlab/gates/notifiers.py` | Modify | Add `ResilientNotifier` import/export for wrapping existing notifiers |

## Interfaces / Contracts

Five public classes in `sdk/quantlab/robustness/`: `CircuitBreaker` (async `call()`), `RetryPolicy` (async `retry()`), `ResilientNotifier` (wraps `Notifier` with retry + JSONL queue), `KnowledgeStoreHealthCheck` (async `check()` returning `HealthStatus`), and `LLMCircuitBreaker` (wraps `call_llm()` with circuit guard). See spec files for full method signatures and configuration parameters.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | CircuitBreaker state transitions (CLOSED→OPEN→HALF_OPEN→CLOSED) | pytest-asyncio, mock coroutines, verify state after threshold failures |
| Unit | RetryPolicy backoff + jitter | Verify delay bounds, max_delay cap, jitter range |
| Unit | ResilientNotifier retry + queue eviction | Mock notifier failures, verify queue persistence, flush delivery |
| Unit | KnowledgeStoreHealthCheck healthy/unhealthy paths | Mock KnowledgeStore write/read, verify HealthStatus |
| Unit | LLMCircuitBreaker short-circuit on OPEN | Mock LLM call, verify fallback triggered immediately when OPEN |
| Integration | LLMResearchAgent with circuit breaker | End-to-end: circuit opens after failures, fallback still works |
| Integration | ResilientNotifier with real SlackNotifier | Verify retry succeeds on transient failure, queue persists on crash |
| E2E | AutonomousMonitorDaemon with health check | Verify heartbeat includes store_status, STORE_UNHEALTHY alert dispatched |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. All changes are additive imports and wrapper patterns. Existing code paths remain untouched when the new robustness layer is not yet wired in. The `ResilientNotifier` and `LLMCircuitBreaker` are opt-in wrappers — existing notifiers and LLM calls continue to work without modification.

## Open Questions

- [ ] Queue file path for `ResilientNotifier` — default location and permissions need a decision
- [ ] `KnowledgeStoreHealthCheck` probe record namespace — should it use a dedicated directory or a sentinel filename?
- [ ] Whether `KnowledgeStore` write buffering should use an in-memory list or a persistent buffer for crash recovery
