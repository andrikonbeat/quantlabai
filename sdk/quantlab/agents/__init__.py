"""Multi-agent research system — core and analysis agents for the QuantLab research pipeline.

This package provides all agent stages for the multi-agent pipeline:

**PR 2 — Core Agents:**
- **ResearchDirector**: Owns ``PipelineRunner``, sequences all 8 agent stages,
  manages campaign lifecycle and human gates.
- **ResearchAgent**: Generates ``ResearchConfig`` from objectives, queries
  Knowledge Lake for historical patterns, formulates hypotheses.
- **BuilderAgent**: Orchestrates DSL-to-CFX translation, CFX validation,
  license checking, SQX dispatch, and campaign monitoring.

**PR 3 — Analysis Agents:**
- **StatisticsAgent**: Computes campaign statistics, aggregations, Monte Carlo
  bands, rolling metrics, and regime detection.
- **ReviewerAgent**: Evaluates campaign results against acceptance criteria,
  detects walk-forward/MC overfitting, compares against benchmarks.
- **PortfolioAgent**: Orchestrates Portfolio Master, correlation analysis,
  risk allocation (Kelly/mean-variance), and walk-forward optimization.

**Bloque D — Bayesian Optimization Agents:**
- **BayesianPostAnalysisAgent**: Post-analysis with Bayesian optimization
  feedback loop. Updates optimizer history with SQX results, decides whether
  to continue optimizing, converge, or advance to backtest comparison.
"""

from quantlab.agents.bayesian_post_analysis_agent import (
    BayesianPostAnalysisAgent,
    BayesianFeedbackDecision,
    create_bayesian_post_analysis_agent,
)
from quantlab.agents.builder_agent import BuilderAgent
from quantlab.agents.portfolio_agent import PortfolioAgent
from quantlab.agents.research_agent import ResearchAgent
from quantlab.agents.research_director import (
    CampaignState,
    ResearchDirector,
)
from quantlab.agents.reviewer_agent import ReviewerAgent
from quantlab.agents.statistics_agent import StatisticsAgent

__all__ = [
    "BayesianPostAnalysisAgent",
    "BayesianFeedbackDecision",
    "BuilderAgent",
    "CampaignState",
    "PortfolioAgent",
    "ResearchAgent",
    "ResearchDirector",
    "ReviewerAgent",
    "StatisticsAgent",
    "create_bayesian_post_analysis_agent",
]