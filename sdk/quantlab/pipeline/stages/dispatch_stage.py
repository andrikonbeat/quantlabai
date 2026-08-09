"""DispatchStage — encapsulates the SQX dispatch step (AD-8).

In the orchestrated pipeline the builder splits translation/validation/license
from dispatch: ``BuilderAgent.run`` skips Phase-4 dispatch when
``orchestrated``, and this stage drives the builder's ``_dispatch_single``
boundary instead (AD-3/AD-8).

The stage respects the HUMAN_APPROVE_CONFIG gate: without an approval decision
the dispatch is blocked and never reaches the builder (REQ-05/06, D2). It only
dispatches — it NEVER deploys (D4, no deploy orchestration in scope).
"""

from __future__ import annotations

import logging
from typing import Any

from quantlab.agents.builder_agent import BuilderAgent
from quantlab.pipeline.base import PipelineContext, Stage

logger = logging.getLogger(__name__)

# Gate approval actions accepted by the dispatch stage. ``approved`` is the
# value written by GateInterceptorStage; ``approve`` by gates.callbacks decisions.
_APPROVED_ACTIONS = frozenset({"approved", "approve", "APPROVED", "APPROVE"})

# Gate that must approve the build config before dispatch (REQ-06).
HUMAN_APPROVE_CONFIG_GATE = "HUMAN_APPROVE_CONFIG"
# Artifact key written by GateInterceptorStage (see gate_interceptor.execute).
GATE_DECISION_ARTIFACT = f"gate_decision_{HUMAN_APPROVE_CONFIG_GATE}"


class DispatchStage(Stage):
    """Dispatch the built campaign via the builder (AD-8).

    **Requires**: cfx_bytes
    **Provides**: campaign_id, sqcli_status, export_paths
    """

    name: str = "dispatch"
    requires: list[str] = ["cfx_bytes"]
    provides: list[str] = ["campaign_id", "sqcli_status", "export_paths"]

    def __init__(
        self,
        builder: BuilderAgent | None = None,
        skip_data_check: bool = False,
    ) -> None:
        # Injectable for tests; the real builder is constructed lazily so
        # registry instantiation stays side-effect free.
        self._builder = builder
        self._skip_data_check = skip_data_check

    @staticmethod
    def _gate_approved(ctx: PipelineContext) -> bool:
        """Return True only when the HUMAN_APPROVE_CONFIG gate approved."""
        gate_decision = ctx.artifacts.get(GATE_DECISION_ARTIFACT)
        if gate_decision is None:
            return False
        if isinstance(gate_decision, dict):
            action = gate_decision.get("action")
        else:
            action = getattr(gate_decision, "action", None)
        return (action or "").lower() in _APPROVED_ACTIONS

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Dispatch the campaign via the builder, honouring the human gate.

        Args:
            ctx: Pipeline context with ``cfx_bytes`` and the
                ``HUMAN_APPROVE_CONFIG`` gate decision.

        Returns:
            Dict with campaign_id, sqcli_status, export_paths — or
            ``dispatch_blocked: True`` when the gate did not approve.
        """
        if not self._gate_approved(ctx):
            ctx.artifacts["dispatch_blocked"] = True
            return {
                "dispatch_blocked": True,
                "campaign_id": None,
                "sqcli_status": None,
                "export_paths": [],
            }

        builder = self._builder
        if builder is None:  # pragma: no cover - exercised by integration
            builder = BuilderAgent()

        build_config = ctx.artifacts.get("build_config")
        research_config = ctx.artifacts.get("research_config")
        try:
            result = await builder._dispatch_single(
                cfx_bytes=ctx.artifacts["cfx_bytes"],
                config=research_config,
                skip_data_check=self._skip_data_check,
                campaign_id=getattr(research_config, "campaign", None),
                build_config=build_config,
                # DispatchStage is the orchestrated dispatch boundary (AD-8):
                # the data pre-flight is a HARD check (REQ-13).
                orchestrated=True,
            )
        except Exception as exc:
            # REQ-2 (builder-agent): the substrate handoff failed — fail safe.
            # The CFX archive stays in context (preserved for recovery), the
            # operation holds instead of advancing, and the error is recorded
            # for the human review gate.
            logger.warning(
                "DispatchStage: handoff failed for '%s' — holding: %s",
                getattr(research_config, "campaign", "?"),
                exc,
            )
            ctx.artifacts["sqcli_status"] = "HOLD"
            ctx.artifacts["dispatch_error"] = str(exc)
            return {
                "campaign_id": None,
                "sqcli_status": "HOLD",
                "export_paths": [],
                "dispatch_error": str(exc),
            }

        campaign_id = getattr(result, "campaign_id", None)
        sqcli_status = getattr(result, "sqcli_status", None)
        export_paths = getattr(result, "export_paths", [])

        ctx.artifacts["campaign_id"] = campaign_id
        ctx.artifacts["sqcli_status"] = sqcli_status
        ctx.artifacts["export_paths"] = export_paths
        return {
            "campaign_id": campaign_id,
            "sqcli_status": sqcli_status,
            "export_paths": export_paths,
        }
