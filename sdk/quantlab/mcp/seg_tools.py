"""SEG MCP tools — strategy generation via StrategyGenerator facade."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from quantlab.evolution.seg import StrategyGenerator

if TYPE_CHECKING:
    from quantlab.mcp.bridge import QuantLabMCPServer

logger = logging.getLogger(__name__)

_generator: StrategyGenerator | None = None


def get_generator() -> StrategyGenerator:
    """Lazy singleton for StrategyGenerator."""
    global _generator
    if _generator is None:
        _generator = StrategyGenerator()
    return _generator


def register(srv: QuantLabMCPServer) -> None:
    """Register SEG tools with the MCP server."""

    mcp = srv.mcp

    @mcp.tool(description="Generate trading strategies from intent parameters")
    async def generate_strategy(
        market: str = "forex",
        timeframe: str = "H1",
        risk_profile: str = "moderate",
        objective: str = "trend_following",
        count: int = 5,
        mode: str = "full",
    ) -> str:
        """Generate and validate strategies based on user intent.

        Args:
            market: Target market (forex, stocks, futures).
            timeframe: Trading timeframe (M15, H1, H4, D1).
            risk_profile: Risk tolerance (conservative, moderate, aggressive).
            objective: Strategy objective (trend_following, mean_reversion, breakout).
            count: Number of candidates to generate.
            mode: Evolution mode (full, genetic_only, generative_only).

        Returns:
            JSON string with ranked candidate results.
        """
        generator = get_generator()
        intent = {
            "market": market,
            "timeframe": timeframe,
            "risk_profile": risk_profile,
            "objective": objective,
            "count": min(count, 20),
            "mode": mode,
        }
        try:
            candidates = await generator.generate(intent)
            results = []
            for c in candidates:
                results.append({
                    "candidate_id": c.candidate_id,
                    "strategy_id": c.strategy_id,
                    "mode": c.mode.value,
                    "status": c.status.value,
                    "fitness_score": c.fitness_score,
                    "parent_candidate_id": c.parent_candidate_id,
                })
            return json.dumps({
                "success": True,
                "count": len(results),
                "candidates": results,
            })
        except Exception as exc:
            logger.exception("Strategy generation failed")
            return json.dumps({
                "success": False,
                "error": str(exc),
                "count": 0,
                "candidates": [],
            })
