"""PR2: BuilderAgent unified execution handoff tests.

Validates phase_type and checkpoint_metadata propagation in orchestrated mode,
and parameter_matrix artifact generation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.agents.builder_agent import BuilderAgent
from quantlab.dsl.models import Market, Timeframe
from quantlab.sqx.project_builder import BuildConfig


def _minimal_research_config() -> dict:
    return {
        "campaign": "test_campaign",
        "market": Market.EURUSD.value,
        "timeframe": Timeframe.H1.value,
    }


class TestUnifiedExecutionHandoff:
    """PR2 orchestrated mode handoff behavior."""

    @pytest.mark.asyncio
    async def test_orchestrated_returns_phase_and_checkpoint(self):
        agent = BuilderAgent()
        ctx = MagicMock()
        ctx.artifacts = {"research_config": _minimal_research_config()}
        ctx.config = {
            "orchestrated": True,
            "campaign_id": "pr2_campaign_001",
            "build_config": BuildConfig(generations=20, population=150),
        }

        agent._translate = AsyncMock(return_value=(b"cfx", {}))
        agent._validate = AsyncMock(return_value={"valid": True})
        agent._check_license = AsyncMock(return_value={"valid": True})

        result = await agent.run(ctx)

        assert result["phase_type"] == "builder"
        assert result["checkpoint_metadata"] == {"campaign_id": "pr2_campaign_001"}
        assert result["build_config"] is not None
        assert "parameter_matrix" in ctx.artifacts
        matrix = ctx.artifacts["parameter_matrix"]
        assert len(matrix) == 2
        params = {e["parameter"]: e for e in matrix}
        assert params["generations"]["value"] == 20
        assert params["population"]["value"] == 150

    @pytest.mark.asyncio
    async def test_non_orchestrated_omits_phase_and_checkpoint(self):
        agent = BuilderAgent()
        ctx = MagicMock()
        ctx.artifacts = {"research_config": _minimal_research_config()}
        ctx.config = {
            "orchestrated": False,
            "campaign_id": "pr2_campaign_002",
            "build_config": BuildConfig(sl_required=True),
        }

        agent._translate = AsyncMock(return_value=(b"cfx", {}))
        agent._validate = AsyncMock(return_value={"valid": True})
        agent._check_license = AsyncMock(return_value={"valid": True})

        dispatch_result = MagicMock()
        dispatch_result.cfx_bytes = b"cfx"
        dispatch_result.campaign_id = "pr2_campaign_002"
        dispatch_result.sqcli_status = "completed"
        dispatch_result.export_paths = ["exports/test.csv"]
        dispatch_result.dispatch_log = []
        agent._dispatch_with_retry = AsyncMock(return_value=dispatch_result)

        result = await agent.run(ctx)

        assert "phase_type" not in result
        assert "checkpoint_metadata" not in result
        assert "parameter_matrix" in ctx.artifacts
        assert len(ctx.artifacts["parameter_matrix"]) == 1
        assert ctx.artifacts["parameter_matrix"][0]["parameter"] == "sl_required"

    @pytest.mark.asyncio
    async def test_parameter_matrix_absent_when_no_build_config(self):
        agent = BuilderAgent()
        ctx = MagicMock()
        ctx.artifacts = {"research_config": _minimal_research_config()}
        ctx.config = {
            "orchestrated": True,
            "campaign_id": "pr2_campaign_003",
        }

        agent._translate = AsyncMock(return_value=(b"cfx", {}))
        agent._validate = AsyncMock(return_value={"valid": True})
        agent._check_license = AsyncMock(return_value={"valid": True})

        result = await agent.run(ctx)

        assert "parameter_matrix" not in ctx.artifacts
        assert result["phase_type"] == "builder"
        assert result["checkpoint_metadata"] == {"campaign_id": "pr2_campaign_003"}
