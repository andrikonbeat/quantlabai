"""Phase 4   Campaign Orchestrator for end-to-end SQX pipeline execution.

Orchestrates the full campaign lifecycle: translate DSL → start SQX daemon  
load CFX → run project → poll status → export results → read exports  
compute statistics → store artifacts. Supports progress callbacks and
dry-run mode.

Refactored to use the generic pipeline framework internally while
preserving 100% public API backward compatibility.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from quantlab.dsl.models import ResearchConfig
from quantlab.dsl.parser import parse_yaml
from quantlab.translate.cfx import CfxArchive
from quantlab.phase4.daemon import SQXDaemonManager
from quantlab.phase4.command_dispatcher import CommandDispatcher, CampaignStatus
from quantlab.phase4.http_client import AsyncSQXClient
from quantlab.tools.exceptions import LicenseError, CampaignError
from quantlab.readers.databank import DatabankCSVReader
from quantlab.stats.engine import StatisticsEngine
from quantlab.knowledge.store import KnowledgeStore

# Import pipeline framework
from quantlab.pipeline import (
    Pipeline,
    PipelineContext,
    PipelineRunner,
    PipelineResult,
    StageResult,
    StageStatus,
)
from quantlab.phase4.stages import (
    SQXValidateStage,
    SQXTranslateStage,
    SQXDaemonStartStage,
    SQXLoadConfigStage,
    SQXRunCampaignStage,
    SQXPollCampaignStage,
    SQXExportStage,
    SQXReadStage,
    SQXComputeStatsStage,
    SQXKnowledgeStoreStage,
    SQXReportStage,
)


class CampaignPhase(str, Enum):
    """Pipeline execution phases."""

    VALIDATE = "validate"
    TRANSLATE = "translate"
    DAEMON_START = "daemon_start"
    LOAD_CONFIG = "load_config"
    RUN = "run"
    POLL = "poll"
    EXPORT = "export"
    READ = "read"
    COMPUTE = "compute"
    STORE = "store"
    COMPLETE = "complete"


class PhaseStatus(str, Enum):
    """Phase execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseResult:
    """Result of a single pipeline phase."""

    phase: CampaignPhase
    status: PhaseStatus
    detail: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        end = self.completed_at or time.time()
        return end - self.started_at


@dataclass
class CampaignResult:
    """Complete campaign execution result."""

    campaign_name: str
    phase_results: list[PhaseResult] = field(default_factory=list)
    cfx_path: Optional[Path] = None
    cfx_bytes: Optional[bytes] = None
    campaign_status: Optional[CampaignStatus] = None
    export_paths: dict[str, Path] = field(default_factory=dict)
    trades: list = field(default_factory=list)
    equity: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    statistics: dict = field(default_factory=dict)
    artifact_paths: dict[str, Path] = field(default_factory=dict)
    total_duration: float = 0.0
    error: Optional[str] = None

    @property
    def is_successful(self) -> bool:
        return self.error is None and all(
            r.status == PhaseStatus.COMPLETED for r in self.phase_results
        )


@dataclass
class CampaignConfig:
    """Configuration for a campaign run."""

    # SQX environment
    sqx_install_path: str = "/opt/StrategyQuantX"
    sqx_port: int = 8888
    sqx_license: str = "FUTLABF255"

    # Pipeline
    research_config_path: Optional[Path] = None
    output_dir: Path = Path("_output")
    dry_run: bool = False

    # Campaign
    campaign_name: str = "Campaign"
    campaign_type: str = "backtest"  # backtest, optimizer, retester, portfolio_master, portfolio

    # Polling
    poll_interval: float = 30.0
    poll_timeout: float = 3600.0  # 1 hour default

    # Exports
    export_formats: list[str] = field(default_factory=lambda: ["csv"])
    export_databanks: bool = True

    # Knowledge Lake
    knowledge_root: Optional[Path] = None

    # Callbacks
    progress_callback: Optional[Callable[[CampaignPhase, PhaseStatus, Optional[str]], Any]] = None


class CampaignOrchestrator:
    """Orchestrates end-to-end SQX campaign execution.

    Coordinates the full pipeline: DSL translation → daemon management  
    sqcli dispatch → status polling → result export → statistics → storage.
    
    Internally uses the generic pipeline framework (quantlab.pipeline) while
    preserving 100% backward compatibility with the public API.
    """

    def __init__(self, config: CampaignConfig):
        self.config = config
        self._daemon: Optional[SQXDaemonManager] = None
        self._dispatcher: Optional[CommandDispatcher] = None
        self._client: Optional[AsyncSQXClient] = None
        self._result = CampaignResult(campaign_name=config.campaign_name)

    #   Public API  

    async def run(self) -> CampaignResult:
        """Execute the full campaign pipeline.

        Returns:
            CampaignResult with all phase results and artifacts.
        """
        start_time = time.time()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            if self.config.dry_run:
                return await self._run_dry_run()

            # Build and execute pipeline
            pipeline = self._build_pipeline()
            ctx = self._create_pipeline_context()

            runner = PipelineRunner()
            pipeline_result = await runner.run(pipeline, ctx)

            # Save daemon reference for cleanup
            self._daemon = ctx.artifacts.get("daemon_manager")

            # Map pipeline result to CampaignResult
            self._map_pipeline_result(pipeline_result, ctx)

        except CampaignError as e:
            self._result.error = str(e)
            raise
        except Exception as e:
            self._result.error = f"Unexpected error: {e}"
            raise CampaignError(f"Campaign failed: {e}", phase="unknown") from e
        finally:
            self._result.total_duration = time.time() - start_time
            await self._cleanup()

        return self._result

    #   Pipeline Construction  

    def _build_pipeline(self) -> Pipeline:
        """Build the SQX campaign pipeline from concrete stage implementations."""
        return (
            Pipeline("SQX Campaign")
            .then(SQXValidateStage())
            .then(SQXTranslateStage())
            .then(SQXDaemonStartStage())
            .then(SQXLoadConfigStage())
            .then(SQXRunCampaignStage())
            .then(SQXPollCampaignStage())
            .then(SQXExportStage())
            .then(SQXReadStage())
            .then(SQXComputeStatsStage())
            .then(SQXKnowledgeStoreStage())
            .then(SQXReportStage())
        )

    def _create_pipeline_context(self) -> PipelineContext:
        """Create PipelineContext initialized from CampaignConfig."""
        config_dict = {
            "sqx_install_path": self.config.sqx_install_path,
            "sqx_port": self.config.sqx_port,
            "sqx_license": self.config.sqx_license,
            "research_config_path": self.config.research_config_path,
            "output_dir": self.config.output_dir,
            "campaign_name": self.config.campaign_name,
            "campaign_type": self.config.campaign_type,
            "poll_interval": self.config.poll_interval,
            "poll_timeout": self.config.poll_timeout,
            "export_formats": self.config.export_formats,
            "export_databanks": self.config.export_databanks,
            "knowledge_root": self.config.knowledge_root,
            "dry_run": self.config.dry_run,
            "progress_callback": self.config.progress_callback,
        }
        return PipelineContext(config=config_dict)

    def _map_pipeline_result(self, pipeline_result: PipelineResult, ctx: PipelineContext) -> None:
        """Map PipelineResult and context artifacts to CampaignResult."""
        artifacts = ctx.artifacts

        # Map phase results
        phase_map = {
            "validate": CampaignPhase.VALIDATE,
            "translate": CampaignPhase.TRANSLATE,
            "daemon_start": CampaignPhase.DAEMON_START,
            "load_config": CampaignPhase.LOAD_CONFIG,
            "run_campaign": CampaignPhase.RUN,
            "poll_campaign": CampaignPhase.POLL,
            "export": CampaignPhase.EXPORT,
            "read": CampaignPhase.READ,
            "compute_stats": CampaignPhase.COMPUTE,
            "knowledge_store": CampaignPhase.STORE,
            "report": CampaignPhase.COMPLETE,
        }

        for stage_result in pipeline_result.stages:
            campaign_phase = phase_map.get(stage_result.stage_name)
            if campaign_phase:
                phase_result = PhaseResult(
                    phase=campaign_phase,
                    status=PhaseStatus(stage_result.status.value) if stage_result.status != StageStatus.SKIPPED else PhaseStatus.SKIPPED,
                    detail=stage_result.error or f"{campaign_phase.value} completed",
                    started_at=stage_result.started_at.timestamp() if stage_result.started_at else time.time(),
                    completed_at=stage_result.completed_at.timestamp() if stage_result.completed_at else None,
                    error=stage_result.error,
                )
                self._result.phase_results.append(phase_result)

                # Fire callbacks
                self._fire_callback(campaign_phase, phase_result.status, phase_result.detail)

        # Map artifacts
        self._result.cfx_bytes = artifacts.get("cfx_bytes")
        self._result.campaign_status = artifacts.get("campaign_status")
        self._result.export_paths = artifacts.get("export_paths", {})
        parsed = artifacts.get("parsed_results", {})
        self._result.trades = parsed.get("trades", [])
        self._result.equity = parsed.get("equity", [])
        self._result.summary = parsed.get("summary", {})
        self._result.statistics = artifacts.get("statistics", {})
        self._result.artifact_paths = artifacts.get("artifact_paths", {})

        if pipeline_result.error:
            self._result.error = pipeline_result.error

    async def _run_dry_run(self) -> CampaignResult:
        """Handle dry-run mode by running VALIDATE+TRANSLATE, simulating rest."""
        # Fire RUNNING callbacks for VALIDATE and TRANSLATE before running pipeline
        self._fire_callback(CampaignPhase.VALIDATE, PhaseStatus.RUNNING, "Dry-run validate started")
        self._fire_callback(CampaignPhase.TRANSLATE, PhaseStatus.RUNNING, "Dry-run translate started")
        
        # Run VALIDATE and TRANSLATE through pipeline
        pipeline = Pipeline("SQX Campaign Dry-Run").then(SQXValidateStage()).then(SQXTranslateStage())
        ctx = self._create_pipeline_context()
        runner = PipelineRunner()
        
        pipeline_result = await runner.run(pipeline, ctx)
        
        # If pipeline failed, re-raise as CampaignError with phase info
        if pipeline_result.error:
            # Find the failed stage
            for stage_result in pipeline_result.stages:
                if stage_result.status == StageStatus.FAILED:
                    phase_map = {
                        "validate": CampaignPhase.VALIDATE,
                        "translate": CampaignPhase.TRANSLATE,
                    }
                    campaign_phase = phase_map.get(stage_result.stage_name)
                    raise CampaignError(
                        stage_result.error or "Stage failed",
                        phase=campaign_phase.value if campaign_phase else "unknown",
                        campaign_name=self.config.campaign_name,
                    )
            raise CampaignError(pipeline_result.error, phase="unknown")
        
        self._result.cfx_bytes = ctx.artifacts.get("cfx_bytes", b"mock-cfx-content")

        # Map pipeline stages to CampaignPhase for VALIDATE and TRANSLATE
        phase_map = {
            "validate": CampaignPhase.VALIDATE,
            "translate": CampaignPhase.TRANSLATE,
        }
        for stage_result in pipeline_result.stages:
            campaign_phase = phase_map.get(stage_result.stage_name)
            if campaign_phase:
                phase_result = PhaseResult(
                    phase=campaign_phase,
                    status=PhaseStatus(stage_result.status.value) if stage_result.status != StageStatus.SKIPPED else PhaseStatus.SKIPPED,
                    detail=stage_result.error or f"{campaign_phase.value} completed",
                    started_at=stage_result.started_at.timestamp() if stage_result.started_at else time.time(),
                    completed_at=stage_result.completed_at.timestamp() if stage_result.completed_at else None,
                    error=stage_result.error,
                )
                self._result.phase_results.append(phase_result)
                self._fire_callback(campaign_phase, phase_result.status, phase_result.detail)

        # Simulate remaining 9 phases
        dry_run_phases = [
            CampaignPhase.DAEMON_START,
            CampaignPhase.LOAD_CONFIG,
            CampaignPhase.RUN,
            CampaignPhase.POLL,
            CampaignPhase.EXPORT,
            CampaignPhase.READ,
            CampaignPhase.COMPUTE,
            CampaignPhase.STORE,
            CampaignPhase.COMPLETE,
        ]
        for phase in dry_run_phases:
            self._fire_callback(phase, PhaseStatus.RUNNING, f"Dry-run {phase.value} started")
            result = PhaseResult(
                phase=phase,
                status=PhaseStatus.COMPLETED,
                detail=f"Dry-run {phase.value} simulated",
            )
            result.completed_at = time.time()
            self._result.phase_results.append(result)
            self._fire_callback(phase, PhaseStatus.COMPLETED, f"Dry-run {phase.value} simulated")

        self._result.total_duration = 0.0
        return self._result

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self._daemon:
            await self._daemon.stop()
        if self._client:
            await self._client.close()

    def _fire_callback(
        self,
        phase: CampaignPhase,
        status: PhaseStatus,
        detail: Optional[str] = None,
    ) -> None:
        """Fire progress callback if registered."""
        if self.config.progress_callback:
            try:
                self.config.progress_callback(phase, status, detail)
            except Exception:
                pass  # Callback errors should not break pipeline

    #   Async Context Manager  

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit — cleans up resources."""
        await self._cleanup()


#   Convenience Function  


async def run_campaign(
    campaign_name: str,
    research_config_path: Path,
    output_dir: Path = Path("_output"),
    *,
    dry_run: bool = False,
    sqx_install_path: str = "/opt/StrategyQuantX",
    poll_interval: float = 30.0,
    poll_timeout: float = 3600.0,
    progress_callback: Optional[Callable] = None,
) -> CampaignResult:
    """High-level function to run a complete campaign.

    Args:
        campaign_name: Name for the campaign.
        research_config_path: Path to research YAML.
        output_dir: Output directory for results.
        dry_run: If True, simulate without SQX.
        sqx_install_path: Path to SQX installation.
        poll_interval: Status polling interval (seconds).
        poll_timeout: Maximum time to wait for completion.
        progress_callback: Optional callback(phase, status, detail).

    Returns:
        CampaignResult with all results and artifacts.
    """
    config = CampaignConfig(
        campaign_name=campaign_name,
        research_config_path=research_config_path,
        output_dir=output_dir,
        dry_run=dry_run,
        sqx_install_path=sqx_install_path,
        poll_interval=poll_interval,
        poll_timeout=poll_timeout,
        progress_callback=progress_callback,
    )

    orchestrator = CampaignOrchestrator(config)
    return await orchestrator.run()