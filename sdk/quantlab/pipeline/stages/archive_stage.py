"""ArchiveStage — composes the maintenance/replacement plan + stats + bundle (REQ-33, REQ-01 phase 13).

Consumes the demo outcome and runs the archive phase: maintenance/replacement
plan from Guardian degradation + portfolio candidates, account statistics
over the demo window, and the archived artifact bundle. The HUMAN_APPROVE_ARCHIVE
gate is consumed inside ``ArchivePhase.run`` (REQ-38 s3) — denial returns the
campaign to maintenance. The phase is injectable for deterministic tests.
"""

from __future__ import annotations

from typing import Any

from quantlab.pipeline.base import PipelineContext, Stage


class ArchiveStage(Stage):
    """Archive the campaign with plan, stats, and bundle (REQ-33).

    **Requires**: demo_result
    **Provides**: archive_bundle
    """

    name: str = "archive"
    requires: list[str] = ["demo_result"]
    provides: list[str] = ["archive_bundle"]

    def __init__(self, phase: Any | None = None) -> None:
        # Injectable for tests; the real ArchivePhase is constructed lazily.
        self._phase = phase

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Run the archive phase and publish the bundle.

        Args:
            ctx: Pipeline context with ``demo_result`` and
                ``config.campaign_id``.

        Returns:
            Dict with ``archive_bundle`` (plan + stats + artifacts).
        """
        campaign_id = "campaign"
        if ctx.config and ctx.config.get("campaign_id"):
            campaign_id = str(ctx.config["campaign_id"])

        phase = self._phase
        if phase is None:  # pragma: no cover - exercised by integration
            from quantlab.phase4.campaign_archive import ArchivePhase

            phase = ArchivePhase()

        bundle = await phase.run(campaign_id)
        ctx.artifacts["archive_bundle"] = bundle
        return {"archive_bundle": bundle}
