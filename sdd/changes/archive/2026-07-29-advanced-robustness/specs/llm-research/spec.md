# Delta for llm-research

## MODIFIED Requirements

### Requirement: Error Handling — Fallback

If the LLM call fails (timeout, API error, parse error), the system MUST fall back to the classic `ResearchAgent` and log the failure. The LLM call MUST be wrapped by a `CircuitBreaker` before the fallback chain is invoked. When the circuit breaker is OPEN, the LLM call is skipped and the system falls back to classic ResearchAgent immediately.

(Previously: LLM call attempted regardless of circuit state; fallback only triggered on actual LLM failure)

#### Scenario: LLM timeout triggers fallback (unchanged)

- GIVEN the LLM API call exceeds the configured timeout
- WHEN LLMResearchAgent.execute() runs
- THEN classic ResearchAgent generates hypotheses instead
- AND a warning is logged

#### Scenario: Parse error in LLM response (unchanged)

- GIVEN the LLM returns malformed JSON
- WHEN parse_response() fails
- THEN fallback to classic ResearchAgent
- AND the error is logged for debugging

#### Scenario: Circuit open skips LLM call

- GIVEN the LLM circuit breaker is in OPEN state
- WHEN LLMResearchAgent.execute() is called
- THEN the LLM API call is NOT made
- AND the system falls back to classic ResearchAgent immediately
- AND a warning is logged noting the circuit is open

#### Scenario: Circuit closed — LLM call proceeds normally

- GIVEN the LLM circuit breaker is in CLOSED state
- WHEN LLMResearchAgent.execute() is called
- THEN the LLM API call proceeds normally
- AND the fallback chain is not invoked

### Requirement: Rate Limiting & Caching

The system MUST reuse `TokenBucket` for LLM API call rate limiting and `SqliteCache` for response caching, keyed by prompt hash. The circuit breaker failure counter is incremented on rate-limit errors and cache misses that result in actual API calls.

#### Scenario: Rate limited request (unchanged)

- GIVEN TokenBucket is exhausted
- WHEN an LLM API call is attempted
- THEN the system waits until tokens are available or returns cached response
- AND does not raise a rate-limit error to the caller

#### Scenario: Cached response hit (unchanged)

- GIVEN an identical prompt was sent within TTL
- WHEN the agent requests LLM completion
- THEN the cached response is returned without calling the API