"""F4: LiveOpsStage — the canonical live-ops phase after archive (REQ-01 p14).

Spec (pipeline-orchestration REQ-6):
- "live_ops" is registered in the StageRegistry mapping to LiveOpsStage.
- LiveOpsStage requires the archive state (archive_status + maintenance_plan,
  carried by the archive_bundle) and provides live_ops_status.

Strict TDD: written first — RED until the stage and its wiring exist.
"""

from __future__ import annotations

import pytest

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.live_ops_stage import LiveOpsStage


def _bundle_with_plan() -> dict:
    return {
        "status": "ARCHIVED",
        "maintenance_plan": {
            "campaign_id": "live-001",
            "review_cycle_days": 30,
            "replacement_candidates": [],
        },
    }


class TestLiveOpsStage:
    """LiveOpsStage publishes a live_ops_status from the archive state."""

    @pytest.mark.asyncio
    async def test_execute_publishes_live_ops_status(self) -> None:
        """GIVEN an archived campaign with a maintenance plan
        WHEN the live-ops stage runs
        THEN ctx.artifacts["live_ops_status"] reports status "live" with the
        archive status and maintenance plan attached.
        """
        stage = LiveOpsStage()
        ctx = PipelineContext(
            config={},
            artifacts={"archive_bundle": _bundle_with_plan()},
        )

        result = await stage.execute(ctx)

        assert "live_ops_status" in ctx.artifacts
        live = ctx.artifacts["live_ops_status"]
        assert live["status"] == "live"
        assert live["archive_status"] == "ARCHIVED"
        assert live["maintenance_plan"]["review_cycle_days"] == 30
        assert result["live_ops_status"] == live

    @pytest.mark.asyncio
    async def test_missing_archive_bundle_keeps_hold_status(self) -> None:
        """GIVEN no archive bundle (archive did not run)
        THEN live-ops must not claim a live account — status stays "hold"
        (fail-closed: never publish "live" without an archive state).
        """
        stage = LiveOpsStage()
        ctx = PipelineContext(config={}, artifacts={})

        result = await stage.execute(ctx)

        assert ctx.artifacts["live_ops_status"]["status"] == "hold"
        assert result["live_ops_status"]["status"] == "hold"
