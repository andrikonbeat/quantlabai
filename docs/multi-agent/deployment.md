# Deployment Guide

Guide to production Agent Research System

Overview

The Multi-Agent Research System provides a complete end-to-end workflow for developing, testing, and deploying trading strategies to live trading environments. This guide covers the deployment process using the DeploymentAgent and related components.

## Deployment Overview

The deployment process consists of three main phases:

1. Strategy Preparation
2. Validation & Testing
3. Live Deployment

### Phase 1: Strategy Preparation

In this phase, the research pipeline generates strategies that pass all quality gates and are ready for deployment. The DeploymentAgent packages the strategy for the target platform.

Key Steps:
- Strategy export from StrategyQuant X (.cfx format)
- Java code generation from the exported strategy
- Custom indicator generation (if applicable)
- Dependency resolution and packaging
- Creation of deployment descriptor files

### Phase 2: Validation & Testing

Before deploying to live markets, strategies undergo rigorous validation and testing in simulated or paper trading environments.

Validation Steps:
- Syntax checking of generated Java code
- Compilation of strategy in isolated environment
- Backtesting with historical data to verify behavior matches expectations
- Walk-forward testing to assess robustness
- Monte Carlo simulation to evaluate statistical significance
- Paper trading for extended period (typically 2-4 weeks)

### Phase 3: Live Deployment

After successful validation, strategies are deployed to live trading environments via the JForex platform.

Deployment Steps:
- Transfer of compiled strategy files to JForex strategies directory
- Loading of custom indicators (if applicable)
- Strategy initialization and parameter configuration
- Initial Initialization and warm-up period
- Go live and begin monitoring

## DeploymentAgent

The DeploymentAgent is responsible for preparing strategies for deployment to various targets. Currently it supports JForex (for Dukascopy accounts) and generic strategy export.

### Key Responsibilities

1. Strategy Export
    - Converts StrategyQuant (.cfx) to Java source code
    - Generates custom indicators from SQX formulas
    - Handles dependencies and imports

2. Code Generation
    - Creates Java class implementing the strategy interface
    - Maps SQX parameters to Java fields with proper types and validation
    - Implements initialization, calculation, and cleanup methods

3. Resource Handling
    - Bundles required resources (indicators, files, etc.)
    - Creates property files for strategy configuration
    - Ensures correct file placement in JForex directory structure

4. Validation
    - Performs basic syntax validation on generated code
    - Checks for common errors (missing imports, syntax errors, etc.)
    - Optionally performs compilation test in isolated environment

### Configuration

The DeploymentAgent is configured via the `agents` section of the pipeline YAML configuration:

```yaml
agents:
  - name: deployment-agent
    type: deployment-agent
    config:
      jforex_path: "/opt/JForex"
      java_version: "11"
      package_name: "com.mycompany.strategy"
      generate_indicators: true
      optimize_for_speed: false
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|---------------------|-----------|-----------------|-----------------------|
| `jforex_path` | string | `"/opt/JForex"` | Path to JForex installation directory |
| `java_version` | string | `"11"` | Target Java version (e.g., `"11"`, `"17"`) |
| `package_name` | string | `"com.example.strategy"` | Java package name for generated code |
| `generate_indicators` | boolean | `true` | Whether to generate custom indicators from SQX formulas |
| `optimize_for_speed` | boolean | `false` | Optimize generated code for execution speed (may reduce readability) |

### Output

The DeploymentAgent produces a deployment package containing:

- `strategy.java`: The main strategy class implementing the strategy logic
- `indicators/` directory: Custom indicators (if generated)
- `strategy.properties` file for strategy configuration
- `README.md`: Documentation on how to install and use the strategy

## JForex Integration

For Dukascopy accounts, strategies are deployed to the JForex platform. The deployment process involves several steps:

### Step 1: Prepare the Deployment Package

Run the complete research pipeline to generate the strategy and run it through the DeploymentAgent. This creates the deployment package in the output directory specified in the agent configuration.

### Step 2: Transfer to JForex Strategies Directory

Copy the generated files to the JForex strategies directory:

```bash
cp -r ./output/deployment/strategy_name/* /opt/JForex/strategies/
```

### Step 3: Configure Custom Indicators (If Needed)

If your strategy uses custom indicators, copy them to the JForex indicators directory:

```bash
cp ./output/deployment/indicators/* /opt/JForex/strategies/indicators/
```

### Step 4: Load the Strategy in JForex

1. Launch JForex
2. Navigate to Strategies → Import
3. Select the strategy JAR file (if applicable) or navigate to the strategy folder
4. Configure strategy parameters via the GUI interface
5. Set up chart and timeframe as specified in strategy properties file
6. Click "Apply" to load the strategy

### Step 5: Monitor and Manage

After loading, monitor the strategy for proper operation:
- Check for any errors in the output console
- Verify that the strategy is executing as expected
- Monitor performance metrics in real-time
- Set up risk management parameters (stop-loss, position size, etc.) as needed

## Alternative Deployment Targets

While JForex is the primary target for the DeploymentAgent, the agent can be extended to support other platforms.

### Generic Strategy Export

The DeploymentAgent can export strategies in generic formats for use with other trading platforms or custom execution engines.

Configuration for generic export:

```yaml
agents:
  - name: deployment-agent
    type: deployment-agent
    config:
      export_format: "generic"
      output_directory: "./deploy"
```

### MetaTrader 5 Integration (Planned)

Future versions may include support for MetaTrader 5 via MetaTrader 5's MetaQuotes Language 5 (MQL5).

## Validation Strategies

Before deploying to live markets, consider these validation strategies to reduce risk:

### Walk-Forward Analysis

Instead of relying solely on in-sample backtesting, use walk-forward analysis to assess strategy robustness across different time periods and market conditions.

Process:
1. Split historical data into training and testing periods (e.g., 70%/30% 70%/30%)
2. Optimize strategy parameters on training data
3. Test optimized strategy on testing data
4. Roll forward the window and repeat
5. Analyze consistency of performance metrics across windows

### Monte Carlo Simulation

Monte Carlo simulation helps assess the statistical significance of strategy performance by creating many simulated equity curves based on the strategy's trade distribution.

Process:
1. Extract the trade distribution (profits, losses, trade durations) from historical backtest
2. Generate thousands of random sequences of trades from this distribution
3. Calculate performance metrics for each sequence
4. Compare the actual strategy performance to the distribution of simulated results
5. If the actual performance is in the top 5% of simulated results, the strategy is statistically significant at the 95% confidence level

### Out-of-Sample Testing

Reserve a portion of the most recent historical data for out-of-sample testing to avoid overfitting to historical patterns.

Process:
1. Split data so that the most recent 20-30% is reserved for out-of-sample testing
2. Develop and optimize strategy on older data (80-70%)
3. Test strategy on the reserved out-of-sample data
4. Only proceed to live deployment if out-of-sample performance is satisfactory

## Risk Management in Deployment

Effective risk management is crucial when deploying strategies to live markets. The following practices help manage risk:

### Position Sizing

Use appropriate position sizing based on account size, strategy risk profile, and market conditions.

Methods:
- Fixed Fractional: Risk a fixed percentage of account equity per trade (e.g., 1% per trade)
- Kelly Criterion: Calculate optimal fraction of capital to risk based on win rate and average win/loss ratio
- Volatility Adjusted: Adjust position size based on market volatility (smaller positions in high volatility environments)

### Stop-Loss and Take-Profit Levels

Always use stop-loss and take-profit orders to limit potential losses and lock in profits.

Guidelines:
- Set stop-loss based on volatility (e.g., 1x average true range) or technical levels (support, resistance, etc.)
- Set take-profit based on risk-reward ratio (typically 1:2 or better) or profit targets
- Consider using trailing stop-loss orders to protect profits in strong trends

### Maximum Drawdown Limits

Implement automatic position reduction or strategy shutdown when drawdown exceeds predefined thresholds.

Levels:
- Warning Level: Alert at 50% of maximum drawdown limit (e.g., alert at 6% if max drawdown is 12%)
- Action Level: Reduce position size by 50% at 75% of maximum drawdown limit
- Emergency Stop: Halt all trading at 90% of maximum drawdown limit

### Position Correlation Monitoring

Monitor correlation between positions to avoid unintended concentration risk.

Guidelines:
- Keep correlation between major positions below 0.7 (70%)
- Consider portfolio diversification when adding new strategies
- Use principal component analysis (PCA) to identify hidden correlations

## Monitoring and Maintenance

Post-deployment, ongoing monitoring and maintenance are essential for sustained strategy performance.

### Real-Time Monitoring

Monitor key metrics in real-time to detect issues early.

Metrics to Monitor:
- Equity Curve (real-time)
- Drawdown (current and maximum)
- Win Rate (rolling window)
- Profit Factor (rolling window)
- Average Trade Duration
- Trades per Day
- Slippage and Execution Quality

### Alerting and Notification

Set up alerts for critical conditions that require immediate attention.

Alert Types:
- Drawdown Alert: Trigger when drawdown exceeds threshold (e.g., 10%)
- Consecutive Losses Alert: Trigger after N consecutive losses (e.g., 5 losses)
- No Trade Alert: Trigger if no trades occur in specified time period (e.g., 24 hours)
- Volatility Spike Alert: Trigger when volatility increases significantly (e.g., 2x average)
- Connection Loss Alert: Trigger if connection to broker is lost

### Regular Review and Optimization

Schedule periodic reviews to assess strategy performance and make necessary adjustments.

Review Frequency:
- Daily: Quick check of essential metrics and health
- Weekly: More detailed analysis of performance trends and risk metrics
- Monthly: Comprehensive performance review including statistics, drawdown analysis, and strategy effectiveness
- Quarterly: Deep dive into strategy logic, assumptions, and market conditions (may involve re-optimization)

### Strategy Retirement

Know when to retire a strategy that is no longer effective.

Indicators for Retirement:
- Extended period of underperformance relative to benchmarks or expectations
- Structural changes in market dynamics that render the strategy ineffective
- Consistent violation of risk parameters (despite adjustments)
- Superior alternative strategies available with better risk-adjusted returns
- Technology obsolescence (if strategy relies on outdated technology or data sources)

## Troubleshooting

Common Issues and Solutions

### Compilation Errors

Issue: Generated Java code fails to compile
Solutions:
- Check for missing imports or incorrect package names
- Verify that all referenced classes and methods exist in the JDK and JForex API
- Look for syntax errors (missing semicolons, mismatched brackets, etc.)
- Check data types for compatibility (e.g., using int where double is required)

### Runtime Errors

Issue: Strategy throws exceptions during execution
Solutions:
- Examine the stack trace to identify the exact location and cause of the error
- Check for null pointer references or division by zero
- Validate array indices and bounds
- Look for issues with external resources (file I/O, network connections, etc.)

### Performance Issues

Issue: Strategy underperforms in live trading compared to backtesting results
Solutions:
- Check for overfitting (use walk-forward analysis and out-of-sample testing)
- Verify that market conditions are similar to those used in backtesting (regime change detection)
- Look for latency issues (order execution delay, slippage increase)
- Check for changes in broker rules or fees that affect profitability
- Review and adjust risk management parameters (position size, stop-loss, etc.)

### Connectivity Issues

Issue: Strategy cannot connect to broker or exchange data feeds
Solutions:
- Verify network connectivity and firewall settings
- Check broker status and maintenance schedules
- Ensure correct API credentials and permissions
- Look for rate limiting or connection quotas
- Consider using a VPS (Virtual Private Server) for more reliable connectivity

## Best Practices

### Version Control

Always use version control for your strategy code and configuration.

Practices:
- Use Git or another version control system
- Commit changes with meaningful commit messages
- Tag releases (e.g., strategy_v1.0, strategy_v1.1)
- Maintain separate branches for development, testing, and production
- Use pull requests for code review before merging into main branch

### Configuration Management

Manage strategy configuration externally to avoid hardcoding values in code.

Techniques:
- Use property files (as generated by the DeploymentAgent) for runtime configuration
- Implement hot-reloading of configuration (without restarting strategy)
- Store sensitive information (API keys, passwords) in secure vaults or environment variables
- Version control configuration files alongside code

### Logging and Debugging

Implement comprehensive logging to facilitate debugging and performance analysis.

Best Practices:
- Log important events (strategy start, trade execution, error occurrence)
- Use appropriate log levels (DEBUG, INFO, WARN, ERROR)
- Include timestamps and context (strategy name, version, trade ID)
- Rotate log files to prevent excessive disk usage
- Send critical logs to external monitoring services (optional)

### Performance Monitoring

Track strategy performance over time to identify trends and degradation

Metrics to Track:
- Cumulative Return
- Annualized Return
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Win Rate
- Profit Factor
- Average Trade Profit
- Average Trade Loss
- Expected Value per Trade

### Documentation

Maintain comprehensive documentation for your strategy to facilitate maintenance, troubleshooting, and knowledge transfer.

Include:
- Strategy Overview (what it does, strategy logic, intended use case)
- Parameter Documentation (what each parameter does, allowed values, default values, units)
- Installation and Setup Instructions
- Usage Guidelines (recommended market conditions, timeframes, position sizing guidelines, etc.)
- Maintenance Procedures (how to update parameters, troubleshoot issues, etc.)
- Version History (what changed in each version and why)
- Known Issues and Limitations (any known bugs or limitations of the strategy)

## Integration with Knowledge Lake

Deployment activities are recorded in the Knowledge Lake for audit, analysis, and learning.

Recorded Information:
- Deployment Timestamp
- Strategy Version
- Deployment Target (e.g., JForex, MetaTrader, etc.)
- Deployment Status (success, failure, partial success)
- Validation Results (backtest statistics, walk-forward results, etc.)
- Deployment Notes (any special instructions or considerations)
- Post-Deployment Performance (if monitored via integrated monitoring)

Access Methods:
- CLI Query: `quantlab knowledge query --type deployment --strategy-name "my-strategy"`
- API Endpoint: `GET /api/v1/knowledge/deployments/{strategy-name}`
- Knowledge Lake File Structure: `knowledge/deployments/{strategy_name}/deployment_timestamp.yaml`

## Safety Checks

Before deploying any strategy to live markets, perform these safety checks:

1. Code Review
    - Have another qualified developer review the generated code for correctness and security vulnerabilities
    - Pay special attention to risk management code (position sizing, stop-loss, etc.)
    - Verify that the strategy respects maximum position size limits and uses appropriate stop-loss mechanisms

2. Validation Checklist
    - [ ] Strategy compiles without errors or warnings
    - [ ] Generated code follows Java coding standards and conventions
    - [ ] Strategy behaves as expected in initial tests (demo or paper trading)
    - [ ] All external dependencies are correctly resolved and accessible
    - [ ] Strategy respects configured risk limits (position size, stop-loss, etc.)
    - [ ] Strategy does not contain any hardcoded market times or expiration dates (unless intentionally designed that way)
    - [ ] Strategy handles market closures and holidays appropriately
    - [ ] Strategy recovers gracefully from temporary connectivity issues
    - [ ] Strategy logs sufficient information for debugging and post-mortem analysis

3. Risk Assessment
    - Calculate maximum potential loss per trade (position size × stop-loss distance in price units × pip value)
    - Verify that maximum potential loss per trade is within acceptable limits (typically 1-2% of account equity per trade)
    - Calculate maximum potential daily loss based on maximum trades per day
    - Ensure adequate margin is available for worst-case scenario
    - Assess liquidity of traded instruments (avoid low-liquidity instruments during volatile periods)
    - Evaluate impact of slippage on strategy performance (especially important for high-frequency strategies)

4. Operational Readiness
    - Verify that all necessary dependencies are installed and available (JForex, JDK etc.)
    - Check that sufficient disk space is available for logging and temporary files
    - Confirm that the system has adequate memory and processing power for the strategy workload
    - Test the recovery process from unexpected shutdown (power loss, system crash, etc.)
    - Ensure that monitoring and alerting systems are functional and configured correctly

## Advanced Topics

### Dynamic Position Sizing

Instead of using fixed position sizing (as configured in the risk section), consider using dynamic position sizing that adjusts based on market conditions or strategy performance.

Approaches:
- Volatility-Based: Adjust position size inversely proportional to market volatility (smaller positions in high volatility environments)
- Performance-Based: Increase position size when strategy is performing well and decrease when performance deteriorates (requires careful risk management to avoid overconfidence)
- Regime-Dependent: Use different position sizing strategies for different market regimes (trending, ranging, high volatility, etc.)

### Strategy Rotation

Instead of running a single strategy continuously, consider rotating between multiple strategies based on performance or market conditions.

Approaches:
- Performance-Based: Allocate more capital to better-performing strategies and less to underperforming ones (requires regular rebalancing)
- Regime-Based: Switch to strategies better suited to current market conditions (e.g., trend-following strategies in bullish markets, mean-reversion reversal strategies in range-bound markets)
- Time-Based: Rotate strategies based on time of day or week (e.g., different strategies for market open, close, and overnight sessions)

### Portfolio Level Risk Management

Apply risk management at the portfolio level in addition to individual strategy risk management.

Techniques:
- Portfolio Diversification: Ensure strategies are not overly correlated (target correlation < 0.3 between major positions)
- Correlation-Based Weighting: Adjust strategy weights based on inverse correlation (less correlated strategies get higher weight)
- Risk Parity: Allocate capital such that each strategy contributes equally to portfolio risk
- Maximum Drawdown Limiting: Apply portfolio-level drawdown limits that trigger actions when overall portfolio drawdown exceeds threshold

## See Also

- [Agent Reference](agents.md) - Detailed agent specifications (see DeploymentAgent section)
- [Pipeline Configuration Reference](pipeline.md) - Complete pipeline YAML configuration reference
- [Running Multi-Agent Campaigns](../guides/running-campaigns.md) - Step-by-step guide for running and managing multi-agent research campaigns
- [JForex User Manual](https://www.dukascopy.com/support/manuals/) - Official JForex documentation (requires Dukascopy account access)
- [StrategyQuant User Manual](https://www.strategyquant.com/manuals/) - Official StrategyQuant documentation (requires license)