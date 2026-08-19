# Agent Reference

Reference guide for all agents in the Multi-Agent Research System.

## Overview

The Multi-Agent Research System consists of specialized agents that collaborate through a pipeline orchestrated by the ResearchDirector. Each agent has a specific responsibility and communicates through well-defined contracts. The canonical pipeline built by `build_pipeline` contains 16 stage entries non-orchestrated (11 agent stages + 5 gate stages), 25 orchestrated (17 agent + 8 gate), and 27 with retest/optimize blocks (19 agent + 8 gate).

## Agent Overview

| Agent | Responsibility | Key Responsibilities |
|-------|----------------|----------------------|
| ResearchDirector | Pipeline Orchestration | Owns PipelineRunner, manages campaign lifecycle, handles human gate callbacks |
| ResearchAgent | Hypothesis Generation | Generates research hypotheses based on market observations and literature |
| BuilderAgent | Strategy Construction | Converts hypotheses to executable strategies via DSL → CFX → SQX |
| StatisticsAgent | Statistical Analysis | Calculates performance metrics, confidence intervals, Monte Carlo bands |
| ReviewerAgent | Strategy Evaluation | Evaluates strategies against quality criteria, suggests improvements |
| PortfolioAgent | Portfolio Construction | Builds optimal strategy portfolios using mean-variance optimization |
| DeploymentAgent | Deployment Preparation | Packages strategies for live trading, generates JForex/Java code |
| MonitoringAgent | Live Monitoring | Tracks deployed strategy performance, detects regime changes |

## Agent Details

### ResearchDirector

**File**: `sdk/quantlab/agents/research_director.py`

The ResearchDirector is the central orchestrator that:
- Owns and manages the PipelineRunner
- Constructs the canonical pipeline from ResearchConfig (16 non-orchestrated / 25 orchestrated / 27 with retest-optimize entries)
- Manages the complete campaign lifecycle (create → run → pause → resume → rollback)
- Handles human gate callbacks and timeout/failover logic
- Implements the objective optimization loop across iteration cycles

Key Methods:
- `build_pipeline(config)` - Constructs pipeline from configuration
- `execute_campaign(config)` - Runs a complete research campaign
- `run_campaign(config)` - Async campaign execution with monitoring
- `rollback_campaign(campaign_id)` - Rolls back a campaign to previous state
- `register_gate_callback(gate_id, callback)` - Registers human gate approval callbacks

### ResearchAgent

**File**: `sdk/quantlab/agents/research_agent.py`

The ResearchAgent generates testable hypotheses by:
- Analyzing market data for patterns and anomalies
- Reviewing academic literature and quantitative research
- Applying statistical tests to identify potential edges
- Formulating hypotheses with clear entry/exit logic

Outputs: HypothesisConfig objects that define:
- Entry conditions
- Exit conditions  
- Position sizing rules
- Risk management parameters

### BuilderAgent

**File**: `sdk/quantlab/agents/builder_agent.py`

The BuilderAgent transforms hypotheses into executable strategies:
- Converts HypothesisConfig to Domain Specific Language (DSL)
- Translates DSL to StrategyQuant X (SQX) compatible format (.cfx files)
- Manages the compilation process in SQX
- Exports compiled strategies for testing

Key Features:
- DSL → CFX translation with validation
- SQX integration for strategy compilation
- Error handling and compilation feedback
- Export strategies to SQX workspace

### StatisticsAgent

**File**: `sdk/quantlab/agents/statistics_agent.py`

The StatisticsAgent performs rigorous statistical analysis:
- Calculates standard performance metrics (Sharpe, Sortino, Calmar)
- Computes confidence intervals for all metrics
- Performs Monte Carlo simulation for robustness testing
- Generates equity curve bands and drawdown analysis
- Tests for overfitting using various statistical methods

Outputs: StatisticsReport with:
- Point estimates and confidence intervals
- Monte Carlo simulation results
- Risk-adjusted performance metrics
- Statistical significance tests

### ReviewerAgent

**File**: `sdk/quantlab/agents/reviewer_agent.py`

The ReviewerAgent evaluates strategies against multiple criteria:
- Performance consistency across market regimes
- Statistical significance of returns
- Drawdown and risk metrics
- Overfitting detection (walk-forward analysis, MC bands)
- Implementation feasibility and complexity

Outputs: ReviewDecision with:
- Approval/rejection recommendation
- Specific improvement suggestions
- Identified weaknesses and risks
- Suggested parameter adjustments

### PortfolioAgent

**File**: `sdk/quantlab/agents/portfolio_agent.py`

The PortfolioAgent constructs optimal strategy portfolios:
- Applies Modern Portfolio Theory (mean-variance optimization)
- Calculates efficient frontier and optimal allocations
- Implements risk parity and other diversification strategies
- Considers transaction costs and liquidity constraints
- Generates rebalancing schedules

Outputs: PortfolioAllocation with:
- Strategy weights and allocation percentages
- Expected portfolio return and risk
- Diversification metrics
- Rebalancing recommendations

### DeploymentAgent

**File**: `sdk/quantlab/agents/deployment_agent.py`

The DeploymentAgent prepares strategies for live deployment:
- Packages strategy code and indicators for JForex
- Generates Java classes from SQX exports
- Creates JForex-compatible strategy files
- Performs dry-run validation in simulated environment
- Packages all required files for deployment

Outputs: DeploymentPackage with:
- Compiled Java strategy files
- Custom indicator implementations
- Property files and configuration
- Deployment instructions

### MonitoringAgent

**File**: `sdk/quantlab/agents/monitoring_agent.py`

The MonitoringAgent tracks live strategy performance:
- Monitors real-time equity curves and drawdowns
- Calculates rolling performance metrics
- Detects regime changes and performance degradation
- Generates alerts for significant deviations
- Logs performance data to Knowledge Lake

Outputs: MonitoringReport with:
- Current performance vs. expected
- Drift detection signals
- Regime classification
- Alert notifications

## Agent Communication

Agents communicate through the PipelineContext which contains:
- **Inputs**: Data required from previous stages (declared in `requires`)
- **Outputs**: Data produced by the stage (declared in `provides`)
- **Metadata**: Additional context including Engram functions, configuration
- **Shared State**: Mutable data accessible to all stages

Each stage declares its input (`requires`) and output (`provides`) contracts, which are validated by the PipelineRunner before execution.

## Configuration

Agents are configured through the ResearchConfig and Pipeline YAML:

```yaml
agents:
  - name: research-agent
    type: research-agent
    config:
      lookback_period: 252
      min_observations: 50
      
  - name: builder-agent
    type: builder-agent
    config:
      sqx_path: /opt/StrategyQuantX
      export_format: cfx
```

See [Pipeline Configuration Reference](pipeline-config.md) for complete details.

## Extending Agents

To create a custom agent:
1. Inherit from `sdk.quantlab.pipeline.base.PipelineStage`
2. Implement the `process(context)` async method
3. Declare `requires` and `provides` contracts
4. Register the agent in `sdk/quantlab/pipeline/registry.py`
5. Reference in pipeline YAML using the agent type name

## See Also

- [Pipeline Configuration Reference](pipeline-config.md)
- [Pipeline Stages Reference](pipeline-stages.md)
- [Running Multi-Agent Campaigns](../guides/running-campaigns.md)