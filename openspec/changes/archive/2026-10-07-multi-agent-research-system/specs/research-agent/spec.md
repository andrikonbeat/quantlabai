# Research Agent Specification

## Purpose

Generates ResearchConfig DSL from research objectives, market hypotheses, and Knowledge Lake queries. Formulates testable hypotheses with confidence scores, queries historical campaigns for context, and produces iteration proposals.

---

## Requirements

### Requirement: ResearchConfig Generation

The system MUST parse high-level objectives into a valid ResearchConfig Pydantic model with markets, timeframes, building blocks, acceptance criteria, hypotheses, iteration_config, and gate_policies.

#### Scenario: Objectives to ResearchConfig
- GIVEN objectives: ["Find mean-reversion on EURUSD H1", "Validate 2020-2024 robustness"]
- AND hypotheses: [{"id": "h1", "description": "RSI(14)<30 + BB lower touch", "confidence": 0.7}]
- WHEN ResearchAgent.generate_config() called
- THEN ResearchConfig with market="EURUSD", timeframe="H1", building_blocks containing RSI/BB entries, acceptance_criteria with min_sharpe=1.0, max_drawdown=15%
- AND iteration_config.max_iterations=5, convergence_threshold=0.02

#### Scenario: Invalid objectives rejected
- GIVEN objectives referencing unknown market "CRYPTO/BTC"
- WHEN ResearchAgent.generate_config() called
- THEN ValidationError raised listing unknown market

### Requirement: Knowledge Lake Query Integration

The system MUST query Knowledge Lake for historical campaigns matching market, timeframe, and strategy tags to inform hypothesis generation.

#### Scenario: Query similar campaigns for context
- GIVEN market="EURUSD", timeframe="H1", tags={"strategy": "mean_reversion"}
- WHEN ResearchAgent.query_knowledge_lake() called
- THEN QueryBuilder filters by tags, date range (last 2 years), Sharpe > 1.0
- AND returns top 10 CampaignSummary with metrics, tags, links

#### Scenario: Hypothesis informed by historical performance
- GIVEN query returns campaigns with avg Sharpe=1.4, max_drawdown=12%
- WHEN ResearchAgent.formulate_hypotheses() called
- THEN new hypotheses reference successful patterns: "RSI(14)<25 outperformed RSI<30 by 0.2 Sharpe"
- AND confidence adjusted based on historical success rate

### Requirement: Hypothesis Formulation

The system MUST generate structured hypotheses with id, description, confidence (0-1), parameters dict, and expected_metrics.

#### Scenario: Multiple hypotheses from single objective
- GIVEN objective "Find breakout strategies on GBPUSD H4"
- WHEN ResearchAgent.formulate_hypotheses() called
- THEN generates 3-5 hypotheses covering: Donchian breakout, Bollinger squeeze, ATR volatility expansion
- AND each hypothesis has unique id, confidence∈[0.3,0.8], testable parameters

#### Scenario: Hypothesis confidence calibrated
- GIVEN historical query shows Donchian(20) Sharpe=1.6, Bollinger Sharpe=1.1
- WHEN formulating hypotheses
- THEN Donchian hypothesis confidence=0.75, Bollinger confidence=0.55

### Requirement: Iteration Proposal Generation

The system MUST propose next-iteration ResearchConfig modifications based on ReviewerAgent feedback and convergence status.

#### Scenario: Iteration proposal from reviewer feedback
- GIVEN ReviewerAgent decision: ITERATE with feedback "Sharpe 1.3 < 1.5 target; max_drawdown 18% > 15% limit"
- WHEN ResearchAgent.propose_iteration() called
- THEN new ResearchConfig tightens acceptance_criteria: min_sharpe=1.5, max_drawdown=12%
- AND adds hypothesis: "Reduce position size on high volatility regimes"
- AND iteration_config.current_iteration incremented

#### Scenario: Convergence proposal
- GIVEN 4 iterations, Sharpe improvement last 2 cycles < 0.01
- WHEN ResearchAgent.propose_iteration() called
- THEN iteration_proposal.action = "CONVERGE", rationale = "Sharpe plateau < threshold"
- AND no new hypotheses generated

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|--------------|
| ResearchConfig validates against research-dsl schema | Unit test: generate → validate → assert no errors |
| Knowledge Lake query returns CampaignSummary list | Integration: seed lake, query, assert fields populated |
| Hypotheses have unique IDs and testable params | Unit test: assert len(set(ids)) == count, params dict not empty |
| Iteration proposal modifies config per feedback | Unit test: feed reviewer feedback, assert config changes |
| Confidence scores in [0,1] range | Unit test: assert all 0<=c<=1 |

---

## Non-Functional Requirements

- **Performance**: Knowledge Lake query < 500ms for 10k campaigns
- **Dependencies**: research-dsl, knowledge-query, engram (for memory)
- **Testability**: Pure functions for hypothesis formulation, mockable query layer