# Cost Pipeline Integration Specification

## Purpose

Integrates the cost engine into the multi-agent pipeline: CostInjectionStage, DSL costs section, and RetesterConfig cost parameters.

## Requirements

### Requirement: CostInjectionStage

The pipeline MUST provide CostInjectionStage as an abstract built-in stage that reads broker_profile from PipelineContext and writes cost_config to artifacts.

| Field | Value |
|-------|-------|
| name | `cost_injection` |
| requires | `["config.broker_profile"]` |
| provides | `["cost_config"]` |

#### Scenario: Stage injects cost config
- GIVEN PipelineContext with config.broker_profile set
- WHEN CostInjectionStage.execute(ctx) runs
- THEN ctx.artifacts["cost_config"] contains initialized CostEngine + CostCollector

### Requirement: DSL Costs Section

The ResearchConfig YAML MUST support an optional `costs` block with broker, commission_override, slippage_mode, and spread_config.

#### Scenario: Costs in campaign YAML
- GIVEN YAML with `costs: {broker: dukascopy, slippage: static}`
- WHEN parsed into ResearchConfig
- THEN costs field is populated with structured model

#### Scenario: No costs section
- GIVEN YAML without costs block
- WHEN parsed
- THEN costs = None (backward compatible)

### Requirement: Retester Cost Parameters

RetesterConfig MUST accept optional broker_profile and cost_config params for cost-aware backtesting via CFX injection.

#### Scenario: Cost-aware retester
- GIVEN RetesterConfig(strategy_id="s1", databanks=["EURUSD_H1"], broker_profile="ib")
- WHEN instantiated
- THEN broker_profile is stored
- AND cost_config is None by default
