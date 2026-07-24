# Pipeline Configuration Reference

Complete reference for configuring the Multi-Agent Research System pipeline using YAML.

## Overview

The Multi-Agent Research System uses a hierarchical YAML configuration to define pipeline execution, agent behavior, gate policies, and system settings. This configuration enables flexible deployment across development, testing, and production environments.

## Configuration Structure

A complete configuration consists of these sections:

```yaml
pipeline:
  # Pipeline definition and stage ordering

agents:
  # Agent-specific configuration parameters

gates:
  # Human gate definitions and policies

memory:
  # Knowledge management and persistence settings

risk:
  # Risk management and position sizing parameters
```

## Pipeline Section

The `pipeline` section defines the execution flow and metadata:

```yaml
pipeline:
  name: "multi-agent-research"
  description: "Complete 17-stage research pipeline"
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
```

### Pipeline Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Unique pipeline identifier |
| `description` | string | no | Human-readable pipeline description |
| `version` | string | no | Schema version (default: "1.0") |
| `stages` | list | yes | Ordered list of stage configurations |

### Stage Configuration

Each stage defines:

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
| `max_hypotheses` | integer | 10 | Maximum hypotheses to generate per cycle |
| `min_expectancy` | float | 0.10 | Minimum expectancy (profit factor - 1) |

#### BuilderAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sqx_path` | string | `/opt/StrategyQuantX` | Path to StrategyQuant X installation |
| `export_format` | string | `cfx` | Export format (`cfx`, `xml`, `json`) |
| `optimize_on_build` | boolean | `true` | Whether to optimize during build |
| `max_bar_size` | string | `"D1"` | Maximum bar size for strategy |
| `use_in_sample_opt` | boolean | `true` | Use in-sample optimization during build |
| "optimization_iterations": integer | 1000 | Number of optimization iterations |

#### StatisticsAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `confidence_level` | float | 0.95 | Confidence interval level |
| `monte_carlo_runs` | integer | 1000 | Number of Monte Carlo simulations |
| `test_normality` | boolean | `true` | Whether to test for normal distribution |
| `benchmark_asset` | string | `"SPY"` | Benchmark for relative performance |
| "risk_free_rate": float | 0.02 | Risk-free rate for Sharpe ratio calculation |
| "include_tail_risks": boolean | true | Include tail risk metrics (Sortino, Calmar) |

#### ReviewerAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_sharpe` | float | 1.0 | Minimum acceptable Sharpe ratio |
| `max_drawdown` | float | 0.20 | Maximum allowed drawdown (20%) |
| `min_win_rate` | float | 0.50 | Minimum win rate (50%) |
| `profit_factor_min` | float | 1.5 | Minimum profit factor |
| `enable_walk_forward` | boolean | `true` | Enable walk-forward analysis |
| `wf_window` | integer | 252 | Walk-forward window size (days) |
| `wf_anchored` | boolean | false | Use anchored walk-forward analysis |
| "max_parameter_combinations": integer | 1000 | Maximum parameter combinations to test |

#### PortfolioAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `optimization_method` | string | `mean_variance` | Optimization approach (`mean_variance`, `risk_parity`, `max_sharpe`, `min_variance`) |
| `risk_aversion` | float | 1.0 | Risk aversion coefficient (higher = more risk averse) |
| `max_weight` | float | 0.20 | Maximum weight per strategy (20%) |
| `min_weight` | float | 0.01 | Minimum weight per strategy (1%) |
| `rebalance_frequency` | string | `monthly` | Portfolio rebalancing schedule (`daily`, `weekly`, `monthly`, `quarterly`) |
| `transaction_cost` | float | 0.001 | Estimated transaction cost (0.1%) |
| "lookback_period": integer | 252 | Historical period for covariance calculation |
| "min_history_days": integer | 60 | Minimum history required for inclusion |

#### DeploymentAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `jforex_path` | string | `/opt/JForex` | Path to JForex installation |
| `java_version` | string | `11` | Target Java version (`11`, `17`) |
| `package_name` | string | `com.mycompany.strategy` | Java package name for generated code |
| `generate_indicators` | boolean | `true` | Whether to generate custom indicators |
| `optimize_for_speed` | boolean | `false` | Optimize generated code for execution speed |
| "source_compatibility": string | "11" | Java source compatibility version |
| "target_compatibility": string | "11" | Java target compatibility version |

#### MonitoringAgent
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `alert_threshold` | float | 0.20 | Drawdown threshold for alerts (20%) |
| `check_interval` | integer | 300 | Check interval in seconds (5 minutes) |
| `metrics_window` | integer | 252 | Rolling window for metrics calculation |
| `enable_email_alerts` | boolean | `false` | Enable email notifications |
| `webhook_url` | string | "" | URL for webhook notifications |
| "performance_metrics": list | ["sharpe", "sortino", "max_drawdown"] | Metrics to track for alerts |
| "notification_cooldown": integer | 3600 | Seconds between similar notifications |

## Gates Section

The `gates` section defines human decision checkpoints:

```yaml
gates:
  - id: gate_research_complete
    name: "Research Complete"
    description: "Review initial hypotheses before building strategies"
    timeout_hours: 24
    fallback: "continue"
    required_agents: [research-agent]
    notification:
      email: ["research-team@example.com"]
      slack: "#quant-research"
    approval_criteria:
      - "At least 3 testable hypotheses generated"
      - "Each hypothesis has clear entry/exit rules"
      - "No look-ahead bias detected"
      
  - id: gate_after_builder
    name: "Post-Build Review"
    description: "Review compiled strategies before statistical analysis"
    timeout_hours: 12
    fallback: "continue"
    required_agents: [builder-agent]
    notification:
      email: ["strategy-dev@example.com"]
    approval_criteria:
      - "All strategies compiled successfully"
      - "No critical compilation warnings"
      - "Exported files match expected format"
```

### Gate Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique gate identifier |
| `name` | string | yes | Human-readable gate name |
| `description` | string | no | Gate purpose description |
| `timeout_hours` | integer | yes | Hours before timeout triggers fallback |
| `fallback` | string | yes | Action on timeout: `continue`, `abort`, `escalate` |
| `required_agents` | list | no | Agents that must complete before gate activates |
| `notification` | object | no | Alert configuration when gate activates |
| `approval_criteria` | list | no | Guidelines for human reviewers |

#### Notification Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | list | no | Email addresses for notifications |
| `slack` | string | no | Slack channel for notifications |
| `webhook` | string | no | Webhook URL for custom notifications |
| `escalation` | list | no | Escalation contacts if primary unresponsive |

## Memory Section

The `memory` section configures knowledge management:

```yaml
memory:
  knowledge_root: "knowledge"
  agent_memory_enabled: true
  retention_days: 90
  engram_enabled: true
  compression: false
  backup_enabled: true
  backup_interval_hours: 24
```

### Memory Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `knowledge_root` | string | `"knowledge"` | Root path for Knowledge Lake |
| `agent_memory_enabled` | boolean | `true` | Store agent memories in Knowledge Lake |
| `retention_days` | integer | `90` | Days to retain agent memories |
| `engram_enabled` | boolean | `true` | Enable Engram persistence for learning |
| `compression` | boolean | `false` | Compress stored data to save space |
| `backup_enabled` | boolean | `true` | Enable automatic backups |
| `backup_interval_hours` | integer | `24` | Hours between backups |
| "indexing_enabled": boolean | true | Enable search indexing for faster queries |
| "max_memory_size_mb": integer | 1024 | Maximum Engram storage size in MB |

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
  stop_loss_enabled: true
  take_profit_enabled: true
```

### Risk Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_portfolio_risk` | float | `0.02` | Maximum portfolio risk per trade (2%) |
| `max_position_size` | float | `0.10` | Maximum position size (10% of equity) |
| `var_confidence` | float | `0.95` | Value-at-Risk confidence level |
| `max_drawdown_limit` | float | `0.15` | Maximum allowable drawdown (15%) |
| `position_sizing_method` | string | `"kelly_fraction"` | Position sizing approach (`fixed_fractional`, `kelly_fraction`, `volatility_adjusted`, `equal_weight`) |
| `max_leverage` | float | `3.0` | Maximum portfolio leverage |
| `stop_loss_enabled` | boolean | `true` | Enable stop-loss orders |
| `take_profit_enabled` | boolean | `true` | Enable take-profit orders |
| "default_stop_loss_pct": float | 0.05 | Default stop-loss percentage (5%) |
| "default_take_profit_pct": float | 0.10 | Default take-profit percentage (10%) |
| "correlation_limit": float | 0.7 | Maximum correlation between positions |

## Environment Variable Overrides

Configuration values can be overridden using environment variables with the pattern:

```
QUANTLAB_PIPELINE_<SECTION>_<FIELD>=value
QUANTLAB_<SECTION>_<FIELD>=value
```

### Examples

```bash
# Pipeline section
QUANTLAB_PIPELINE_NAME="production-research"
QUANTLAB_PIPELINE_VERSION="2.0"

# Agents section - array indexing starts at 0
QUANTLAB_PIPELINE_AGENTS_0_CONFIG_LOOKBACK_PERIOD=500
QUANTLAB_PIPELINE_AGENTS_1_CONFIG_SQX_PATH="/opt/SQX"

# Gates section
QUANTLAB_PIPELINE_GATES_0_TIMEOUT_HOURS=48
QUANTLAB_PIPELINE_GATES_1_FALLBACK="abort"

# Memory section
QUANTLAB_MEMORY_KNOWLEDGE_ROOT="/mnt/data/knowledge"
QUANTLAB_MEMORY_ENGRAM_ENABLED="false"

# Risk section
QUANTLAB_RISK_MAX_POSITION_SIZE=0.05
QUANTLAB_RISK_MAX_LEVERAGE=5.0
```

### Special Array Indexing Notes

For array-based sections (agents, gates), use zero-based indexing:
- First agent: `QUANTLAB_PIPELINE_AGENTS_0_*`
- Second agent: `QUANTLAB_PIPELINE_AGENTS_1_*`
- First gate: `QUANTLAB_PIPELINE_GATES_0_*`
- Second gate: `QUANTLAB_PIPELINE_GATES_1_*`

## Complete Example Configuration

Here's a complete example configuration for a production research pipeline:

```yaml
pipeline:
  name: "quantitative-research-production"
  description: "Institutional-grade research pipeline for systematic strategy development"
  version: "2.0"
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
      signal_threshold: 0.015
      max_hypotheses: 15
      min_expectancy: 0.15
      
  - name: builder-agent
    type: builder-agent
    config:
      sqx_path: "/opt/StrategyQuantX"
      export_format: "cfx"
      optimize_on_build: true
      max_bar_size: "W1"  # Weekly bars for longer-term strategies
      use_in_sample_opt: true
      optimization_iterations: 2000
      
  - name: statistics-agent
    type: statistics-agent
    config:
      confidence_level: 0.99
      monte_carlo_runs: 2000
      test_normality: true
      benchmark_asset: "SPY"
      risk_free_rate: 0.025
      include_tail_risks: true
      
  - name: reviewer-agent
    type: reviewer-agent
    config:
      min_sharpe: 1.5
      max_drawdown: 0.15
      min_win_rate: 0.52
      profit_factor_min: 1.8
      enable_walk_forward: true
      wf_window: 252
      wf_anchored: false
      max_parameter_combinations: 5000
      
  - name: portfolio-agent
    type: portfolio-agent
    config:
      optimization_method: "risk_parity"
      risk_aversion: 1.5
      max_weight: 0.15
      min_weight: 0.02
      rebalance_frequency: "weekly"
      transaction_cost: 0.0005
      lookback_period: 252
      min_history_days: 90
      
  - name: deployment-agent
    type: deployment-agent
    config:
      jforex_path: "/opt/JForex"
      java_version: "11"
      package_name: "com.quantlab.strategy"
      generate_indicators: true
      optimize_for_speed: true
      source_compatibility: "11"
      target_compatibility: "11"
      
  - name: monitoring-agent
    type: monitoring-agent
    config:
      alert_threshold: 0.15
      check_interval: 300
      metrics_window: 252
      enable_email_alerts: true
      webhook_url: "https://hooks.example.com/quantlab-alerts"
      performance_metrics: ["sharpe", "sortino", "max_drawdown", "win_rate"]
      notification_cooldown: 1800

gates:
  - id: gate_research_complete
    name: "Research Complete"
    description: "Review initial hypotheses before building strategies"
    timeout_hours: 24
    fallback: "continue"
    required_agents: [research-agent]
    notification:
      email: ["research-team@quantlab.com"]
      slack: "#quant-research"
      escalation: ["head-of-research@quantlab.com"]
    approval_criteria:
      - "At least 5 testable hypotheses generated"
      - "Each hypothesis has clear economic rationale"
      - "No look-ahead bias or data sponing detected"
      - "All hypotheses meet minimum expectancy threshold"
      
  - id: gate_after_builder
    name: "Post-Build Review"
    description: "Review compiled strategies before statistical analysis"
    timeout_hours: 12
    fallback: "continue"
    required_agents: [builder-agent]
    notification:
      email: ["strategy-dev@quantlab.com"]
      slack: "#quant-strategy-dev"
    approval_criteria:
      - "All strategies compiled successfully"
      - "Compilation warnings addressed and documented"
      - "Exported files include all required components"
      - "Custom indicators generated and validated"
      
  - id: gate_after_statistics
    name: "Statistical Validation"
    description: "Evaluate statistical validity of strategy performance"
    timeout_hours: 12
    fallback: "continue"
    required_agents: [statistics-agent]
    notification:
      email: ["quant-analyst@quantlab.com"]
      slack: "#quant-analysis"
    approval_criteria:
      - "Sharpe ratio > 1.0 with 95% confidence"
      - "Profit factor > 1.5"
      - "Max drawdown < 20% with 80% confidence"
      - "No significant serial dependence in returns"
      - "Strategy robust to regime changes"
      
  - id: gate_after_reviewer
    name: "Quality Review"
    description: "Assess overall strategy quality and implementation feasibility"
    timeout_hours: 24
    fallback: "continue"
    required_agents: [reviewer-agent]
    notification:
      email: ["senior-research@quantlab.com"]
      slack: "#quant-review"
    approval_criteria:
      - "Strategy meets all qualitative quality criteria"
      - "Implementation complexity justified by expected returns"
      - "Strategy robust across multiple market regimes"
      - "Capacity limits well understood and documented"
      
  - id: gate_pre_deployment
    name: "Pre-Deployment Safety Check"
    description: "Final validation before live deployment"
    timeout_hours: 36
    fallback: "abort"
    required_agents: [portfolio-agent, deployment-agent]
    notification:
      email: ["risk-management@quantlab.com", "trading-desk@quantlab.com"]
      slack: "#risk-management"
      escalation: ["cro@quantlab.com", "cto@quantlab.com"]
    approval_criteria:
      - "Portfolio meets all risk limits and constraints"
      - "Deployable package generated and validated"
      - "All necessary documentation completed"
      - "Operational readiness confirmed"
      - ready"

memory:
  knowledge_root: "/mnt/data/knowledge"
  agent_memory_enabled: true
  retention_days: 365
  engram_enabled: true
  compression: true
  backup_enabled: true
  backup_interval_hours: 6
  indexing_enabled: true
  max_memory_size_mb: 4096

risk:
  max_portfolio_risk: 0.01
  max_position_size: 0.05
  var_confidence: 0.99
  max_drawdown_limit: 0.10
  position_sizing_method: "kelly_fraction"
  max_leverage: 4.0
  stop_loss_enabled: true
  take_profit_enabled: true
  default_stop_loss_pct: 0.03
  default_take_profit_pct: 0.08
  correlation_limit: 0.65
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
- Configuration value ranges and types
- Referential integrity (required agents exist)

## See Also

- [Agent Reference](../multi-agent/agents.md) - Detailed agent specifications
- [Multi-Agent Pipeline Reference](../multi-agent/pipeline.md) - Pipeline stage details
- [Running Multi-Agent Campaigns](../guides/running-campaigns.md) - Execution guide
- [Human Gates Guide](../multi-agent/gates.md) - Gate configuration and usage