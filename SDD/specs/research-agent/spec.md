# Research Agent Specification

## Purpose

Enhances ResearchAgent for capital-aware reasoning and extended Knowledge Lake queries beyond Sharpe filters.

## Requirements

### Requirement: Capital-Aware Reasoning

The system MUST make ResearchAgent aware of account capital constraints when forming research queries. The agent SHALL incorporate capital tier, margin requirements, and cost profiles into hypothesis generation.

#### Scenario: Low-capital account adjusts research

- GIVEN a $5,000 account with 1:100 leverage
- WHEN ResearchAgent generates hypotheses
- THEN all proposed strategies respect margin requirements
- AND position sizing fits within capital constraints

#### Scenario: High-capital account enables diverse search

- GIVEN a $500,000 account
- WHEN ResearchAgent searches Knowledge Lake
- THEN the search includes strategies validated at similar capital scales
- AND diversification constraints are applied

### Requirement: Extended Knowledge Lake Queries

The system MUST enable ResearchAgent to query Knowledge Lake beyond Sharpe filters. Queries SHALL support: regime alignment, cost profile matching, drawdown constraints, and Guardian feedback history.

#### Scenario: Regime-aligned query

- GIVEN ResearchAgent is targeting a high-volatility regime
- WHEN it queries Knowledge Lake
- THEN results are filtered to strategies validated in similar regimes
- AND Sharpe filter is not the only criterion

#### Scenario: Guardian feedback informs query

- GIVEN Guardian feedback indicates cost sensitivity
- WHEN ResearchAgent queries Knowledge Lake
- THEN cost profile is included as a filter
- AND strategies with high spread/slippage are deprioritized

## ADDED Requirements

### Requirement: Research Stage Canon (G5)

The research stage names in the canonical pipeline MUST be `research` (classic) and `research_llm` (LLM-routed), positioned as the first agent stage of `build_pipeline`. The retired "8 agents + 5 gates" wording MUST be superseded by the canonical counts in full-campaign-lifecycle.

#### Scenario: Research is the first agent stage

- GIVEN the orchestrated pipeline
- WHEN the stage list is inspected
- THEN the first agent entry is `research` or `research_llm`
- AND no doc claims a fixed 8-agent set
