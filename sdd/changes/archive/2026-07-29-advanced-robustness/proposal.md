# Proposal: Advanced Robustness

## Intent

Scattered robustness patterns (retry, fallback, circuit breaker) exist across 6+ modules with no unified layer. Four critical gaps: LLM calls lack circuit breaking, notifiers lose notifications on transient failure, KnowledgeStore writes have no I/O protection, and KnowledgeStore has no health reporting for the monitoring agent.

## Scope

### In Scope
- CircuitBreaker class (CLOSED/OPEN/HALF_OPEN) in `quantlab.robustness`
- RetryPolicy class (configurable max_retries + exponential backoff)
- ResilientNotifier wrapping existing notifiers with retry + queue
- KnowledgeStoreHealthCheck (writability/readability verification)
- Circuit breaker for LLM calls integrated with LLMResearchAgent fallback
- KnowledgeStore write buffering when circuit is open
- MonitoringAgent integration with KnowledgeStore health checks

### Out of Scope
- ResultReader graceful degradation (stale data fallback)
- DeploymentAgent retry logic
- Circuit breaker for external data providers (YahooFinance, Fred, WebSearch)
- Centralized error budget / SLO tracking
- Unified retry utility extraction (deferred to refactor)

## Capabilities

### New Capabilities
- `circuit-breaker`: General circuit breaker with CLOSED/OPEN/HALF_OPEN states, configurable failure threshold and recovery timeout
- `retry-policy`: Configurable retry with exponential backoff, max retries, and jitter
- `resilient-notifier`: Wrapper applying retry + persistent queue to existing notifier adapters
- `knowledge-store-health`: Health check verifying KnowledgeStore writability and readability
- `llm-circuit-breaker`: Circuit breaker for LLM calls integrated with existing LLMResearchAgent fallback chain

### Modified Capabilities
- `llm-research`: LLMResearchAgent now uses circuit breaker before falling back to classic ResearchAgent
- `knowledge-storage`: KnowledgeStore exposes `health_check()` and buffers writes when circuit is open
- `autonomous-monitor`: MonitoringAgent integrates KnowledgeStore health status into its alerting pipeline

## Approach

Create `sdk/quantlab/robustness/` package with CircuitBreaker, RetryPolicy, ResilientNotifier, KnowledgeStoreHealthCheck, and LLM circuit breaker. Integrate with existing fallback chains in LLMResearchAgent and KnowledgeStore. Wire health checks into MonitoringAgent. Follow existing patterns from AsyncSQXClient (circuit breaker) and PipelineRunner (retry + backoff).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `sdk/quantlab/robustness/` | New | New package: CircuitBreaker, RetryPolicy, ResilientNotifier, KnowledgeStoreHealthCheck |
| `sdk/quantlab/agents/llm_research_agent.py` | Modified | Circuit breaker wraps LLM calls before fallback |
| `sdk/quantlab/knowledge/store.py` | Modified | Write buffering when circuit open; health_check() method |
| `sdk/quantlab/gates/notifiers.py` | Modified | ResilientNotifier wrapper adds retry + queue |
| `sdk/quantlab/agents/monitoring_agent.py` | Modified | Integrates KnowledgeStore health checks |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Circuit breaker state leaks across pipeline runs | Medium | Reset state per pipeline execution; persist only failure counts |
| Retry queue grows unbounded under sustained outage | High | Bounded queue with configurable max size; oldest entries evicted |
| KnowledgeStore health check adds monitoring latency | Low | Cache health status with TTL; async health check |
| LLM circuit breaker opens too aggressively | Medium | Configurable failure threshold (default 5); half-open probe |

## Rollback Plan

1. Remove `quantlab.robustness` import from all modules
2. Revert LLMResearchAgent to direct OpenAI client calls (existing fallback still works)
3. Remove ResilientNotifier wrapper; notifiers fall back to catch + log behavior
4. Remove KnowledgeStore health_check() and write buffering
5. Remove MonitoringAgent health integration
6. All changes are additive imports — no existing code deleted, only wrapped

## Dependencies

- None external; uses existing Python stdlib (threading, time)
- Depends on existing `AsyncSQXClient` circuit breaker pattern as reference implementation

## Success Criteria

- [ ] Circuit breaker opens after configurable consecutive failures and auto-recovers via half-open probe
- [ ] Notifier retry succeeds on transient failure (max 3 attempts, exp backoff)
- [ ] KnowledgeStore write buffering preserves data when circuit is open
- [ ] MonitoringAgent reports KnowledgeStore health status
- [ ] All existing tests pass (530+)
- [ ] New tests cover circuit breaker state transitions and retry backoff
