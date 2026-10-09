# Delta for Portfolio Master

## MODIFIED Requirements

### Requirement: Portfolio Master CFX Generation

The system MUST generate a valid Portfolio Master CFX with genetic algorithm configuration, supporting multi-strategy correlation-aware selection and risk budgeting constraints.
(Previously: Basic CFX with generations, population, strategy count)

#### Scenario: CFX includes correlation constraints
- GIVEN PortfolioMasterConfig with strategies=["s1","s2","s3"], max_correlation=0.7
- WHEN `PortfolioMaster.build_cfx(config)` is called
- THEN CFX contains `<AutomaticPortfolioBuilder>` with CorrelationFilter section
- AND CorrelationFilter.MaxCorrelation = 0.7

#### Scenario: CFX includes risk budgeting parameters
- GIVEN config with risk_budget: {max_drawdown: 0.15, kelly_cap: 0.25, var_confidence: 0.95}
- WHEN CFX generated
- THEN `<PortfolioSettings>` includes RiskBudgeting subsection with these parameters

### Requirement: Run Portfolio Master via sqcli

The system MUST execute the portfolio master through sqcli and extract results, supporting correlation-aware genetic search.
(Previously: Basic genetic search execution)

#### Scenario: Correlation-aware genetic search runs
- GIVEN valid portfolio master CFX with CorrelationFilter
- WHEN `PortfolioMaster.run(config)` is called
- THEN sqcli executes with correlation constraints active
- AND selected strategies respect max_correlation limit
- AND method returns list of selected strategy IDs with correlation matrix

#### Scenario: Risk budgeting enforced during optimization
- GIVEN config with max_portfolio_drawdown=0.15
- WHEN genetic search runs
- THEN portfolios exceeding 15% drawdown penalized in fitness
- AND final selection respects drawdown budget

### Requirement: Extract Selected Strategies from Results

The system MUST parse the sqcli export to identify which strategies were selected, including their allocated weights and risk contributions.
(Previously: Only strategy IDs)

#### Scenario: Extract returns strategies with weights and risk contributions
- GIVEN sqcli exported portfolio result XML
- WHEN `PortfolioMaster.extract_selected_strategies(result_path)` is called
- THEN list of dicts: [{"id": "s1", "weight": 0.5, "risk_contribution": 0.35}, {"id": "s2", "weight": 0.3, "risk_contribution": 0.25}, ...]
- AND weights sum to 1.0

#### Scenario: Extract handles missing result file
- GIVEN result path does not exist
- WHEN `extract_selected_strategies()` is called
- THEN PortfolioMasterResultError is raised

### Requirement: Dry-Run Mode

The system MUST support dry-run for CFX inspection without SQX.
(Previously: Basic dry-run)

#### Scenario: Dry-run generates CFX with correlation and risk config
- GIVEN PortfolioMaster with dry_run=True, config with correlation and risk budgeting
- WHEN `run(config)` is called
- THEN CFX is generated at expected path with CorrelationFilter and RiskBudgeting sections
- AND mock selected strategies returned with weights
- AND no sqcli process is spawned

## ADDED Requirements

### Requirement: Multi-Strategy Integration with Correlation Analysis

The system MUST provide `PortfolioMaster.analyze_correlation(strategies)` returning correlation matrix and cluster recommendations before CFX generation.

#### Scenario: Correlation analysis prevents over-concentration
- GIVEN 5 strategies, pairwise correlations computed
- WHEN `analyze_correlation()` called
- THEN returns matrix + clusters (corr>0.7 grouped)
- AND recommendation: "Select max 1 from each cluster"

### Requirement: Risk Budgeting Allocation

The system MUST provide `PortfolioMaster.compute_risk_budget(strategies, risk_config)` returning per-strategy risk allocation using Kelly/mean-variance with portfolio-level constraints.

#### Scenario: Risk budget respects portfolio drawdown limit
- GIVEN strategies with individual Sharpe, covariance matrix, risk.max_portfolio_drawdown=0.15
- WHEN `compute_risk_budget()` called
- THEN weights optimize Sharpe subject to portfolio VaR(95%) ≤ 15%
- AND no single weight > risk.max_single_strategy_weight

### Requirement: Walk-Forward Validation for Portfolio

The system MUST integrate with optimizer-automation for portfolio-level walk-forward optimization.

#### Scenario: Portfolio WF optimization runs
- GIVEN portfolio CFX, WF config: cycles=10, IS=70%, OOS=30%
- WHEN `PortfolioMaster.run_walk_forward()` called
- THEN optimizer_automation.walk_forward() executes portfolio-level WF
- AND returns aggregate OOS stats with AggregateStats

---

## REMOVED Requirements

None.

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| CFX includes CorrelationFilter section | Unit test: build CFX → parse XML → assert CorrelationFilter |
| CFX includes RiskBudgeting section | Unit test: assert RiskBudgeting subsection present |
| Correlation-aware search respects max_correlation | Integration: mock sqcli → assert selected strategies corr ≤ 0.7 |
| Risk budgeting enforced in fitness | Integration: portfolio drawdown ≤ limit in final selection |
| Extract returns weights and risk contributions | Unit test: parse mock XML → assert weight, risk_contribution fields |
| Correlation analysis returns clusters | Unit test: 5 strategies → assert clusters identified |
| Risk budget optimizes subject to VaR | Unit test: assert portfolio VaR ≤ limit |
| Portfolio WF uses optimizer-automation | Integration: mock WF → assert cycles executed |

---