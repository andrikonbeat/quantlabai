"""Pipeline execution framework — generic, SQX-agnostic."""

from quantlab.pipeline.base import (
    Pipeline,
    PipelineContext,
    Stage as PipelineStage,
)
from quantlab.pipeline.models import (
    PipelineResult,
    PipelineRun,
    StageResult,
    StageRun,
    StageStatus,
)
from quantlab.pipeline.runner import PipelineRunner
from quantlab.pipeline.stages import (
    ValidateStage,
    TranslateStage,
    DaemonStartStage,
    LoadConfigStage,
    RunCampaignStage,
    PollCampaignStage,
    CampaignStage,
    ExportStage,
    ReadStage,
    ComputeStatsStage,
    KnowledgeStoreStage,
    ReportStage,
)
from quantlab.pipeline.registry import PipelineRegistry, StageRegistry
from quantlab.pipeline.config import PipelineConfig, PipelineSummary, StageConfig

# New agent stage exports
from quantlab.pipeline.stages.agent_stages import (
    BuilderStage,
    DeployStage,
    MonitorStage,
    PortfolioStage,
    ResearchStage,
    ReviewStage,
    StatisticsStage,
)
from quantlab.pipeline.stages.gate_interceptor import (
    FallbackPolicy,
    GateAction,
    GateCallback,
    GateContext,
    GateDecision,
    GateInterceptorStage,
)

from quantlab.pipeline.license import LicenseManager, LicenseStatus
from quantlab.pipeline.progress import ProgressCallback

__all__ = [
    # Core
    "PipelineContext",
    "Pipeline",
    "PipelineStage",
    "StageStatus",
    "StageResult",
    "PipelineResult",
    "StageRun",
    "PipelineRun",
    "PipelineRunner",
    # SQX stages (original 9/12)
    "ValidateStage",
    "TranslateStage",
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
    # Agent stages (new, PR 1)
    "ResearchStage",
    "BuilderStage",
    "StatisticsStage",
    "ReviewStage",
    "PortfolioStage",
    "DeployStage",
    "MonitorStage",
    # Gate interceptor
    "GateInterceptorStage",
    "GateDecision",
    "GateContext",
    "GateCallback",
    "GateAction",
    "FallbackPolicy",
    # Registry
    "StageRegistry",
    "PipelineRegistry",
    # Config
    "PipelineConfig",
    "StageConfig",
    "PipelineSummary",
    # Utility
    "LicenseManager",
    "LicenseStatus",
    "ProgressCallback",
]
