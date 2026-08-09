"""LiveOpsStage — canonical live-ops phase after archive (REQ-01 phase 14, REQ-6).

Consumes the archive state and publishes the live-ops status: the campaign is
deemed ``live`` only when an archive bundle exists (archive status +
maintenance plan ride on the ``archive_bundle`` from ``ArchivePhase.run``).
Without an archive state the stage fails closed — it never claims a live
account (status ``hold``), so a campaign that never reached the archive phase
cannot be reported as live.
"""

from __future__ import annotations

from typing import Any

from quantlab.pipeline.base import PipelineContext, Stage


class LiveOpsStage(Stage):
    """Start live-ops monitoring for the archived campaign (REQ-6).

    **Requires**: archive_bundle
    **Provides**: live_ops_status
    """

    name: str = "live_ops"
    requires: list[str] = ["archive_bundle"]
    provides: list[str] = ["live_ops_status"]

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Publish ``live_ops_status`` from the archive state.

        Args:
            ctx: Pipeline context with the ``archive_bundle`` artifact.

        Returns:
            Dict with ``live_ops_status`` (status "live" with the archive
            status and maintenance plan, or "hold" fail-closed without one).
        """
        bundle = ctx.artifacts.get("archive_bundle")
        if bundle is None:
            # Fail-closed: without an archive state the campaign cannot be
            # reported as live (never auto-approve, REQ-11/REQ-38).
            ctx.artifacts["live_ops_status"] = {
                "status": "hold",
                "archive_status": None,
                "maintenance_plan": None,
            }
            return {"live_ops_status": ctx.artifacts["live_ops_status"]}

        if isinstance(bundle, dict):
            archive_status = bundle.get("status")
            maintenance_plan = bundle.get("maintenance_plan") or bundle.get("plan")
        else:
            archive_status = getattr(bundle, "status", None)
            maintenance_plan = getattr(bundle, "maintenance_plan", None) or getattr(
                bundle, "plan", None
            )

        live_ops_status = {
            "status": "live",
            "archive_status": archive_status,
            "maintenance_plan": maintenance_plan,
        }
        ctx.artifacts["live_ops_status"] = live_ops_status
        return {"live_ops_status": live_ops_status}
