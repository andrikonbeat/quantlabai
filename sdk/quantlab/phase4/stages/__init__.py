"""SQX-specific pipeline stage implementations.

Each stage extends the corresponding abstract base stage from
``quantlab.pipeline.stages`` with concrete SQX domain logic.

Stages that depend on Phase 4 modules (``CommandDispatcher``,
``SQXDaemonManager``, ``AsyncSQXClient``) use deferred/lazy imports
so the module can be imported without Phase 4 present.
"""

from __future__ import annotations

import asyncio
import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import yaml

from quantlab.dsl.models import ResearchConfig
from quantlab.dsl.parser import parse_yaml
from quantlab.knowledge.conformance import assert_conformance
from quantlab.knowledge.store import KnowledgeStore
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.models import (
    StageResult as StageResult,
)
from quantlab.pipeline.models import (
    StageStatus as StageStatus,
)
from quantlab.pipeline.stages import (
    CampaignStage,
    ComputeStatsStage,
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
from quantlab.readers.databank import DatabankCSVReader
from quantlab.stats.engine import StatisticsEngine
from quantlab.tools.exceptions import CampaignError, LicenseError
from quantlab.translate.cfx import CfxArchive

if TYPE_CHECKING:
    from quantlab.phase4.command_dispatcher import CommandDispatcher
    from quantlab.phase4.daemon import SQXDaemonManager


class SQXValidateStage(ValidateStage):
    """Validate SQX license and binary availability."""

    name: ClassVar[str] = "validate"
    requires: ClassVar[list[str]] = []
    provides: ClassVar[list[str]] = ["validated_config"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        config = ctx.config
        dry_run = config.get("dry_run", False)

        if dry_run:
            return {"validated": True, "dry_run": True}

        from pathlib import Path

        from quantlab.tools.platform import get_sqcli_binary, resolve_sqcli_path

        install_path = Path(config.get("sqx_install_path", "/opt/StrategyQuantX"))
        binary_name = get_sqcli_binary()
        binary_path = install_path / binary_name

        binary = resolve_sqcli_path(binary_path)
        if binary is None:
            raise LicenseError(
                "SQX not found",
                license_path=str(install_path),
            )

        return {"validated": True, "sqx_binary": str(binary)}


class SQXTranslateStage(TranslateStage):
    """Translate ResearchConfig DSL to CFX archive."""

    name: ClassVar[str] = "translate"
    requires: ClassVar[list[str]] = ["validated_config"]
    provides: ClassVar[list[str]] = ["cfx_bytes", "cfx_path"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        config = ctx.config
        dry_run = config.get("dry_run", False)
        research_config_path = config.get("research_config_path")
        campaign_name = config.get("campaign_name", "Campaign")

        if dry_run:
            if research_config_path:
                # In dry-run, still validate that config parses, but return mock bytes
                parse_yaml(research_config_path)
            return {"cfx_bytes": b"mock-cfx-content", "cfx_path": None}

        if research_config_path:
            try:
                research_config = parse_yaml(research_config_path)
            except Exception as e:
                from quantlab.tools.exceptions import TranslationError

                raise TranslationError(f"Failed to parse research config: {e}") from e
        else:
            research_config = ResearchConfig(
                campaign=campaign_name,
                market="EURUSD",
                timeframe="H1",
            )

        # CfxArchive.from_model writes the .cfx file and returns CfxResult
        result = CfxArchive.from_model(research_config, dry_run=False)
        cfx_path = result.path
        cfx_bytes = cfx_path.read_bytes()

        # Store in context artifacts for downstream stages
        ctx.artifacts["cfx_bytes"] = cfx_bytes
        ctx.artifacts["cfx_path"] = cfx_path

        return {"cfx_bytes": cfx_bytes, "cfx_path": str(cfx_path) if cfx_path else None}


class SQXDaemonStartStage(DaemonStartStage):
    """Start SQX -gui daemon and create HTTP client + dispatcher."""

    name: ClassVar[str] = "daemon_start"
    requires: ClassVar[list[str]] = []
    provides: ClassVar[list[str]] = ["daemon_url", "daemon_manager", "dispatcher", "http_client"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        # Deferred imports: Phase 4 modules not guaranteed present at import time
        from quantlab.phase4.command_dispatcher import CommandDispatcher
        from quantlab.phase4.daemon import SQXDaemonManager
        from quantlab.phase4.http_client import AsyncSQXClient

        config = ctx.config
        sqx_install_path = config.get("sqx_install_path", "/opt/StrategyQuantX")
        sqx_port = config.get("sqx_port", 8888)

        _daemon = SQXDaemonManager(
            sqx_install_path,
            port=sqx_port,
            startup_timeout=60.0,
        )
        base_url = await _daemon.start()

        client = AsyncSQXClient(base_url)
        dispatcher = await CommandDispatcher.from_daemon(_daemon)

        # Store in context for later stages
        ctx.artifacts["daemon_manager"] = _daemon
        ctx.artifacts["http_client"] = client
        ctx.artifacts["dispatcher"] = dispatcher

        return {
            "daemon_url": base_url,
            "daemon_manager": _daemon,
            "dispatcher": dispatcher,
            "http_client": client,
        }


class SQXLoadConfigStage(LoadConfigStage):
    """Load CFX config into SQX."""

    name: ClassVar[str] = "load_config"
    requires: ClassVar[list[str]] = ["dispatcher", "cfx_bytes"]
    provides: ClassVar[list[str]] = []

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        cfx_bytes = ctx.artifacts.get("cfx_bytes")
        dispatcher: CommandDispatcher = ctx.artifacts.get("dispatcher")

        if cfx_bytes is None:
            raise CampaignError("No CFX bytes available for load_config")

        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            cfx_path = Path(tmp.name)

        try:
            await dispatcher.load_config(cfx_path)
        finally:
            cfx_path.unlink(missing_ok=True)

        return {}


class SQXRunCampaignStage(RunCampaignStage):
    """Start the SQX project/campaign."""

    name: ClassVar[str] = "run_campaign"
    requires: ClassVar[list[str]] = ["dispatcher"]
    provides: ClassVar[list[str]] = ["campaign_name"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        config = ctx.config
        dispatcher: CommandDispatcher = ctx.artifacts.get("dispatcher")

        campaign_name = config.get("campaign_name", "Campaign")
        await dispatcher.start_project(campaign_name)

        return {"campaign_name": campaign_name}


class SQXPollCampaignStage(PollCampaignStage):
    """Poll campaign status until completion or timeout."""

    name: ClassVar[str] = "poll_campaign"
    requires: ClassVar[list[str]] = ["dispatcher", "campaign_name"]
    provides: ClassVar[list[str]] = ["campaign_status"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        config = ctx.config
        dispatcher: CommandDispatcher = ctx.artifacts.get("dispatcher")
        campaign_name = ctx.artifacts.get("campaign_name") or config.get(
            "campaign_name", "Campaign"
        )

        poll_interval = config.get("poll_interval", 30.0)
        poll_timeout = config.get("poll_timeout", 3600.0)

        start = time.time()
        while time.time() - start < poll_timeout:
            status = await dispatcher.get_status(campaign_name)

            if status.is_complete:
                return {"campaign_name": campaign_name, "campaign_status": status}

            if status.is_failed:
                raise CampaignError(
                    f"Campaign failed: {status.error_message}",
                    phase="poll",
                    campaign_name=campaign_name,
                )

            await asyncio.sleep(poll_interval)

        # Timeout
        await dispatcher.stop_project(campaign_name)
        raise CampaignError(
            f"Campaign timeout after {poll_timeout}s",
            phase="poll",
            campaign_name=campaign_name,
        )


class SQXCampaignStage(CampaignStage):
    """Load CFX config, start campaign, and poll for completion."""

    name: ClassVar[str] = "campaign"
    requires: ClassVar[list[str]] = ["daemon_manager", "dispatcher", "cfx_bytes"]
    provides: ClassVar[list[str]] = ["campaign_name", "campaign_status"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        config = ctx.config
        cfx_bytes = ctx.artifacts.get("cfx_bytes")
        dispatcher: CommandDispatcher = ctx.artifacts.get("dispatcher")
        _daemon: SQXDaemonManager = ctx.artifacts.get("daemon_manager")

        if cfx_bytes is None:
            raise CampaignError("No CFX bytes available for campaign")

        # Load CFX config
        with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
            tmp.write(cfx_bytes)
            cfx_path = Path(tmp.name)

        try:
            await dispatcher.load_config(cfx_path)
        finally:
            cfx_path.unlink(missing_ok=True)

        # Start campaign
        campaign_name = config.get("campaign_name", "Campaign")
        await dispatcher.start_project(campaign_name)

        # Poll for completion
        poll_interval = config.get("poll_interval", 30.0)
        poll_timeout = config.get("poll_timeout", 3600.0)

        start = time.time()
        while time.time() - start < poll_timeout:
            status = await dispatcher.get_status(campaign_name)

            if status.is_complete:
                return {"campaign_name": campaign_name, "campaign_status": status}

            if status.is_failed:
                raise CampaignError(
                    f"Campaign failed: {status.error_message}",
                    phase="poll",
                    campaign_name=campaign_name,
                )

            await asyncio.sleep(poll_interval)

        # Timeout
        await dispatcher.stop_project(campaign_name)
        raise CampaignError(
            f"Campaign timeout after {poll_timeout}s",
            phase="poll",
            campaign_name=campaign_name,
        )


class SQXExportStage(ExportStage):
    """Export campaign results in configured formats."""

    name: ClassVar[str] = "export"
    requires: ClassVar[list[str]] = ["campaign_name", "dispatcher"]
    provides: ClassVar[list[str]] = ["export_paths"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        config = ctx.config
        campaign_name = ctx.artifacts.get("campaign_name") or config.get(
            "campaign_name", "Campaign"
        )
        dispatcher: CommandDispatcher = ctx.artifacts.get("dispatcher")

        export_formats = config.get("export_formats", ["csv"])
        export_databanks = config.get("export_databanks", True)
        output_dir = Path(config.get("output_dir", "_output")) / campaign_name
        output_dir.mkdir(parents=True, exist_ok=True)

        exports = {}

        # Export results
        if "csv" in export_formats:
            path = await dispatcher.export_results(campaign_name, output_dir)
            exports["results_csv"] = Path(path)

        # Export databanks
        if export_databanks:
            db_dir = output_dir / "databanks"
            db_paths = await dispatcher.export_databanks(campaign_name, db_dir)
            for p in db_paths:
                exports[f"databank_{Path(p).name}"] = Path(p)

        return {"export_paths": exports}


class SQXReadStage(ReadStage):
    """Read exported CSV/XLSX files into structured data."""

    name: ClassVar[str] = "read"
    requires: ClassVar[list[str]] = ["export_paths"]
    provides: ClassVar[list[str]] = ["parsed_results"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        export_paths = ctx.artifacts.get("export_paths", {})
        reader = DatabankCSVReader()

        trades = []
        equity = []
        summary = {}

        for path in export_paths.values():
            if path.suffix == ".csv":
                if "trades" in path.name.lower():
                    trades = reader.read_trades(path)
                elif "equity" in path.name.lower():
                    equity = reader.read_equity(path)
                elif "summary" in path.name.lower():
                    summary = reader.read_summary(path)

        return {
            "trades": trades,
            "equity": equity,
            "summary": summary,
        }


class SQXComputeStatsStage(ComputeStatsStage):
    """Compute trading statistics from trades and equity."""

    name: ClassVar[str] = "compute_stats"
    requires: ClassVar[list[str]] = ["parsed_results"]
    provides: ClassVar[list[str]] = ["statistics"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        parsed = ctx.artifacts.get("parsed_results", {})
        trades = parsed.get("trades", [])
        equity = parsed.get("equity", [])

        engine = StatisticsEngine()
        result = engine.compute_all(
            trades=trades,
            equity=equity,
            returns=[t.profit for t in trades] if trades else [],
        )

        return {
            "profit_factor": result.profit_factor,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "expectancy": result.expectancy,
            "mar_ratio": result.mar_ratio,
            "win_rate": result.win_rate,
            "total_trades": len(trades),
        }


class SQXKnowledgeStoreStage(KnowledgeStoreStage):
    """Store campaign artifacts in Knowledge Lake."""

    name: ClassVar[str] = "knowledge_store"
    requires: ClassVar[list[str]] = ["parsed_results", "statistics", "cfx_bytes", "export_paths"]
    provides: ClassVar[list[str]] = ["artifact_paths"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        config = ctx.config
        knowledge_root = config.get("knowledge_root")

        if not knowledge_root:
            return {"artifact_paths": {}}

        store = KnowledgeStore(root=knowledge_root)
        store.initialize()

        artifacts = {}
        campaign_name = config.get("campaign_name", "Campaign")
        campaign_id = re.sub(r"[^A-Za-z0-9._-]", "_", campaign_name) or "campaign"
        campaign_dir = Path(knowledge_root) / "structured" / campaign_id

        # Store CFX (config_writer -> structured/*/**)
        cfx_bytes = ctx.artifacts.get("cfx_bytes")
        if cfx_bytes:
            cfx_path = campaign_dir / f"{campaign_id}.cfx"
            assert_conformance(
                "config_writer", str(cfx_path.relative_to(Path(knowledge_root)))
            )
            cfx_path.parent.mkdir(parents=True, exist_ok=True)
            cfx_path.write_bytes(cfx_bytes)
            artifacts["cfx"] = cfx_path

        # Store results (config_writer -> structured/*/**; per-artifact subdir)
        export_paths = ctx.artifacts.get("export_paths", {})
        for name, path in export_paths.items():
            dest = campaign_dir / "results" / path.name
            assert_conformance(
                "config_writer", str(dest.relative_to(Path(knowledge_root)))
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(path.read_bytes())
            artifacts[name] = dest

        # Store statistics (metrics_writer -> structured/*/metrics.yaml)
        stats = ctx.artifacts.get("statistics", {})
        stats_path = campaign_dir / "metrics.yaml"
        assert_conformance(
            "metrics_writer", str(stats_path.relative_to(Path(knowledge_root)))
        )
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(yaml.dump(stats))
        artifacts["statistics"] = stats_path

        # Rebuild index
        store.rebuild_index()

        return {"artifact_paths": artifacts}


class SQXReportStage(ReportStage):
    """Generate campaign report delegating to ReportGenerator."""

    name: ClassVar[str] = "report"
    requires: ClassVar[list[str]] = ["parsed_results", "statistics"]
    provides: ClassVar[list[str]] = ["report_path", "report_html", "report_json", "report_charts"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        # Delegate to Phase 5b ReportGenerator
        from pathlib import Path

        from quantlab.reporting.generator import ReportGenerator
        from quantlab.reporting.models import ReportConfig, ReportFormat, ReportTheme

        campaign_name = ctx.config.get("campaign_name", "campaign")
        output_dir = Path(ctx.config.get("output_dir", "reports"))
        statistics = ctx.artifacts.get("statistics", {})
        trades = ctx.artifacts.get("trades", [])
        equity = ctx.artifacts.get("equity", [])

        config = ReportConfig(
            campaign_id=campaign_name,
            output_dir=output_dir,
            formats=[ReportFormat.HTML, ReportFormat.JSON],
            include_charts=True,
            theme=ReportTheme.DARK,
            title=f"Campaign: {campaign_name}",
        )

        # Convert stats dict to StatsResult if needed
        if isinstance(statistics, dict):
            from quantlab.stats.models import StatsResult

            statistics = StatsResult(
                **{k: v for k, v in statistics.items() if k in StatsResult.model_fields}
            )

        generator = ReportGenerator(config)
        result = generator.generate(
            campaign_id=campaign_name,
            trades=trades,
            equity=equity,
            statistics=statistics,
        )

        artifacts = {}
        if result.html_path:
            artifacts["report_path"] = str(result.html_path)
            artifacts["report_html"] = str(result.html_path)
        if result.json_path:
            artifacts["report_json"] = str(result.json_path)
        if result.charts_generated:
            artifacts["report_charts"] = result.charts_generated

        return {"artifact_paths": artifacts}
