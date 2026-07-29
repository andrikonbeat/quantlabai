"""Abstract base stages for the SQX campaign pipeline (original 12 stages).

Each stage declares its I/O contract via ``requires``/``provides``.
Concrete SQX implementations live in ``quantlab.phase4.stages``.

This is a private module — import via ``quantlab.pipeline.stages`` instead.
"""

from quantlab.pipeline.base import PipelineContext, Stage


class ValidateStage(Stage):
    """Validate configuration and license."""
    name = "validate"
    requires = []
    provides = ["validated_config"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        # Abstract — concrete implementation in phase4
        raise NotImplementedError("ValidateStage must be implemented by SQX-specific subclass")


class TranslateStage(Stage):
    """Translate DSL ResearchConfig to CFX archive bytes."""
    name = "translate"
    requires = ["validated_config"]
    provides = ["cfx_bytes", "cfx_path"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("TranslateStage must be implemented by SQX-specific subclass")


class DaemonStartStage(Stage):
    """Start SQX -gui daemon and return base URL."""
    name = "daemon_start"
    requires = []
    provides = ["daemon_url", "daemon_manager"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("DaemonStartStage must be implemented by SQX-specific subclass")


class LoadConfigStage(Stage):
    """Load CFX config into SQX."""
    name = "load_config"
    requires = ["dispatcher", "cfx_bytes"]
    provides = []
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("LoadConfigStage must be implemented by SQX-specific subclass")


class RunCampaignStage(Stage):
    """Start the SQX project/campaign."""
    name = "run_campaign"
    requires = ["dispatcher"]
    provides = ["campaign_name"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("RunCampaignStage must be implemented by SQX-specific subclass")


class PollCampaignStage(Stage):
    """Poll campaign status until completion or timeout."""
    name = "poll_campaign"
    requires = ["dispatcher", "campaign_name"]
    provides = ["campaign_status"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("PollCampaignStage must be implemented by SQX-specific subclass")


class CampaignStage(Stage):
    """Load CFX, start project, poll to completion."""
    name = "campaign"
    requires = ["daemon_url", "cfx_path"]
    provides = ["campaign_name", "campaign_status"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("CampaignStage must be implemented by SQX-specific subclass")


class ExportStage(Stage):
    """Export campaign results."""
    name = "export"
    requires = ["campaign_name", "daemon_url"]
    provides = ["export_paths"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("ExportStage must be implemented by SQX-specific subclass")


class ReadStage(Stage):
    """Parse exported CSV/XLSX into structured data."""
    name = "read"
    requires = ["export_paths"]
    provides = ["parsed_results"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("ReadStage must be implemented by SQX-specific subclass")


class ComputeStatsStage(Stage):
    """Compute trading statistics from parsed results."""
    name = "compute_stats"
    requires = ["parsed_results"]
    provides = ["statistics"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("ComputeStatsStage must be implemented by SQX-specific subclass")


class KnowledgeStoreStage(Stage):
    """Store artifacts in Knowledge Lake."""
    name = "knowledge_store"
    requires = ["parsed_results", "statistics"]
    provides = ["knowledge_keys"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("KnowledgeStoreStage must be implemented by SQX-specific subclass")


class CostInjectionStage(Stage):
    """Inject cost configuration from broker_profile into pipeline artifacts.

    Reads ``config.broker_profile`` from PipelineContext and writes
    ``cost_config`` to artifacts, containing CostEngine + CostCollector
    for downstream stages (BuilderStage, GuardianEvaluationStage).
    """
    name = "cost_injection"
    requires = ["config.broker_profile"]
    provides = ["cost_config"]

    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("CostInjectionStage must be implemented by SQX-specific subclass")


class ReportStage(Stage):
    """Generate HTML/JSON report."""
    name = "report"
    requires = ["parsed_results", "statistics"]
    provides = ["report_path"]
    
    async def execute(self, ctx: PipelineContext) -> dict:
        raise NotImplementedError("ReportStage must be implemented by SQX-specific subclass")
