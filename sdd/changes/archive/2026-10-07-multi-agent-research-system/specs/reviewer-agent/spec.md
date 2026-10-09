# Reviewer Agent Specification

## Purpose

Adversarial reviewer that evaluates campaign results against acceptance criteria, performs walk-forward and Monte Carlo overfitting checks, compares against benchmarks, and proposes iteration or approval decisions for human gate #2.

---

## Requirements

### Requirement: Acceptance Criteria Evaluation

The system MUST evaluate campaign statistics against ResearchConfig acceptance_criteria (min_sharpe, max_drawdown, min_profit_factor, min_win_rate, min_trades).

#### Scenario: Campaign passes all criteria
- GIVEN stats: sharpe=1.6, mdd=10%, pf=1.8, win_rate=55%, trades=150
- AND criteria: min_sharpe=1.5, max_drawdown=15%, min_pf=1.5, min_win_rate=50%, min_trades=100
- WHEN ReviewerAgent.evaluate() called
- THEN decision = APPROVE, all checks pass, no iteration proposal

#### Scenario: Campaign fails criteria → iteration proposal
- GIVEN stats: sharpe=1.2, mdd=18%, pf=1.3
- AND criteria: min_sharpe=1.5, max_drawdown=15%, min_pf=1.5
- WHEN ReviewerAgent.evaluate() called
- THEN decision = ITERATE, failed_checks = ["sharpe", "max_drawdown", "profit_factor"]
- AND iteration_proposal suggests: tighten entry filter, reduce position size, add volatility filter

### Requirement: Walk-Forward Overfitting Check

The system MUST analyze walk-forward optimization results for in-sample vs out-of-sample degradation.

#### Scenario: WF degradation detected
- GIVEN WF cycles: IS sharpe=[2.1, 2.3, 2.0], OOS sharpe=[0.8, 0.5, 0.3]
- WHEN ReviewerAgent.check_wf_overfitting() called
- THEN overfitting_flag = TRUE, degradation_ratio = mean(OOS)/mean(IS) ≈ 0.3
- AND iteration_proposal includes: "Reduce parameter space, increase OOS window"

#### Scenario: WF robust
- GIVEN IS sharpe=[1.8, 1.9], OOS sharpe=[1.5, 1.6]
- WHEN ReviewerAgent.check_wf_overfitting() called
- THEN overfitting_flag = FALSE, degradation_ratio ≈ 0.85 (>0.7 threshold)

### Requirement: Monte Carlo Overfitting Check

The system MUST compare live/backtest equity curve against Monte Carlo percentile bands.

#### Scenario: Live curve below MC p10 → overfit risk
- GIVEN live equity curve, MC bands p10/p50/p90 from StatisticsAgent
- WHEN ReviewerAgent.check_mc_overfitting() called
- AND live curve crosses below p10 at trade 40
- THEN mc_overfit_flag = TRUE, breach_trade = 40, severity = "HIGH"

#### Scenario: Live curve within bands
- GIVEN live equity tracks near p50, never below p10
- WHEN ReviewerAgent.check_mc_overfitting() called
- THEN mc_overfit_flag = FALSE

### Requirement: Benchmark Comparison

The system MUST compare strategy against relevant benchmark (buy-and-hold, market index) using StatisticsAggregator.benchmark_compare().

#### Scenario: Strategy beats benchmark
- GIVEN strategy returns, benchmark returns (same period)
- WHEN ReviewerAgent.compare_benchmark() called
- THEN BenchmarkComparison with alpha>0, IR>0.5, up_capture>1, down_capture<1
- AND benchmark_verdict = "OUTPERFORMS"

#### Scenario: Strategy underperforms benchmark
- GIVEN alpha=-0.02, IR=-0.3, down_capture=1.5
- WHEN ReviewerAgent.compare_benchmark() called
- THEN benchmark_verdict = "UNDERPERFORMS", iteration_proposal suggests "Review market regime alignment"

### Requirement: Iteration Proposal Generation

The system MUST generate structured IterationProposal with action, parameter_changes, new_hypotheses, and rationale.

#### Scenario: Comprehensive iteration proposal
- GIVEN failed checks: sharpe, mdd, wf_degradation
- WHEN ReviewerAgent.generate_iteration_proposal() called
- THEN IterationProposal:
  - action: "MODIFY_AND_RETEST"
  - parameter_changes: {"position_size": "0.5x", "add_filter": "ATR>20"}
  - new_hypotheses: ["Volatility filter improves risk-adjusted returns"]
  - rationale: "Sharpe 1.2<1.5; MDD 18%>15%; WF degradation 65%"

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| All acceptance criteria evaluated | Unit test: feed stats + criteria, assert each check result |
| WF degradation ratio computed correctly | Unit test: known IS/OOS → assert ratio |
| MC breach detection at correct trade index | Unit test: synthetic equity crosses p10 at trade 40 |
| Benchmark comparison produces all metrics | Unit test: assert alpha, beta, IR, captures populated |
| Iteration proposal addresses all failures | Unit test: failed_checks ⊆ proposal.rationale |

---

## Non-Functional Requirements

- **Dependencies**: stats-aggregation, knowledge-query (for historical benchmarks)
- **Objectivity**: No learning — deterministic evaluation against fixed criteria
- **Auditability**: All checks, ratios, and decisions logged to Engram (agent/reviewer-agent/{campaign_id})