"""Pipeline stages — original SQX stages, new agent stages, and gate interceptor.

This package re-exports all stage classes from the original ``_stages`` module
plus the new multi-agent stages and gate interceptor, providing a single
import source::

    from quantlab.pipeline.stages import (
        ValidateStage,          # original SQX
        ResearchStage,          # new agent
        GateInterceptorStage,   # new gate
    )
"""

# Re-export original SQX stages from the private module
from quantlab.pipeline._stages import (
    CampaignStage,
    ComputeStatsStage,
    CostInjectionStage,
    DaemonStartStage,
    ExportStage,
    KnowledgeStoreStage,
    LoadConfigStage,
    PollCampaignStage,
    ReadStage,
    ReportStage,
    RunCampaignStage,
    TranslateStage,
    ValidateStage,
)

# Re-export new agent stages
from quantlab.pipeline.stages.agent_stages import (
    BuilderStage,
    DeployStage,
    GuardianEvaluationStage,
    MonitorStage,
    PortfolioStage,
    ResearchStage,
    ReviewStage,
    StatisticsStage,
)

# Re-export gate interceptor
from quantlab.pipeline.stages.gate_interceptor import (
    FallbackPolicy,
    GateAction,
    GateCallback,
    GateContext,
    GateDecision,
    GateInterceptorStage,
    HUMAN_GATE_IDS,
)
from quantlab.pipeline.stages.monte_carlo_stage import MonteCarloStage

# Re-export orchestrated flow stages (PR 3): config review, dispatch, retest, optimize
from quantlab.pipeline.stages.config_review_stage import ConfigReviewStage
from quantlab.pipeline.stages.dispatch_stage import DispatchStage
from quantlab.pipeline.stages.optimizer_stage import OptimizerStage
from quantlab.pipeline.stages.retester_stage import RetesterStage

__all__ = [
    # Original SQX stages
    "ValidateStage",
    "TranslateStage",
    "CostInjectionStage",
    "DaemonStartStage",
    "LoadConfigStage",
    "RunCampaignStage",
    "PollCampaignStage",
    "CampaignStage",
    "ExportStage",
    "ReadStage",
    "ComputeStatsStage",
    "KnowledgeStoreStage",
    "ReportStage",
    # New agent stages
    "ResearchStage",
    "BuilderStage",
    "StatisticsStage",
    "ReviewStage",
    "PortfolioStage",
    "DeployStage",
    "MonitorStage",
    "GuardianEvaluationStage",
    # Gate interceptor
    "GateInterceptorStage",
    "GateDecision",
    "GateContext",
    "GateCallback",
    "GateAction",
    "FallbackPolicy",
    "HUMAN_GATE_IDS",
    # Monte Carlo
    "MonteCarloStage",
    # Orchestrated flow (PR 3)
    "ConfigReviewStage",
    "DispatchStage",
    "RetesterStage",
    "OptimizerStage",
]
