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
    AnalysisStage as AnalysisStage,
)
from quantlab.pipeline.stages.agent_stages import (
    BuilderStage,
    GuardianEvaluationStage,
    MonitorStage,
    ResearchStage,
    ReviewStage,
    StatisticsStage,
)
from quantlab.pipeline.stages.agent_stages import (
    HypothesisBuilderStage as HypothesisBuilderStage,
)
from quantlab.pipeline.stages.agent_stages import (
    LLMResearchStage as LLMResearchStage,
)
from quantlab.pipeline.stages.agent_stages import (
    RefutationStage as RefutationStage,
)

# Concrete post-optimize stages (PR 6, REQ-01 phases 9-13): these shadow the
# abstract anchors of the same name — both subclass the abstract contract.
from quantlab.pipeline.stages.archive_stage import ArchiveStage
from quantlab.pipeline.stages.compile_stage import CompileStage

# Re-export orchestrated flow stages (PR 3): config review, dispatch, retest, optimize
from quantlab.pipeline.stages.advanced_analysis_stage import AdvancedAnalysisStage
from quantlab.pipeline.stages.bayesian_optimizer_stage import (
    BayesianOptimizerFeedbackStage,
    BayesianOptimizerStage,
    BayesianOptimizerStageConfig,
)
from quantlab.pipeline.stages.config_review_stage import ConfigReviewStage
from quantlab.pipeline.stages.demo_stage import DemoStage
from quantlab.pipeline.stages.deploy_stage import DeployStage
from quantlab.pipeline.stages.dispatch_stage import DispatchStage

# Re-export gate interceptor
from quantlab.pipeline.stages.gate_interceptor import (
    HUMAN_GATE_IDS,
    FallbackPolicy,
    GateAction,
    GateCallback,
    GateContext,
    GateDecision,
    GateInterceptorStage,
)
from quantlab.pipeline.stages.live_ops_stage import LiveOpsStage
from quantlab.pipeline.stages.monte_carlo_stage import MonteCarloStage
from quantlab.pipeline.stages.optimizer_stage import OptimizerStage
from quantlab.pipeline.stages.portfolio_stage import PortfolioStage
from quantlab.pipeline.stages.retester_stage import RetesterStage

__all__ = [  # Original SQX stages
    "HUMAN_GATE_IDS",  # Monte Carlo
    "AnalysisStage",
    "ArchiveStage",  # Canonical live-ops phase (REQ-01 phase 14)
    "AdvancedAnalysisStage",  # Advanced analysis pipeline
    "BayesianOptimizerFeedbackStage",  # Bayesian optimization feedback
    "BayesianOptimizerStage",  # Bayesian optimization
    "BayesianOptimizerStageConfig",  # Bayesian optimization config
    "BuilderStage",
    "CampaignStage",
    "CompileStage",
    "ComputeStatsStage",
    "ConfigReviewStage",
    "CostInjectionStage",
    "DaemonStartStage",
    "DemoStage",
    "DeployStage",
    "DispatchStage",
    "ExportStage",
    "FallbackPolicy",
    "GateAction",
    "GateCallback",
    "GateContext",
    "GateDecision",
    "GateInterceptorStage",
    "GuardianEvaluationStage",  # Gate interceptor
    "HypothesisBuilderStage",
    "KnowledgeStoreStage",
    "LLMResearchStage",
    "LiveOpsStage",
    "LoadConfigStage",
    "MonitorStage",
    "MonteCarloStage",  # Orchestrated flow (PR 3)
    "OptimizerStage",  # Post-optimize orchestrated stages (PR 6, REQ-01 phases 9-13)
    "PollCampaignStage",
    "PortfolioStage",
    "ReadStage",
    "RefutationStage",
    "ReportStage",  # New agent stages
    "ResearchStage",
    "RetesterStage",
    "ReviewStage",
    "RunCampaignStage",
    "StatisticsStage",
    "TranslateStage",
    "ValidateStage",
]
