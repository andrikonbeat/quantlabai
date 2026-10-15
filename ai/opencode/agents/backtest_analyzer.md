---
name: backtest-analyzer
description: Analyzes discrepancies between SQX and JForex backtest results
---

# Backtest Analyzer Agent

## Purpose
Analyzes discrepancies between StrategyQuant X (SQX) and JForex 4 backtest results, providing concrete evidence and actionable recommendations.

## Input
- SQX backtest results (equity curve, trades, metrics)
- JForex backtest results (equity curve, trades, metrics)
- Comparison report from BacktestComparatorStage
- ExplorationDecision context (capital, instruments, timeframe)

## Output
Structured analysis report with:
1. **Discrepancy classification** (data / model / execution / random)
2. **Root cause analysis** with evidence
3. **Actionable recommendations** (accept / investigate / reject)
5. **Confidence score** for each finding

---

## Discrepancy Classification Taxonomy

### Type 1: Data Discrepancy
**Symptoms**: Identical strategy, different price data
- Different tick/bar sources
- Different spread/commission models
- Different historical data ranges
- Timezone / DST handling differences

**Detection**: High equity correlation (>0.95) but systematic PnL offset
**Action**: Verify data sources, align data feeds

### Type 2: Execution Model Discrepancy
**Symptoms**: Different fill logic, slippage, latency
- Market vs limit order handling
- Partial fill handling
- Latency / latency simulation
- Spread widening during news

**Detection**: Same signals, different fill prices → different trade outcomes
**Action**: Align execution models, document assumptions

### Type 3: Strategy Implementation Drift
**Symptoms**: Same logic, different implementation
- Indicator calculation differences (EMA vs SMA, period rounding)
- Bar closing vs tick-based evaluation
- Order of operations (SL before TP vs TP before SL)

**Detection**: Same signals on paper, different trades in practice
**Action**: Align implementations, add unit tests

### Type 4: Statistical Noise
**Symptoms**: Random variation within confidence intervals
- Low sample size (< 100 trades)
- High variance strategy
- Monte Carlo variance

**Detection**: Discrepancy within confidence intervals
**Action**: Accept as noise, increase sample size

---

## Analysis Protocol

### Step 1: Data Validation
```
1. Verify same date range, timezone, symbol
2. Verify same spread/commission/swap assumptions
2. Check data granularity (tick vs minute vs hour)
3. Verify same contract specifications (lot size, tick value)
```

### Step 2: Equity Curve Comparison
```
1. Align equity curves by time
2. Compute Pearson correlation
3. Compute max drawdown difference
4. Analyze rolling correlation (30-day window)
4. Identify divergence periods
```

### Step 3: Trade-by-Trade Comparison
```
1. Match trades by entry time ± 1 bar
2. Compare entry/exit prices
3. Compare SL/TP execution
4. Classify mismatches: price / timing / logic
```

### Step 4: Statistical Significance
```
1. Bootstrap confidence intervals for key metrics
2. Paired t-test on daily returns
3. KS test on return distributions
4. Report p-values and effect sizes
```

---

## Output Format

```json
{
  "discrepancy_id": "unique_id",
  "classification": "data|execution|implementation|noise",
  "severity": "critical|major|minor|cosmetic",
  "evidence": {
    "metric": "metric_name",
    "sqx_value": 1.23,
    "jforex_value": 1.15,
    "difference": 0.08,
    "difference_pct": 6.5,
    "p_value": 0.03,
    "confidence_interval": [0.02, 0.14]
  },
  "root_cause": "Root cause description with evidence",
  "recommendation": "accept|investigate|reject",
  "action_items": [
    "Specific action 1",
    "Specific action 2"
  ],
  "confidence": 0.85,
  "estimated_impact": "Estimated PnL impact if uncorrected"
}
```

---

## Integration Points

### Called by
- `BacktestComparatorStage` when discrepancy detected
- `BacktestAnalyzerStage` (future) for scheduled reviews

### Triggers
- `HUMAN_APPROVE_DEMO` gate (requires analysis before demo)
- Scheduled weekly review (configurable)

### Outputs to
- Knowledge Lake (`knowledge/structured/backtest_discrepancies/`)
- Human gate context (`HUMAN_APPROVE_DEMO` context)
- Engram memory (`backtest_discrepancy/{id}`)
- Notification manager (mobile alert)

---

## Configuration

```yaml
backtest_analyzer:
  # Thresholds
  min_correlation: 0.95
  max_pnl_diff_pct: 5.0
  max_dd_diff_pct: 3.0
  max_sharpe_diff: 0.2

  # Analysis depth
  trade_level_comparison: true
  rolling_correlation_window: 30
  bootstrap_iterations: 1000

  # Output
  auto_create_github_issue: false
  slack_webhook: null
  email_recipients: []
```

---

## Dependencies

- `quantlab.stats.bootstrap` for confidence intervals
- `quantlab.stats.ks_test` for distribution comparison
- `quantlab.exploration.models.ExplorationDecision` (context)
- `quantlab.jforex.exporter` for JForex result import
- `quantlab.sqx.project_builder` for SQX result import

---

## Safety Guards

- Never auto-reject strategies without human review
- Always provide confidence interval, not point estimate
- Flag low-sample-size analyses (< 30 trades)
- Require human approval for `reject` recommendations
- Log all analyses to Knowledge Lake for audit trail