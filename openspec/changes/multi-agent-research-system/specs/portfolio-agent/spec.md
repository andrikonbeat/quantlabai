# Portfolio Agent Specification

## Purpose

Orchestrates Portfolio Master (genetic portfolio builder) via portfolio-master module, runs correlation analysis, applies risk allocation (Kelly/mean-variance), composes multi-strategy portfolio CFX, and executes walk-forward optimization via optimizer-automation.

---

## Requirements

### Requirement: Portfolio Master Orchestration

The system MUST generate Portfolio Master CFX from selected strategies, execute genetic optimization via sqcli, and extract selected strategies.

#### Scenario: Portfolio CFX generated and optimized
- GIVEN selected_strategies=["strat_1", "strat_2", "strat_3"] with CFX paths
- WHEN PortfolioAgent.run_portfolio_master() called
- THEN PortfolioMaster.build_cfx() creates CFX with AutomaticPortfolioBuilder (generations=50, pop=200)
- AND PortfolioMaster.run() executes sqcli lifecycle
- AND extract_selected_strategies() returns ["strat_1", "strat_3"] (strat_2 dropped)

#### Scenario: Empty selection handled
- GIVEN genetic run selects 0 strategies
- WHEN PortfolioAgent.run_portfolio_master() called
- THEN portfolio_result.selected_strategies = [], portfolio_cfx = None, warning logged

### Requirement: Correlation Analysis

The system MUST compute pairwise correlation matrix of strategy returns and identify highly correlated clusters.

#### Scenario: Correlation matrix computed
- GIVEN 5 strategies with daily returns (aligned timestamps)
- WHEN PortfolioAgent.analyze_correlation() called
- THEN correlation_matrix 5x5 with values in [-1, 1], diagonal=1.0
- AND clusters identified: groups with corr>0.7

#### Scenario: High correlation cluster triggers diversification
- GIVEN strategies A,B,C have pairwise corr>0.8
- WHEN PortfolioAgent.analyze_correlation() called
- THEN cluster_detected = ["A","B","C"], recommendation = "Select 1 from cluster, diversify"

### Requirement: Risk Allocation (Kelly / Mean-Variance)

The system MUST compute optimal position sizes using Kelly criterion and mean-variance optimization.

#### Scenario: Kelly allocation computed
- GIVEN strategy with win_rate=0.55, avg_win=1.2R, avg_loss=1.0R
- WHEN PortfolioAgent.compute_kelly_allocation() called
- THEN kelly_fraction = 0.55 - (0.45/1.2) ≈ 0.175, capped at max_kelly=0.25
- AND position_size = account_equity * kelly_fraction

#### Scenario: Mean-variance optimization
- GIVEN 3 strategies with returns, covariance matrix
- WHEN PortfolioAgent.optimize_mean_variance(target_return=0.15) called
- THEN weights sum to 1.0, portfolio variance minimized, return ≥ target
- AND no weight < min_weight (default 0.05) or > max_weight (default 0.5)

### Requirement: Portfolio CFX Composition

The system MUST compose final portfolio CFX using portfolio-composer with selected strategies and allocated weights.

#### Scenario: Portfolio CFX includes all selected strategies with weights
- GIVEN selected=["s1","s2"], weights={"s1":0.6, "s2":0.4}
- WHEN PortfolioAgent.compose_portfolio_cfx() called
- THEN CFX contains both strategies with correct weight allocation
- AND PortfolioSettings: RebalancingPeriod=Monthly, FitnessFunction=NetProfit

### Requirement: Walk-Forward Optimization

The system MUST execute walk-forward optimization via optimizer-automation for robustness validation.

#### Scenario: WF optimization runs and aggregates OOS stats
- GIVEN portfolio CFX, WF config: 10 cycles, 70% IS / 30% OOS
- WHEN PortfolioAgent.run_walk_forward() called
- THEN optimizer_automation.walk_forward() executes 10 cycles
- AND aggregate_wf_cycles() returns AggregateStats for OOS Sharpe, PF, MDD

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| Portfolio Master CFX valid for sqcli | Integration: build → validate via cfx-editor |
| Correlation matrix symmetric, diagonal=1 | Unit test: assert matrix properties |
| Kelly fraction formula correct | Unit test: known win/loss → assert kelly ≈ 0.175 |
| Mean-variance weights sum to 1, respect bounds | Unit test: assert sum=1, min≤w≤max |
| WF aggregation uses OOS stats only | Unit test: mock cycles, assert IS excluded |

---

## Non-Functional Requirements

- **Dependencies**: portfolio-master, portfolio-composer, optimizer-automation, stats-aggregation
- **Performance**: Correlation matrix O(n²) < 100ms for 50 strategies; WF optimization async
- **Risk controls**: Max position size, max sector exposure, max correlation concentration enforced