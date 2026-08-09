"""F5: dispatch handoff failure holds safely and preserves the build artifact.

Spec (builder-agent REQ-2 scenarios):
- GIVEN the substrate handoff fails THEN the CFX archive remains preserved for
  recovery AND the operation fails safely (the campaign does NOT advance and
  does NOT lose the build).

Strict TDD: written first — RED until DispatchStage fails closed on error.
"""

from __future__ import annotations

import pytest

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.dispatch_stage import (
    GATE_DECISION_ARTIFACT,
    DispatchStage,
)


class _FailingBuilder:
    """A builder whose dispatch boundary always raises (substrate handoff)."""

    async def _dispatch_single(self, **kwargs):
        raise RuntimeError("sqcli daemon unreachable — handoff failed")


class TestDispatchFailureHold:
    """DispatchStage fails closed on handoff failure (REQ-2)."""

    @pytest.mark.asyncio
    async def test_failure_sets_hold_and_preserves_cfx(self) -> None:
        """GIVEN the gate approved and the dispatch boundary raises
        WHEN the dispatch stage runs
        THEN sqcli_status is "HOLD" with a dispatch_error
        AND the cfx_bytes artifact is retained for recovery.
        """
        stage = DispatchStage(builder=_FailingBuilder())
        ctx = PipelineContext(
            config={},
            artifacts={
                "cfx_bytes": b"cfx-preserved-for-recovery",
                GATE_DECISION_ARTIFACT: {"action": "approved"},
            },
        )

        result = await stage.execute(ctx)

        assert result["sqcli_status"] == "HOLD"
        assert result["campaign_id"] is None
        assert "sqcli daemon unreachable" in ctx.artifacts.get("dispatch_error", "")
        # REQ-2: the CFX archive is preserved for recovery on handoff failure.
        assert ctx.artifacts["cfx_bytes"] == b"cfx-preserved-for-recovery"
        assert ctx.artifacts.get("sqcli_status") == "HOLD"
