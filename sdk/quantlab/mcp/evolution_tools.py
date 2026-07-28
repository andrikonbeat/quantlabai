"""MCP tools wrapping the Strategic Evolution Engine.

Each function is registered as an MCP tool via the ``register()`` function,
which the bridge calls at startup.  Tools delegate to ``EvolutionOrchestrator``
and ``CandidatePool``, serialise with ``model_dump(mode="json")``, and
return JSON strings.
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
    """Register all evolution-related MCP tools on the server."""

    mcp = srv.mcp

    @mcp.tool(
        name="generate_candidates",
        description="Generate evolution candidates for a given strategy.",
    )
    async def generate_candidates(strategy_id: str, count: int = 5) -> str:
        """Generate new strategy candidates via the evolution engine.

        Args:
            strategy_id: The strategy to evolve.
            count: Number of candidates to generate (default 5).

        Returns:
            JSON string with the evolution result.
        """
        try:
            from quantlab.evolution import EvolutionCandidate

            orchestrator = srv.evolution_orchestrator
            # The orchestrator.genetic.optimize is the primary generator path.
            # We call it synchronously for on-demand generation.
            if orchestrator._genetic is not None:
                candidates = await orchestrator._genetic.optimize(
                    strategy_id=strategy_id,
                    cfx_content="",
                )
                for c in candidates:
                    orchestrator.pool.add(c)

                result_dict: dict[str, Any] = {
                    "strategy_id": strategy_id,
                    "candidates_generated": len(candidates),
                    "candidates": [
                        c.model_dump(mode="json") for c in candidates
                    ],
                }
            else:
                result_dict = {
                    "strategy_id": strategy_id,
                    "candidates_generated": 0,
                    "message": "Genetic optimizer not configured.",
                }

            return json.dumps(result_dict, default=str)
        except Exception as exc:
            logger.exception("generate_candidates failed")
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Candidate generation failed: {exc}",
                details={"strategy_id": strategy_id},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)

    @mcp.tool(
        name="query_pool",
        description="Query the candidate pool, optionally filtered by status.",
    )
    async def query_pool(status: str | None = None) -> str:
        """Query evolution candidates from the pool.

        Args:
            status: Optional filter — one of ``pending``, ``passed``,
                ``failed``, ``promoted``.  ``None`` returns all candidates.

        Returns:
            JSON string with the matching candidates.
        """
        try:
            from quantlab.evolution.models import CandidateStatus

            pool = srv.candidate_pool

            if status:
                try:
                    candidate_status = CandidateStatus(status)
                except ValueError:
                    error = MCPError(
                        code=ErrorCode.INVALID_REQUEST,
                        message=f"Invalid status '{status}'. Valid values: {[s.value for s in CandidateStatus]}",
                        details={"status": status},
                    )
                    return json.dumps(error.model_dump(mode="json"), default=str)

                candidates = pool.get_by_status(candidate_status)
            else:
                candidates = pool.load_all()

            return json.dumps(
                [c.model_dump(mode="json") for c in candidates],
                default=str,
            )
        except Exception as exc:
            logger.exception("query_pool failed")
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Pool query failed: {exc}",
            )
            return json.dumps(error.model_dump(mode="json"), default=str)

    @mcp.tool(
        name="promote_candidate",
        description="Promote a candidate to active strategy status.",
    )
    async def promote_candidate(candidate_id: str) -> str:
        """Promote an evolution candidate to active status.

        Args:
            candidate_id: The candidate to promote.

        Returns:
            JSON string indicating success or failure.
        """
        try:
            pool = srv.candidate_pool
            success = pool.promote(candidate_id)

            if success:
                return json.dumps({
                    "candidate_id": candidate_id,
                    "promoted": True,
                    "message": f"Candidate {candidate_id} promoted successfully.",
                }, default=str)
            else:
                error = MCPError(
                    code=ErrorCode.NOT_FOUND,
                    message=f"Candidate '{candidate_id}' not found in pool.",
                    details={"candidate_id": candidate_id},
                )
                return json.dumps(error.model_dump(mode="json"), default=str)
        except Exception as exc:
            logger.exception("promote_candidate failed")
            error = MCPError(
                code=ErrorCode.PROVIDER_ERROR,
                message=f"Promotion failed: {exc}",
                details={"candidate_id": candidate_id},
            )
            return json.dumps(error.model_dump(mode="json"), default=str)
