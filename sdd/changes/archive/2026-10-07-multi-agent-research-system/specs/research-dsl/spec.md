# Delta for Research DSL

## MODIFIED Requirements

### Requirement: DSL Parsing

The system MUST parse a valid YAML research definition into a structured Pydantic model. The DSL MUST support markets, timeframes, strategy building blocks, acceptance criteria, AND the new extensions: hypotheses[], iteration_config{}, gate_policies{}, agents{}, memory{}, risk{}.
(Previously: Only markets, timeframes, building blocks, acceptance criteria)

#### Scenario: Extended ResearchConfig parses successfully
- GIVEN a YAML file with all base fields plus hypotheses, iteration_config, gate_policies, agents, memory, risk
- WHEN the system parses the file
- THEN a structured Pydantic model is returned with all fields populated correctly
- AND nested models validated: Hypothesis, IterationConfig, GatePolicy, AgentConfig, MemoryConfig, RiskConfig

#### Scenario: Invalid extension field rejected
- GIVEN a YAML file with unknown field under `agents.research.unknown_param`
- WHEN the system validates the parsed model
- THEN a ValidationError is raised listing the unknown parameter

### Requirement: DSL Validation

The system MUST validate semantic constraints for new extensions: hypothesis confidence ∈ [0,1], iteration_config.max_iterations > 0, gate_policies timeout_hours > 0, risk limits within bounds.
(Previously: Only market/timeframe/building blocks/acceptance criteria validation)

#### Scenario: Hypothesis confidence out of range rejected
- GIVEN a YAML with hypothesis confidence=1.5
- WHEN the system validates the parsed model
- THEN a ValidationError is raised: "confidence must be in [0, 1]"

#### Scenario: Gate policy timeout zero rejected
- GIVEN a YAML with gate_policies.HUMAN_REVIEW_OBJECTIVES.timeout_hours=0
- WHEN the system validates
- THEN ValidationError: "timeout_hours must be > 0"

#### Scenario: Risk correlation limit validated
- GIVEN a YAML with risk.max_strategy_correlation=1.5
- WHEN the system validates
- THEN ValidationError: "max_strategy_correlation must be in [0, 1]"

## ADDED Requirements

### Requirement: Hypotheses Extension

The system MUST support `hypotheses` list in ResearchConfig with fields: id (str), description (str), confidence (float 0-1), parameters (dict), expected_metrics (dict).

#### Scenario: Multiple hypotheses with parameters
- GIVEN YAML with hypotheses:
  - id: "h1", description: "RSI<30 + BB lower", confidence: 0.7, parameters: {rsi_period: 14, bb_period: 20}
  - id: "h2", description: "MACD crossover", confidence: 0.5, parameters: {fast: 12, slow: 26, signal: 9}
- WHEN parsed
- THEN ResearchConfig.hypotheses contains 2 Hypothesis objects with all fields

### Requirement: Iteration Config Extension

The system MUST support `iteration_config` with: max_iterations (int > 0), convergence_threshold (float ≥ 0), min_improvement (float ≥ 0).

#### Scenario: Iteration config controls campaign loop
- GIVEN iteration_config: {max_iterations: 5, convergence_threshold: 0.02, min_improvement: 0.01}
- WHEN ResearchDirector runs campaign
- THEN max 5 iterations, stops if Sharpe improvement < 0.02 for 2 consecutive cycles

### Requirement: Gate Policies Extension

The system MUST support `gate_policies` mapping gate_id → {timeout_hours, fallback, required_approvers, notifications}.

#### Scenario: Gate policies drive HumanGateOrchestrator
- GIVEN gate_policies.HUMAN_APPROVE_DEPLOY: {timeout_hours: 6, fallback: "HOLD", notifications: ["slack"]}
- WHEN pipeline reaches deploy gate
- THEN gate uses 6h timeout, HOLD fallback, Slack notification

### Requirement: Agents Configuration Extension

The system MUST support `agents` mapping agent_name → AgentConfig with: model, temperature, max_retries, timeout_seconds, custom_params (dict).

#### Scenario: Per-agent parameters configurable
- GIVEN agents.research: {max_hypotheses: 10, query_lookback_days: 730}
- AND agents.statistics: {mc_simulations: 2000, rolling_window: 100}
- WHEN PipelineConfig loads
- THEN each agent receives its config dict

### Requirement: Memory Configuration Extension

The system MUST support `memory` with: enabled (bool), topic_prefix (str), retention_days (int), cross_agent_sharing (bool).

#### Scenario: Memory config controls Engram integration
- GIVEN memory: {enabled: true, topic_prefix: "quantlab/agent", retention_days: 365}
- WHEN ResearchDirector initializes
- THEN Engram topics use prefix, TTL set to 365 days

### Requirement: Risk Configuration Extension

The system MUST support `risk` with: max_portfolio_drawdown (float 0-1), max_strategy_correlation (float 0-1), max_single_strategy_weight (float 0-1), kelly_fraction_cap (float 0-1), var_confidence (float 0-1).

#### Scenario: Risk limits enforced by PortfolioAgent
- GIVEN risk: {max_portfolio_drawdown: 0.20, max_strategy_correlation: 0.7}
- WHEN PortfolioAgent runs
- THEN correlation > 0.7 rejected, portfolio drawdown monitored at 20%

---

## REMOVED Requirements

None.

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Extended ResearchConfig parses all new fields | Unit test: parse full YAML → assert all nested models |
| Validation rejects invalid hypothesis confidence | Unit test: confidence=1.5 → ValidationError |
| Validation rejects invalid gate timeout | Unit test: timeout_hours=0 → ValidationError |
| Validation rejects invalid risk correlation | Unit test: correlation=1.5 → ValidationError |
| Agents config passed to each agent | Integration: assert agent receives custom_params |
| Memory config controls Engram topic naming | Unit test: assert topic_key format |
| Risk config enforced by PortfolioAgent | Integration: correlation > 0.7 → rejected |

---