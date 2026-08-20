# Pipeline YAML Reference

Reference guide for configuring the Multi-Agent Research System pipeline using YAML.

## Overview

The Multi-Agent Research System uses a declarative YAML configuration to define pipeline execution. The configuration specifies:
- Which agents to run and in what order
- Agent-specific configuration parameters
- Gate definitions and policies
- Memory and risk management settings
- Knowledge Lake and Engram integration points

## Configuration Structure

A complete pipeline configuration consists of these top-level sections:

```yaml
pipeline:
  # Pipeline metadata and stage definition
  
agents:
  # Agent definitions and configuration

gates:
  # Human gate definitions and approval policies

memory:
  # Memory and knowledge management settings

risk:
  # Risk management and position sizing parameters
```

## Pipeline Section

The `pipeline` section defines the execution flow:

```yaml
pipeline:
  name: "multi-agent-research"
  description: "Complete multi-agent research pipeline (16 stages non-orchestrated, 25 orchestrated, 27 with retest/optimize)"
  version: "1.0"
  stages:
    - name: research-agent
      type: research-agent
    - name: builder-agent
      type: builder-agent
    # ... additional stages
```

### Pipeline Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Unique pipeline identifier |
| `description` | string | no | Human-readable pipeline description |
| `version` | string | no | Schema version (default: "1.0") |
| `stages` | list | yes | Ordered list of stage configurations |

### Stage Configuration

Each stage in the `stages` list defines:

```yaml
- name: stage_name
  type: agent_type_name
  config:
    # Agent-specific parameters
```

#### Stage Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Unique stage identifier within pipeline |
| `type` | string | yes | Agent type (matches registry entry) |
| `config` | object | no | Agent-specific configuration parameters |

## Agents Section

The `agents` section provides detailed configuration for each agent type:

```yaml
agents:
  - name: research-agent
    type: research-agent
    config:
      lookback_period: 252
      min_observations: 50
      confidence_threshold: 0.95
      
  - name: builder-agent
    type: builder-agent
    config:
      sqx_path: "/opt/StrategyQuantX"
      export_format: "cfx"
      optimize_on_build: true
```

### Agent Configuration Reference

#### ResearchAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lookback_period` | integer | 252 | Days of historical data to analyze |
| `min_observations` | integer | 50 | Minimum data points for pattern detection |
| `confidence_threshold` | float | 0.95 | Minimum confidence for hypothesis generation |
| `signal_threshold` | float | 0.02 | Minimum signal strength to consider |

#### BuilderAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sqx_path` | string | `/opt/StrategyQuantX` | Path to StrategyQuant X installation |
| `export_format` | string | `cfx` | Export format (`cfx`, `xml`, `json`) |
| `optimize_on_build` | boolean | `true` | Whether to optimize during build |
| `max_bar_size` | string | `"D1"` | Maximum bar size for strategy |

#### StatisticsAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `confidence_level` | float | 0.95 | Confidence interval level |
| `monte_carlo_runs` | integer | 1000 | Number of Monte Carlo simulations |
| `test_normality` | boolean | `true` | Whether to test for normal distribution |
| `benchmark_asset` | string | `"SPY"` | Benchmark for relative performance |

#### ReviewerAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_sharpe` | float | 1.0 | Minimum acceptable Sharpe ratio |
| `max_drawdown` | float | 0.20 | Maximum allowed drawdown (20%) |
| `min_win_rate` | float | 0.50 | Minimum win rate (50%) |
| `profit_factor_min` | float | 1.5 | Minimum profit factor |
| `enable_walk_forward` | boolean | `true` | Enable walk-forward analysis |
| `wf_window` | integer | 252 | Walk-forward window size (days) |

#### PortfolioAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `optimization_method` | string | `mean_variance` | Optimization approach |
| `risk_aversion` | float | 1.0 | Risk aversion coefficient |
| `max_weight` | float | 0.20 | Maximum weight per strategy (20%) |
| `min_weight` | float | 0.01 | Minimum weight per strategy (1%) |
| `rebalance_frequency` | string | `monthly` | Portfolio rebalancing schedule |
| `transaction_cost` | float | 0.001 | Estimated transaction cost (0.1%) |

#### DeploymentAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `jforex_path` | string | `/opt/JForex` | Path to JForex installation |
| `java_version` | string | `11` | Target Java version |
| `package_name` | string | `com.mycompany.strategy` | Java package name |
| `generate_indicators` | boolean | `true` | Whether to generate custom indicators |
| `optimize_for_speed` | boolean | `false` | Optimize generated code for execution speed |

#### MonitoringAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `alert_threshold` | float | 0.20 | Drawdown threshold for alerts (20%) |
| `check_interval` | integer | 300 | Check interval in seconds (5 minutes) |
| `metrics_window` | integer | 252 | Rolling window for metrics calculation |
| `enable_email_alerts` | boolean | `false` | Enable email notifications |
| `webhook_url` | string | "" | URL for webhook notifications |

## Gates Section

The `gates` section defines human decision checkpoints:

```yaml
gates:
  - id: gate_research_complete
    name: "Research Complete"
    description: "Review initial hypotheses before building"
    timeout_hours: 24
    fallback: "continue"
    required_agents: [research-agent]
    
  - id: gate_pre_deployment
    name: "Pre-Deployment Review"
    description: "Final review before live deployment"
    timeout_hours: 48
    fallback: "abort"
    required_agents: [portfolio-agent]
```

### Gate Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique gate identifier |
| `name` | string | yes | Human-readable gate name |
| `description` | string | no | Gate purpose description |
| `timeout_hours` | integer | yes | Hours before timeout triggers fallback |
| `fallback` | string | yes | Action on timeout: `continue`, `abort`, `escalate` |
| `required_agents` | list | no | Agents that must complete before gate |

## Memory Section

The `memory` section configures knowledge management:

```yaml
memory:
  knowledge_root: "knowledge"
  agent_memory_enabled: true
  retention_days: 90
  engram_enabled: true
  compression: true
```

### Memory Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `knowledge_root` | string | `"knowledge"` | Root path for Knowledge Lake |
| `agent_memory_enabled` | boolean | `true` | Store agent memories |
| `retention_days` | integer | `90` | Days to retain agent memories |
| `engram_enabled` | boolean | `true` | Enable Engram persistence |
| `compression` | boolean | `false` | Compress stored data |

## Risk Section

The `risk` section manages position sizing and risk limits:

```yaml
risk:
  max_portfolio_risk: 0.02
  max_position_size: 0.10
  var_confidence: 0.95
  max_drawdown_limit: 0.15
  position_sizing_method: "kelly_fraction"
  max_leverage: 3.0
```

### Risk Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_portfolio_risk` | float | `0.02` | Maximum portfolio risk per trade (2%) |
| `max_position_size` | float | `0.10` | Maximum position size (10%) |
| `var_confidence` | float | `0.95` | VaR confidence level |
| `max_drawdown_limit` | float | `0.15` | Maximum allowable drawdown (15%) |
| `position_sizing_method` | string | `"kelly_fraction"` | Position sizing approach |
| `max_leverage` | float | `3.0` | Maximum portfolio leverage |

## Environment Variable Overrides

Configuration values can be overridden using environment variables with the pattern:

```
QUANTLAB_PIPELINE_<SECTION>_<FIELD>=value
```

Examples:
- `QUANTLAB_PIPELINE_AGENTS_0_CONFIG_LOOKBACK_PERIOD=500`
- `QUANTLAB_PIPELINE_GATES_0_TIMEOUT_HOURS=48`
- `QUANTLAB_PIPELINE_RISK_MAX_POSITION_SIZE=0.15`

## Complete Example

Here's a complete example configuration for a conservative research pipeline:

```yaml
pipeline:
  name: "conservative-research"
  description: "Low-frequency, high-conviction strategy research"
  version: "1.0"
  stages:
    - name: research-agent
      type: research-agent
    - name: builder-agent
      type: builder-agent
    - name: statistics-agent
      type: statistics-agent
    - name: reviewer-agent
      type: reviewer-agent
    - name: portfolio-agent
      type: portfolio-agent
    - name: deployment-agent
      type: deployment-agent
    - name: monitoring-agent
      type: monitoring-agent

agents:
  - name: research-agent
    type: research-agent
    config:
      lookback_period: 500
      min_observations: 100
      confidence_threshold: 0.99
      
  - name: builder-agent
    type: builder-agent
    config:
      sqx_path: "/opt/StrategyQuantX"
      export_format: "cfx"
      optimize_on_build: true

gates:
  - id: gate_after_builder
    name: "Post-Build Review"
    description: "Review compiled strategies before statistical analysis"
    timeout_hours: 12
    fallback: "continue"
    
  - id: gate_pre_deployment
    name: "Pre-Deployment Review"
    description: "Final safety check before live deployment"
    timeout_hours: 24
    fallback: "abort"

memory:
  knowledge_root: "knowledge"
  agent_memory_enabled: true
  retention_days: 365
  engram_enabled: true

risk:
  max_portfolio_risk: 0.01
  max_position_size: 0.05
  max_drawdown_limit: 0.10
  position_sizing_method: "kelly_fraction"
```

## Validation

Use the CLI command to validate your pipeline configuration:

```bash
quantlab pipeline validate config/pipeline.yaml
```

This checks:
- YAML syntax validity
- Required field presence
- Agent type validity (against registry)
- Gate configuration completeness
- Configuration value ranges

## See Also

- [Agent Reference](agents.md) - Detailed agent specifications
- [Running Multi-Agent Campaigns](../guides/running-campaigns.md) - Execution guide
- [Research Configuration Reference](../dsl/research-config.md) - DSL configuration