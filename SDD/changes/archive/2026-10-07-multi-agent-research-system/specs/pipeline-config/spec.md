# Pipeline Configuration Specification

## Purpose

Declarative YAML configuration for pipeline stage ordering, agent parameters, gate placement, and gate policies. Extends ResearchConfig DSL with pipeline-specific sections: agents[], gates[], memory{}, risk{}.

---

## Requirements

### Requirement: Pipeline YAML Structure

The system MUST define a PipelineConfig Pydantic model that loads from YAML with sections: pipeline, agents, gates, memory, risk.

#### Scenario: Minimal valid pipeline config
- GIVEN YAML with only pipeline.stages: [research, build, statistics, review, portfolio, deploy, monitor]
- WHEN PipelineConfig.load(yaml_path) called
- THEN config parsed, defaults applied for agents, gates, memory, risk

#### Scenario: Full config with all sections
- GIVEN YAML containing agents[] with per-agent config, gates[] with timeout/fallback, memory{} with engram topics, risk{} with limits
- WHEN PipelineConfig.load() called
- THEN all fields populated, validation passes

### Requirement: Agents Configuration

The agents section MUST allow per-agent parameter overrides: model, temperature, max_retries, timeout, custom_params.

#### Scenario: ResearchAgent custom parameters
- GIVEN agents.research: {max_hypotheses: 10, query_lookback_days: 730, confidence_threshold: 0.6}
- WHEN PipelineConfig.load() called
- THEN ResearchAgent receives config dict with these values
- AND defaults used for unspecified params

#### Scenario: StatisticsAgent Monte Carlo config
- GIVEN agents.statistics: {mc_simulations: 2000, mc_percentiles: [5, 50, 95], rolling_window: 100}
- WHEN PipelineConfig.load() called
- THEN StatisticsAgent uses 2000 sims, custom percentiles, 100-period window

### Requirement: Gates Configuration

The gates section MUST define all 5 gates with gate_id, timeout_hours, fallback, escalate_to, notification_channels.

#### Scenario: Custom gate timeout and fallback
- GIVEN gates.HUMAN_APPROVE_DEPLOY: {timeout_hours: 6, fallback: "ABORT", escalate_to: "devops@quantlab.ai"}
- WHEN PipelineConfig.load() called
- THEN HumanGateOrchestrator uses 6h timeout, ABORT fallback for deploy gate

#### Scenario: Gate notification channels configured
- GIVEN gates.HUMAN_REVIEW_PERFORMANCE: {notifications: ["slack", "email"], slack_channel: "#perf-alerts"}
- WHEN gate activates
- THEN notifications sent to both channels

### Requirement: Memory Configuration

The memory section MUST configure Engram integration: enabled, topic_prefix, retention_days, cross_agent_sharing.

#### Scenario: Agent memory enabled with custom topic prefix
- GIVEN memory: {enabled: true, topic_prefix: "quantlab/agent", retention_days: 365, cross_agent_sharing: true}
- WHEN PipelineConfig.load() called
- THEN Engram topics use prefix "quantlab/agent/{agent_name}/{campaign_id}"
- AND cross_agent_sharing allows ResearchDirector to read all agent memories

#### Scenario: Memory disabled for stateless run
- GIVEN memory: {enabled: false}
- WHEN PipelineConfig.load() called
- THEN no Engram writes, agents operate stateless

### Requirement: Risk Configuration

The risk section MUST define portfolio-level risk limits: max_portfolio_drawdown, max_strategy_correlation, max_single_strategy_weight, kelly_fraction_cap, var_confidence.

#### Scenario: Risk limits enforced by PortfolioAgent
- GIVEN risk: {max_portfolio_drawdown: 0.20, max_strategy_correlation: 0.7, max_single_strategy_weight: 0.4, kelly_fraction_cap: 0.25}
- WHEN PortfolioAgent.run() called
- THEN correlation analysis rejects pairs >0.7
- AND position sizing caps at kelly_fraction_cap
- AND portfolio drawdown monitored against 20% limit

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| PipelineConfig loads minimal and full YAML | Unit test: load both, assert fields populated |
| Agent config overrides merge with defaults | Unit test: partial config → assert defaults fill gaps |
| Gate config drives HumanGateOrchestrator behavior | Integration: custom timeout → assert timeout used |
| Memory config controls Engram topic naming | Unit test: assert topic_key format matches prefix |
| Risk limits passed to PortfolioAgent | Unit test: assert PortfolioAgent receives risk config |

---

## Non-Functional Requirements

- **Schema validation**: PipelineConfig YAML validated against JSON Schema (pipeline-config.schema.json)
- **Environment overrides**: Any YAML value overridable via ENV (e.g., QUANTLAB_PIPELINE_AGENTS_RESEARCH_MAX_HYPOTHESES)
- **Versioning**: config_version field for migration compatibility
- **Dependencies**: research-dsl (base), pydantic, pyyaml