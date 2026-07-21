"""Unit tests for DeploymentAgent — tasks 4.8-4.11, 4.14.

Tests:
- CFX validation (task 4.10 dry-run validation)
- JForex packaging (task 4.9)
- JCloud config generation (task 4.9)
- Dry-run mode produces artifacts without upload (task 4.10)
- Invalid CFX produces DRY_RUN_FAILED (task 4.10)
- Pipeline context artifacts written correctly (task 4.9)
"""

from __future__ import annotations

import os
import tempfile

import pytest

from quantlab.agents.deployment_agent import DeploymentAgent, DeploymentResult
from quantlab.pipeline.base import PipelineContext


# ── Helpers ────────────────────────────────────────────────────────────────────

# _validate_cfx accepts bytes >= 100, so make sure test CFX passes that bar.
_MINIMAL_CFX = b"PK\x05\x06" + b"\x00" * 120  # 124 bytes — passes len > 100


def _make_context(
    portfolio_cfx: bytes | str,
    campaign_id: str = "campaign_pr4",
) -> PipelineContext:
    return PipelineContext(
        config={"campaign_id": campaign_id},
        artifacts={"portfolio_cfx": portfolio_cfx},
    )


# ── Task 4.10: dry-run validation ────────────────────────────────────────────


class TestDeploymentAgentValidation:
    @pytest.mark.asyncio
    async def test_valid_cfx_artifacts_packaged_on_dry_run(self) -> None:
        """GIVEN valid CFX bytes and dry_run=True
        WHEN run() is called
        THEN jforex_package, jcloud_config, deployment_result are written
             to context artifacts and status=DRY_RUN_SUCCESS.
        """
        agent = DeploymentAgent(dry_run=True)
        ctx = _make_context(_MINIMAL_CFX)

        output = await agent.run(ctx)

        assert output["status"] == "DRY_RUN_SUCCESS"
        assert "jforex_package" in output
        assert "jcloud_config" in output
        assert not output.get("errors")
        assert "jforex_package" in ctx.artifacts
        assert "jcloud_config" in ctx.artifacts
        assert "deployment_result" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_invalid_cfx_returns_dry_run_failed(self) -> None:
        """GIVEN invalid CFX (too short) and dry_run=True
        WHEN run() is called
        THEN status=DRY_RUN_FAILED and errors mention validation.
        """
        agent = DeploymentAgent(dry_run=True)
        ctx = _make_context(b"short")

        output = await agent.run(ctx)

        assert output["status"] == "DRY_RUN_FAILED"
        assert output["errors"], "Expected validation errors"

    @pytest.mark.asyncio
    async def test_missing_portfolio_cfx_raises(self) -> None:
        """GIVEN no portfolio_cfx in context
        WHEN run() is called
        THEN ValueError is raised.
        """
        agent = DeploymentAgent(dry_run=True)
        ctx = PipelineContext(config={"campaign_id": "test"}, artifacts={})

        with pytest.raises(ValueError, match="portfolio_cfx"):
            await agent.run(ctx)


# ── Task 4.9: packaging + JCloud config ──────────────────────────────────────


class TestDeploymentAgentPackaging:
    @pytest.mark.asyncio
    async def test_dry_run_creates_package_and_config(self) -> None:
        """GIVEN DeploymentAgent(dry_run=True)
        WHEN run() is called with valid CFX
        THEN a package path and jcloud config dict are returned.
        """
        agent = DeploymentAgent(dry_run=True)
        ctx = _make_context(_MINIMAL_CFX)

        output = await agent.run(ctx)

        assert output["status"] == "DRY_RUN_SUCCESS"
        assert output["jforex_package"], "Expected a JAR path"
        assert isinstance(output["jcloud_config"], dict)

    @pytest.mark.asyncio
    async def test_jcloud_config_contains_required_fields(self) -> None:
        """GIVEN DeploymentAgent
        WHEN run() generates JCloud config
        THEN monitoring, instance_type, auto_restart are present.
        """
        agent = DeploymentAgent(dry_run=True)
        ctx = _make_context(_MINIMAL_CFX)

        output = await agent.run(ctx)
        jcloud = output["jcloud_config"]

        assert jcloud.get("auto_restart") is True
        assert jcloud.get("max_restarts", 0) > 0
        assert "monitoring" in jcloud

    @pytest.mark.asyncio
    async def test_file_path_cfx_validated(self) -> None:
        """GIVEN CFX as a file path string
        WHEN run() is called
        THEN packaging proceeds and returns a JAR path.
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".cfx", delete=False)
        tmp.write(_MINIMAL_CFX)
        tmp.close()
        try:
            agent = DeploymentAgent(dry_run=True)
            ctx = _make_context(str(tmp.name))

            output = await agent.run(ctx)

            assert output["status"] == "DRY_RUN_SUCCESS"
            assert output["jforex_package"]
        finally:
            os.unlink(tmp.name)


# ── Task 4.10: live deploy path ──────────────────────────────────────────────


class TestDeploymentAgentLive:
    @pytest.mark.asyncio
    async def test_live_deploy_returns_instance_ids(self) -> None:
        """WHEN dry_run=False and jforex_deploy is unavailable
        THEN simulated deploy returns instance_ids and endpoint_url.
        """
        agent = DeploymentAgent(dry_run=False)
        ctx = _make_context(_MINIMAL_CFX, campaign_id="live_test")

        output = await agent.run(ctx)

        assert output["status"] == "DEPLOYED"
        assert output["instance_ids"]
        assert output["endpoint_url"]
