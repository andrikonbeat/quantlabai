"""ArchiverStage — pipeline adapter for :class:`Archiver` (REQ-33).

Wraps the archive agent as a ``Stage`` so the orchestrated pipeline can run
it after the demo phase. Reads ``guardian_state`` from the context artifacts
(produced by the ``guardian_evaluate`` stage), composes the portfolio data
from context, runs the injectable archiver, and publishes ``archive_result``.
The HUMAN_APPROVE_ARCHIVE human confirmation is enforced by the surrounding
archive phase gate, not by this stage.
"""

from __future__ import annotations

from typing import Any

from quantlab.pipeline.base import PipelineContext, Stage


class ArchiverStage(Stage):
    """Compose and persist the archive maintenance artifacts (REQ-33).

    **Requires**: guardian_state
    **Provides**: archive_result
    """

    name: str = "archiver"
    requires: list[str] = ["guardian_state"]
    provides: list[str] = ["archive_result"]

    def __init__(self, archiver: Any | None = None) -> None:
        # Injectable for tests; the real Archiver is constructed lazily.
        self._archiver = archiver

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Run the archive agent for the configured campaign.

        Args:
            ctx: Pipeline context with ``guardian_state`` artifact and
                config keys (``campaign_id``, ``deployed_strategy_id``,
                ``knowledge_root``); portfolio data is read from artifacts
                (``equity_points``, ``portfolio_candidates``,
                ``parameter_matrix``) when present.

        Returns:
            Dict with ``archive_result`` (an :class:`ArchiveResult`).
        """
        campaign_id = "campaign"
        if ctx.config and ctx.config.get("campaign_id"):
            campaign_id = str(ctx.config["campaign_id"])

        guardian_state = ctx.artifacts.get("guardian_state")
        portfolio_data = {
            "deployed_strategy_id": str(
                (ctx.config or {}).get("deployed_strategy_id", "")
            ),
            "equity_points": ctx.artifacts.get("equity_points")
            or ctx.artifacts.get("live_equity")
            or [],
            "portfolio_candidates": list(
                ctx.artifacts.get("portfolio_candidates") or []
            ),
            "strategy_state": (ctx.config or {}).get("strategy_state")
            or ctx.artifacts.get("strategy_state"),
            "parameter_matrix": ctx.artifacts.get("parameter_matrix"),
            "candidate_metrics": ctx.artifacts.get("candidate_metrics") or {},
            "knowledge_root": (ctx.config or {}).get("knowledge_root", "knowledge"),
        }

        archiver = self._archiver
        if archiver is None:  # pragma: no cover - exercised by integration
            from quantlab.agents.archiver import Archiver

            archiver = Archiver()

        result = await archiver.archive(campaign_id, guardian_state, portfolio_data)
        ctx.artifacts["archive_result"] = result
        return {"archive_result": result}
