"""Multi-agent research system — core agents for the QuantLab research pipeline.

This package provides the three core agents (PR 2):

- **ResearchDirector**: Owns ``PipelineRunner``, sequences all 8 agent stages,
  manages campaign lifecycle and human gates.

- **ResearchAgent**: Generates ``ResearchConfig`` from objectives, queries
  Knowledge Lake for historical patterns, formulates hypotheses.

- **BuilderAgent**: Orchestrates DSL-to-CFX translation, CFX validation,
  license checking, SQX dispatch, and campaign monitoring.
"""

from quantlab.agents.research_director import (
    CampaignState,
    ResearchDirector,
)
from quantlab.agents.research_agent import ResearchAgent
from quantlab.agents.builder_agent import BuilderAgent

__all__ = [
    "ResearchDirector",
    "CampaignState",
    "ResearchAgent",
    "BuilderAgent",
]
