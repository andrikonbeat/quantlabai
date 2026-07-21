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
"""

from quantlab.agents.research_director import (
    CampaignState,
    ResearchDirector,
)
from quantlab.agents.research_agent import ResearchAgent
from quantlab.agents.builder_agent import BuilderAgent
from quantlab.agents.statistics_agent import StatisticsAgent
from quantlab.agents.reviewer_agent import ReviewerAgent
from quantlab.agents.portfolio_agent import PortfolioAgent

__all__ = [
    "ResearchDirector",
    "CampaignState",
    "ResearchAgent",
    "BuilderAgent",
    "StatisticsAgent",
    "ReviewerAgent",
    "PortfolioAgent",
]
