# Delta for Reporting

## MODIFIED Requirements

### Requirement: Report Configuration Model

The system MUST extend `ReportConfig` with optional agent-specific sections: `include_agent_decisions: bool`, `include_comparison_view: bool`, `comparison_campaign_ids: list[str]`.
(Previously: Only campaign_id, output_dir, formats, include_charts, theme, title, benchmark_equity, chart_config)

#### Scenario: Agent decisions included in report
- GIVEN ReportConfig(include_agent_decisions=True)
- WHEN report generated for campaign with agent memories
- THEN HTML report includes "Agent Decisions" section with gate decisions, hypothesis evolution, iteration rationale
- AND JSON report includes "agent_decisions" object

#### Scenario: Comparison view across campaigns
- GIVEN ReportConfig(include_comparison_view=True, comparison_campaign_ids=["camp-1", "camp-2"])
- WHEN report generated
- THEN HTML includes comparison charts: Sharpe trend, drawdown comparison, regime alignment
- AND JSON includes "comparison" object with side-by-side metrics

### Requirement: HTML Report Generator

The system MUST extend HTML report with agent-specific sections when `include_agent_decisions=True`.
(Previously: Only equity curve, drawdown, trade scatter, metrics table)

#### Scenario: Agent decisions section rendered
- GIVEN campaign with 5 gate decisions, 3 iterations, agent memories
- WHEN generate_html() called with include_agent_decisions=True
- THEN HTML contains:
  - Gate Decision Timeline (gate_id, decision, decider, timestamp, rationale)
  - Hypothesis Evolution (iteration → hypothesis, confidence, outcome)
  - Iteration Rationale (reviewer feedback → research agent response)
  - Agent Performance Summary (stage duration, success rate, artifacts produced)

#### Scenario: Comparison view rendered
- GIVEN 3 campaigns with metrics
- WHEN generate_html() with include_comparison_view=True
- THEN HTML contains:
  - Multi-campaign equity curves (overlay, normalized)
  - Rolling Sharpe comparison (aligned time)
  - Regime timeline comparison
  - Metrics radar chart (Sharpe, PF, MDD, Win Rate, Calmar)

### Requirement: JSON Report Generator

The system MUST extend JSON schema with `agent_decisions` and `comparison` objects.
(Previously: Only campaign_id, summary, statistics, equity_curve, trades, phases)

#### Scenario: JSON includes agent decisions
- GIVEN ReportConfig(include_agent_decisions=True)
- WHEN generate_json() called
- THEN JSON includes:
  ```json
  "agent_decisions": {
    "gate_decisions": [...],
    "hypothesis_evolution": [...],
    "iteration_rationales": [...],
    "agent_summaries": {...}
  }
  ```

#### Scenario: JSON includes comparison
- GIVEN ReportConfig(include_comparison_view=True, comparison_campaign_ids=[...])
- WHEN generate_json() called
- THEN JSON includes:
  ```json
  "comparison": {
    "campaigns": [...],
    "metrics_comparison": {...},
    "regime_alignment": {...}
  }
  ```

## ADDED Requirements

### Requirement: Agent Decision Audit Report

The system MUST provide `ReportGenerator.generate_agent_audit_report(campaign_id, agent_memories)` producing a focused report on agent decision quality.

#### Scenario: Agent audit report generated
- GIVEN campaign_id, all 8 agent memories from Engram
- WHEN generate_agent_audit_report() called
- THEN HTML report with:
  - Decision accuracy: gate decisions vs eventual outcomes
  - Hypothesis calibration: confidence vs actual performance
  - Iteration efficiency: cycles to convergence
  - Agent stage performance: duration, retries, errors

### Requirement: Multi-Campaign Comparison Report

The system MUST provide `ReportGenerator.generate_comparison_report(campaign_ids, metrics)` for cross-campaign analysis.

#### Scenario: Comparison report generated
- GIVEN list of 10 campaign_ids, metrics=["sharpe", "max_drawdown", "calmar"]
- WHEN generate_comparison_report() called
- THEN HTML with: metric distributions, regime performance matrix, strategy type clustering

---

## REMOVED Requirements

None.

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| ReportConfig accepts new optional fields | Unit test: config with include_agent_decisions=True validates |
| HTML includes agent decisions section | Integration: generate → parse HTML → assert section exists |
| HTML includes comparison view | Integration: 3 campaigns → assert comparison charts |
| JSON schema extended and validates | Unit test: jsonschema.validate(generated_json, extended_schema) |
| Agent audit report includes calibration | Unit test: assert confidence vs outcome analysis |
| Comparison report includes regime matrix | Unit test: assert regime alignment table |

---