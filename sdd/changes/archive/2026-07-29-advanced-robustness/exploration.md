# Exploration: Advanced Robustness (Change 6)

**Date**: 2026-07-29
**Context**: QuantLab AI SDK — Phase 5 pipeline complete, roadmap Change 6
**Pipeline**: `research_llm|research → hypothesis_builder → refutation → [gate] → builder → statistics → review → portfolio → deploy → monitor`

---

## Current State

The codebase already has **scattered robustness patterns** across multiple modules, but no unified "Advanced Robustness" layer. Each critical path has its own ad-hoc approach to failure handling, with significant gaps between them.

### Pipeline Stages and Their Current Failure Handling

| Stage | Failure Handling | Pattern |
|-------|-----------------|---------|
| `research_llm` | LLMResearchAgent falls back to classic ResearchAgent on any error | Fallback |
| `hypothesis_builder` | LLM mode falls back to rule mode on any error (RB-6) | Fallback |
| `refutation` | Individual strategy failures caught and logged; other strategies continue | Graceful skip |
| `[gate]` | HumanGateOrchestrator applies configurable fallback (ABORT/CONTINUE/ESCALATE/HOLD) on timeout | Timeout + fallback |
| `builder` | BuilderAgent has configurable retry (default 2) + exponential backoff + fixture fallback | Retry + fallback |
| `statistics` | Returns empty/zero on insufficient data; NaN handling | Degraded output |
| `review` | Walk-forward degradation detection; overfitting flags | Monitoring |
| `portfolio` | No explicit error handling found in exploration | **Gap** |
| `deploy` | DeploymentAgent catches ImportError for jforex_deploy; simulates if unavailable | Fallback |
| `monitor` | MonitoringAgent returns "no_data" when no equity; autonomous monitor has health checks + reconnection | Graceful + health |

---

## Patrones de Robustez Existentes

### 1. Retry with Exponential Backoff

| Location | Max Retries | Backoff | Scope |
|----------|-------------|---------|-------|
| `PipelineRunner` (`pipeline/runner.py`) | Configurable (`max_retries`) | `retry_delay * 2^(attempt-1)` | Per-stage pipeline execution |
| `BuilderAgent` (`agents/builder_agent.py`) | 2 (configurable) | Exponential + fixture fallback | SQX dispatch |
| `ResultReader` (`readers/result_reader.py`) | 5 (configurable) | `backoff_base * 2^(retries-1)` (30s base) | Live equity streaming |
| `AutonomousMonitor` (`agents/autonomous_monitor.py`) | 5 (configurable) | `_reconnect_base * 2^(retries-1)` | Stream reconnection |
| `WebSearchProvider` (`data/news/web_search.py`) | 1 | None (single retry) | Web search |
| `OpenAI client` (inside `llm_research_agent.py`) | 2 (built-in) | N/A (SDK internal) | LLM API calls |

### 2. Fallback Patterns

| Location | Trigger | Fallback Action |
|----------|---------|-----------------|
| `LLMResearchAgent` | ImportError, API error, parse error, missing SDK | Falls back to classic `ResearchAgent` |
| `HypothesisBuilder` | LLM mode raises any exception | Falls back to `RuleMode` (RB-6) |
| `HumanGateOrchestrator` | Timeout or callback error | ABORT/CONTINUE/ESCALATE/HOLD based on policy |
| `KnowledgeStore` | Corrupted index file | Auto-rebuilds from filesystem |
| `KnowledgeStore` | Corrupted pipeline run YAML | Skips file, continues |
| `DeploymentAgent` | `jforex_deploy` not installed | Simulates deployment (dry-run) |
| `CfxReader` | Unknown complex section | Stores as raw XML passthrough |
| `MonitoringAgent` | No `live_equity` data | Returns empty results with "no_data" status |

### 3. Circuit Breaker

| Location | Implementation |
|----------|---------------|
| `AsyncSQXClient` (`phase4/http_client.py`) | Explicit circuit breaker with OPEN/HALF_OPEN/CLOSED states, failure counting, recovery timeout |
| **Other modules** | **None** — no circuit breaker pattern applied to LLM calls, notifiers, KnowledgeStore, or data providers |

### 4. Graceful Degradation

| Location | Pattern |
|----------|---------|
| `Notifiers` (`gates/notifiers.py`) | All `send()` methods catch exceptions and log warnings — notification failures never block the pipeline |
| `RefutationLayer` (`agents/refutation/__init__.py`) | Individual strategy failures caught per-strategy; other strategies continue (RF-4) |
| `KnowledgeStore` | `load_pipeline_runs()` skips corrupted files; `read_index()` auto-rebuilds on corruption |
| `MonitoringAgent` | Returns empty dicts and "no_data" gate decision when equity data is missing |
| `WebSearchProvider` | Returns empty list if `DDGS` is not installed |

### 5. Health Checks and Observability

| Location | Pattern |
|----------|---------|
| `AutonomousMonitor` (`agents/autonomous_monitor.py`) | Heartbeat tracking (3-miss stale detection), DAEMON_FAILURE CRITICAL alerts, stream reconnection with backoff |
| `TimeSeriesStore` (`knowledge/store.py`) | SQLite-based metrics, alerts, and heartbeat persistence |
| `MonitoringAgent` (`agents/monitoring_agent.py`) | Rolling metrics, regime detection, performance alert thresholds |
| `SQXDaemonManager` (`cli/daemon.py`) | `health_check()` verifies process is alive and responsive |
| `AsyncSQXClient` | `health_check()` endpoint check |

---

## Gaps Principales

### GAP 1: No Circuit Breaker for LLM Calls
The `LLMResearchAgent` uses the OpenAI client's built-in `max_retries=2` but has **no circuit breaker**. If the LLM provider is down, it retries twice and then falls back — but it doesn't learn from repeated failures. A circuit breaker would prevent wasted calls to a known-down provider and enable automatic recovery detection.

### GAP 2: No Retry for Notifier Failures
All notifiers (`WebhookNotifier`, `EmailNotifier`, `SlackNotifier`) catch exceptions and log warnings, but there's **no retry logic**. If a webhook endpoint is temporarily down, the notification is silently lost. The notifier failure is non-blocking (by design), but the information is lost.

### GAP 3: No Circuit Breaker for KnowledgeStore Writes
The `KnowledgeStore` has **no retry or circuit breaker** for writes. If the filesystem is full, the disk is failing, or there's a transient I/O error, writes fail without any recovery mechanism. This is critical because pipeline run history and agent memory persistence are essential for audit trails.

### GAP 4: No Health Check for KnowledgeStore
The `TimeSeriesStore` has heartbeat tracking, but the `KnowledgeStore` itself has **no health reporting**. There's no way to query whether the Knowledge Lake is writable, readable, or corrupted from the monitoring agent.

### GAP 5: No Graceful Degradation for ResultReader
`ResultReader.stream_live()` raises `ConnectionError` after max retries — it **doesn't degrade gracefully** (e.g., by returning stale data or switching to a backup source). The monitoring pipeline stops receiving equity data entirely.

### GAP 6: No Retry for Deployment Failures
The `DeploymentAgent` has **no retry logic** for live deployment failures. If `jforex_deploy.deploy()` fails, it returns a FAILED status without attempting recovery.

### GAP 7: No Circuit Breaker for External Data Providers
`YahooFinanceProvider`, `FredProvider`, and `WebSearchProvider` have **no circuit breaker**. They fail on each call independently without learning from repeated failures across the pipeline.

### GAP 8: No Centralized Error Budget / SLO Tracking
There's no concept of error budgets, SLOs, or availability tracking across the system. The monitoring agent tracks performance metrics but doesn't track **system reliability metrics** (e.g., "LLM availability this hour", "KnowledgeStore write success rate").

### GAP 9: No Unified Retry/Backoff Utility
Retry logic is implemented differently in each module (PipelineRunner, BuilderAgent, ResultReader, AutonomousMonitor, WebSearchProvider). There's **no shared retry utility** with consistent configuration, logging, and metrics.

### GAP 10: Portfolio Agent Has No Error Handling
The portfolio agent stage has no explicit error handling or fallback strategy discovered in the exploration — it's a gap in the pipeline's robustness chain.

---

## Recomendación de Alcance

### Prioridad Alta (MVP de Advanced Robustness)

1. **Circuit Breaker para LLM calls** — Wrap LLM calls with a circuit breaker that tracks failures, opens after N consecutive failures, and auto-recovers. Integrate with the existing `LLMResearchAgent` fallback chain.

2. **Retry con backoff para Notifiers** — Add retry logic (with exponential backoff, max 3 attempts) to all notifier `send()` methods. Notifications should be queued for retry rather than silently dropped.

3. **Circuit Breaker para KnowledgeStore writes** — Add a circuit breaker around KnowledgeStore write operations (especially `save_pipeline_run` and `store_agent_memory`). On open circuit, buffer to local cache and retry when closed.

4. **Health Check para KnowledgeStore** — Add a `health_check()` method to `KnowledgeStore` that verifies writability and readability. Integrate with the monitoring agent's alerting system.

### Prioridad Media (Pipeline Coverage)

5. **Retry para DeploymentAgent** — Add configurable retry with backoff for live deployment failures (max 2-3 retries).

6. **Circuit Breaker para data providers** — Apply circuit breaker pattern to `YahooFinanceProvider`, `FredProvider`, and `WebSearchProvider`.

7. **Graceful degradation para ResultReader** — Instead of raising after max retries, return stale data with a `STALE_DATA` warning, or switch to a simulated data source.

### Prioridad Baja (Observability)

8. **Métricas de robustez centralizadas** — Track retry counts, fallback triggers, circuit breaker state changes, and health check results in `TimeSeriesStore`.

9. **Utility de retry reutilizable** — Extract the retry + backoff pattern into a shared `quantlab.tools.retry` utility used across all modules.

---

## Archivos Clave Identificados

| Archivo | Rol |
|---------|-----|
| `sdk/quantlab/pipeline/runner.py` | Retry + backoff reference implementation |
| `sdk/quantlab/agents/llm_research_agent.py` | LLM fallback chain (needs circuit breaker) |
| `sdk/quantlab/gates/notifiers.py` | Notification adapters (needs retry) |
| `sdk/quantlab/gates/orchestrator.py` | Gate timeout + fallback logic |
| `sdk/quantlab/gates/models.py` | FallbackPolicy enum (ABORT, CONTINUE, ESCALATE, HOLD) |
| `sdk/quantlab/knowledge/store.py` | KnowledgeStore (needs circuit breaker + health check) |
| `sdk/quantlab/agents/monitoring_agent.py` | Monitoring + alerting (needs robustness metrics) |
| `sdk/quantlab/agents/autonomous_monitor.py` | Health checks + reconnection (reference pattern) |
| `sdk/quantlab/agents/builder_agent.py` | Retry + fixture fallback (reference pattern) |
| `sdk/quantlab/readers/result_reader.py` | Retry + backoff for streaming (needs graceful degradation) |
| `sdk/quantlab/agents/deployment_agent.py` | Deployment (needs retry) |
| `sdk/quantlab/cfx/reader.py` | CFX parsing with error hierarchy (reference for error types) |
| `sdk/quantlab/cfx/errors.py` | Error hierarchy (CfxNotFoundError, CfxCorruptError, etc.) |
| `sdk/quantlab/data/news/web_search.py` | Single retry pattern (needs circuit breaker) |
| `sdk/quantlab/agents/refutation/__init__.py` | Per-strategy error isolation (RF-4) |
| `sdk/quantlab/agents/hypothesis_builder/__init__.py` | LLM→rule fallback chain (RB-6) |

---

## Ready for Proposal

**Yes** — The exploration has identified clear patterns, gaps, and a prioritized scope. The next step is to create a proposal with specific requirements and scenarios for the Advanced Robustness change.
