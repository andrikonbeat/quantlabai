"""MCP tools wrapping the Health Score and MetaGuardian subsystems.

Each function is registered as an MCP tool via the ``register()`` function,
which the bridge calls at startup.  Tools delegate to ``HealthScoreCalculator``
and ``MetaGuardianOrchestrator``, serialise with ``model_dump(mode="json")``,
and return JSON strings.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from quantlab.mcp.models import ErrorCode, MCPError

if TYPE_CHECKING:
    from quantlab.mcp.bridge import QuantLabMCPServer

logger = logging.getLogger(__name__)


def register(srv: QuantLabMCPServer) -> None:
    """Register all health-related MCP tools on the server."""

    mcp = srv.mcp

    @mcp.tool(
        name="evaluate_strategy",
        description="Evaluate a strategy's health using MetaGuardian.",
    )
    async def evaluate_strategy(strategy_id: str) -> str:
        """Run a full health evaluation on a strategy.

        Args:
            strategy_id: The strategy to evaluate.

        Returns:
            JSON string with the evaluation result.
        """
        try:
            guardian = srv.meta_guardian
            portfolio_state = guardian.evaluate()

            # Build a human-readable summary from guardian results
            result: dict[str, Any] = {
                "strategy_id": strategy_id,
                "portfolio_state": portfolio_state.value,
                "state_history": [
                    {"state": s.value, "timestamp": t}
                    for s, t in guardian.state_history
                ],
            }

            return json.dumps(result, default=str)
        except Exception as exc:
            logger.exception("evaluate_strategy failed")
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Strategy evaluation failed: {exc}",
                details={"strategy_id": strategy_id},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)

    @mcp.tool(
        name="get_health_metrics",
        description="Retrieve health metrics for a strategy over a time period.",
    )
    async def get_health_metrics(strategy_id: str, period: str = "90d") -> str:
        """Get health score metrics for a strategy.

        Period currently returns a scored assessment without requiring
        ``StatsResult`` input.  Pass ``stats_json`` to ``compute_fitness``
        for a full computation.

        Args:
            strategy_id: The strategy to assess.
            period: Time window (e.g. ``"30d"``, ``"90d"``, ``"1y"``).

        Returns:
            JSON string with health metrics.
        """
        try:
            calculator = srv.health_calculator

            # Without a real StatsResult, we return a scaffolding response
            # that tells callers how to supply data via compute_fitness.
            result: dict[str, Any] = {
                "strategy_id": strategy_id,
                "period": period,
                "message": (
                    "No stored StatsResult available for this strategy. "
                    "Use the compute_fitness tool with a stats_json argument "
                    "to compute health metrics from raw statistics."
                ),
                "available_metrics": [
                    "profit_factor",
                    "sharpe_ratio",
                    "sortino_ratio",
                    "max_drawdown",
                    "recovery_factor",
                    "win_rate",
                    "expectancy_ratio",
                ],
            }

            return json.dumps(result, default=str)
        except Exception as exc:
            logger.exception("get_health_metrics failed")
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Health metrics retrieval failed: {exc}",
                details={"strategy_id": strategy_id},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)

    @mcp.tool(
        name="compute_fitness",
        description="Compute a health/fitness score from raw strategy statistics.",
    )
    async def compute_fitness(stats_json: str) -> str:
        """Compute a health score from a JSON stats payload.

        The ``stats_json`` argument must be a JSON string matching the
        ``StatsResult`` schema::

            {
              "profit_factor": 1.5,
              "sharpe_ratio": 0.8,
              "sortino_ratio": 1.2,
              "max_drawdown": 0.15,
              "recovery_factor": 2.0,
              "win_rate": 0.55,
              "expectancy_ratio": 0.3
            }

        All fields are optional — missing metrics are excluded from the
        weighted average.

        Args:
            stats_json: JSON string of strategy statistics.

        Returns:
            JSON string with the computed health score.
        """
        try:
            from quantlab.stats.models import StatsResult

            stats_data: dict[str, Any] = json.loads(stats_json)
            stats = StatsResult(**stats_data)
            calculator = srv.health_calculator

            health = calculator.compute(stats, period="manual")
            return json.dumps(health.model_dump(mode="json"), default=str)
        except json.JSONDecodeError as exc:
            error = MCPError(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Invalid JSON in stats_json: {exc}",
                details={"stats_json": stats_json},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)
        except Exception as exc:
            logger.exception("compute_fitness failed")
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Fitness computation failed: {exc}",
            )
            return json.dumps(error.model_dump(mode="json"), default=str)
