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
    AnalysisStage,
    BuilderStage,
    GuardianEvaluationStage,
    HypothesisBuilderStage,
    LLMResearchStage,
    MonitorStage,
    RefutationStage,
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

# Concrete post-optimize stages (PR 6, REQ-01 phases 9-13): these shadow the
# abstract anchors of the same name — both subclass the abstract contract.
from quantlab.pipeline.stages.archive_stage import ArchiveStage
from quantlab.pipeline.stages.compile_stage import CompileStage
from quantlab.pipeline.stages.demo_stage import DemoStage
from quantlab.pipeline.stages.deploy_stage import DeployStage
from quantlab.pipeline.stages.live_ops_stage import LiveOpsStage
from quantlab.pipeline.stages.portfolio_stage import PortfolioStage

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
    # Post-optimize orchestrated stages (PR 6, REQ-01 phases 9-13)
    "PortfolioStage",
    "DeployStage",
    "CompileStage",
    "DemoStage",
    "ArchiveStage",
    # Canonical live-ops phase (REQ-01 phase 14)
    "LiveOpsStage",
]
