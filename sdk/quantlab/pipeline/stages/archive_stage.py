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

            # REQ-38 (s4/s5, ADR-5b): when the run provides a gate event dir,
            # wire a decision-file gate_fn into ArchivePhase so the internal
            # HUMAN_APPROVE_ARCHIVE pending_gate marker is resolved through
            # the same pending.json → decision.json protocol as the pipeline
            # gates. Headless runs (--gate-decisions-file) resolve from the
            # decisions file; otherwise the interactive channel polls for a
            # decision file. With neither configured, ArchivePhase keeps its
            # default HumanGateOrchestrator (fail-closed HOLD → DENIED).
            gate_fn = None
            if ctx.config:
                gate_event_dir = ctx.config.get("gate_event_dir")
                if gate_event_dir:
                    from quantlab.gates.callbacks import (
                        DecisionsFileGateCallback,
                        QuestionToolGateCallback,
                    )

                    decisions_file = ctx.config.get("gate_decisions_file")
                    timeout = ctx.config.get("gate_timeout")
                    gate_fn = (
                        DecisionsFileGateCallback(decisions_file)
                        if decisions_file
                        else QuestionToolGateCallback(
                            gate_event_dir=gate_event_dir,
                            campaign_id=campaign_id,
                            timeout=timeout,
                        )
                    )
            phase = ArchivePhase(gate_fn=gate_fn)

        bundle = await phase.run(campaign_id)
        ctx.artifacts["archive_bundle"] = bundle
        return {"archive_bundle": bundle}
