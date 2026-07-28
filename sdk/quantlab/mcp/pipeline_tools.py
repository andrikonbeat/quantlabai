"""MCP tools wrapping the Pipeline subsystem.

Each function is registered as an MCP tool via the ``register()`` function,
which the bridge calls at startup.  Tools are thin wrappers — they parse
inputs, delegate to ``PipelineRunner`` / ``PipelineRegistry``, serialise
results with ``model_dump(mode="json")``, and return JSON strings.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from quantlab.mcp.models import ErrorCode, MCPError

if TYPE_CHECKING:
    from quantlab.mcp.bridge import QuantLabMCPServer

logger = logging.getLogger(__name__)


def _pipeline_result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a ``PipelineResult`` (dataclass) to a JSON-safe dict."""
    stages: list[dict[str, Any]] = []
    for s in getattr(result, "stages", []):
        stages.append({
            "stage_name": s.stage_name,
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "duration": s.duration,
            "error": s.error,
            "output": str(s.output) if s.output is not None else None,
            "started_at": (
                s.started_at.isoformat() if hasattr(s.started_at, "isoformat") else str(s.started_at)
            ),
            "completed_at": (
                s.completed_at.isoformat()
                if s.completed_at and hasattr(s.completed_at, "isoformat")
                else str(s.completed_at) if s.completed_at else None
            ),
        })

    return {
        "pipeline_name": getattr(result, "pipeline_name", ""),
        "total_duration": getattr(result, "total_duration", 0.0),
        "error": getattr(result, "error", None),
        "is_successful": getattr(result, "is_successful", False),
        "stages": stages,
    }


def register(srv: QuantLabMCPServer) -> None:
    """Register all pipeline-related MCP tools on the server."""

    mcp = srv.mcp

    @mcp.tool(name="run_backtest", description="Run a backtest pipeline with the given configuration.")
    async def run_backtest(
        pipeline_config: str,
        symbol: str,
        start: str,
        end: str,
    ) -> str:
        """Run a pipeline backtest.

        Args:
            pipeline_config: JSON string describing the pipeline configuration.
            symbol: Trading symbol to backtest (e.g. ``"BTC-USD"``).
            start: Start date in ``YYYY-MM-DD`` format.
            end: End date in ``YYYY-MM-DD`` format.

        Returns:
            JSON string with the pipeline result or an error.
        """
        try:
            from quantlab.pipeline import Pipeline, PipelineContext, PipelineRunner

            config_dict: dict[str, Any] = json.loads(pipeline_config)
            pipeline_name = config_dict.get("name", "backtest")

            pipeline = Pipeline(name=pipeline_name)
            ctx = PipelineContext(
                symbol=symbol,
                start_date=start,
                end_date=end,
            )

            runner: PipelineRunner = srv.pipeline_runner
            result = await runner.run(pipeline, ctx)

            return json.dumps(_pipeline_result_to_dict(result), default=str)
        except Exception as exc:
            logger.exception("run_backtest failed")
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Backtest failed: {exc}",
                details={"pipeline_config": pipeline_config, "symbol": symbol},
            )
            return error.model_dump(mode="json")

    @mcp.tool(name="list_pipelines", description="List all available pipeline configurations.")
    async def list_pipelines() -> str:
        """Return a list of all discovered pipeline configurations.

        Returns:
            JSON string with discovered pipeline summaries.
        """
        try:
            from quantlab.pipeline import PipelineRegistry

            registry = PipelineRegistry()
            summaries = registry.list()
            results: list[dict[str, Any]] = []
            for s in summaries:
                results.append({
                    "name": s.name,
                    "stage_count": s.stage_count,
                    "description": s.description,
                })
            return json.dumps(results, default=str)
        except Exception as exc:
            logger.exception("list_pipelines failed")
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Failed to list pipelines: {exc}",
            )
            return json.dumps(error.model_dump(mode="json"), default=str)

    @mcp.tool(name="get_pipeline_run", description="Retrieve a previous pipeline run by ID.")
    async def get_pipeline_run(run_id: str) -> str:
        """Get a previously executed pipeline run.

        Args:
            run_id: Unique run identifier.

        Returns:
            JSON string with the run details or an error.
        """
        try:
            from quantlab.pipeline import PipelineRun

            # In-memory runs are ephemeral — log the lookup for observability.
            # A production implementation would query the Knowledge Lake.
            logger.info("Pipeline run lookup requested: %s", run_id)
            return json.dumps({
                "run_id": run_id,
                "message": "Run details are available in the Knowledge Lake (query not yet implemented).",
            }, default=str)
        except Exception as exc:
            logger.exception("get_pipeline_run failed")
            error = MCPError(
                code=ErrorCode.NOT_FOUND,
                message=f"Pipeline run not found: {exc}",
                details={"run_id": run_id},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)
