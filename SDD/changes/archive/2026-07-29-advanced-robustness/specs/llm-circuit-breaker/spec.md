# LLM Circuit Breaker Specification

## Purpose

Circuit breaker for LLM calls integrated with the existing LLMResearchAgent fallback chain, preventing wasted API calls during outages.

## Requirements

### Requirement: LLM Circuit Breaker Integration

The system MUST wrap LLM API calls with a `CircuitBreaker` before the existing fallback chain in `LLMResearchAgent`.

#### Scenario: Circuit closed — LLM call proceeds

- GIVEN the LLM circuit breaker is in CLOSED state
- WHEN `LLMResearchAgent.execute()` is called
- THEN the LLM API call proceeds normally
- AND the fallback chain is not invoked

#### Scenario: Circuit open — fallback triggered immediately

- GIVEN the LLM circuit breaker is in OPEN state
- WHEN `LLMResearchAgent.execute()` is called
- THEN the LLM API call is NOT made
- AND the system falls back to classic `ResearchAgent` immediately
- AND a warning is logged noting the circuit is open

#### Scenario: Circuit half-open — probe call determines state

- GIVEN the LLM circuit breaker is in HALF_OPEN state
- WHEN `LLMResearchAgent.execute()` is called
- THEN a single LLM call is allowed as a probe
- IF the probe succeeds: circuit closes, LLM result is returned
- IF the probe fails: circuit re-opens, fallback to classic ResearchAgent

### Requirement: Failure Threshold Configuration

The system SHALL allow configuration of the LLM circuit breaker's `failure_threshold` (default 5) and `recovery_timeout` (default 30s).

#### Scenario: Custom threshold prevents premature opening

- GIVEN `failure_threshold=10`
- WHEN 7 consecutive LLM calls fail
- THEN the circuit remains CLOSED
- AND the 8th failure does NOT trigger fallback

### Requirement: Fallback Chain Preservation

The existing fallback chain (LLM → classic ResearchAgent) MUST be preserved. The circuit breaker is an additional guard that short-circuits the LLM call when open.

#### Scenario: Fallback chain intact

- GIVEN the LLM circuit breaker is CLOSED
- WHEN the LLM API returns a parse error
- THEN the fallback to classic ResearchAgent still occurs
- AND the circuit breaker records a failure (counting toward threshold)
