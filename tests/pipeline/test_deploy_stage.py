"""T-4.11 RED: DeployStage strategy_id routing, multi-strategy isolation, missing strategy handling.

Tests for WU6: DeployStage should accept strategy_ids, call JCloudDeployClient.deploy()
per strategy_id, and connect to CompileStage via .jfx artifact paths.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.deploy_stage import DeployStage


def _make_jfx(tmp_path: Path, name: str = "DemoStrategy") -> Path:
    """Write a fake compiled .jfx archive and return its path."""
    jfx = tmp_path / f"{name}.jfx"
    jfx.write_text("fake jfx bytes")
    return jfx


def _mock_deploy_result(strategy_id: str, count: int = 1) -> MagicMock:
    """Build a mock DeploymentResult for a simulated deploy."""
    return MagicMock(
        status="DEPLOYED",
        instance_ids=[f"sim-{strategy_id}-{count}"],
        endpoint_url=f"https://jcloud.quantlab.ai/{strategy_id}",
        artifact_paths=[f"/out/{strategy_id}.jfx"],
    )


def _mock_client() -> MagicMock:
    """Create a mock JCloudDeployClient with an AsyncMock deploy method."""
    client = MagicMock()
    client.deploy = AsyncMock()
    return client


class TestDeployStageStrategyIdRouting:
    """T-4.11: DeployStage routes deploy calls by strategy_id."""

    @pytest.mark.asyncio
    async def test_deploy_called_once_per_strategy_id(self, tmp_path: Path):
        """GIVEN DeployStage with strategy_ids=["s1", "s2"]
        AND compiled_strategies contains .jfx paths for both strategies
        WHEN execute runs
        THEN JCloudDeployClient.deploy() is called exactly twice,
        once for each strategy_id with the correct (jfx_path, strategy_id, config) tuple.
        """
        jfx_s1 = _make_jfx(tmp_path, "s1")
        jfx_s2 = _make_jfx(tmp_path, "s2")

        client = _mock_client()
        client.deploy.side_effect = [
            _mock_deploy_result("s1", 1),
            _mock_deploy_result("s2", 1),
        ]

        stage = DeployStage(
            strategy_ids=["s1", "s2"],
            jcloud_client=client,
        )

        ctx = PipelineContext(
            config={"jcloud_account": {"account": "test", "server": "test"}},
            artifacts={"compiled_strategies": [jfx_s1, jfx_s2]},
        )

        result = await stage.execute(ctx)

        assert client.deploy.call_count == 2
        client.deploy.assert_any_call(jfx_s1, "s1", {"account": "test", "server": "test"})
        client.deploy.assert_any_call(jfx_s2, "s2", {"account": "test", "server": "test"})

    @pytest.mark.asyncio
    async def test_deploy_result_keyed_by_strategy_id(self, tmp_path: Path):
        """GIVEN multiple strategies
        WHEN execute runs
        THEN deployment_result is a dict keyed by strategy_id.
        """
        jfx_s1 = _make_jfx(tmp_path, "s1")
        jfx_s2 = _make_jfx(tmp_path, "s2")

        client = _mock_client()
        client.deploy.side_effect = [
            _mock_deploy_result("s1", 1),
            _mock_deploy_result("s2", 1),
        ]

        stage = DeployStage(
            strategy_ids=["s1", "s2"],
            jcloud_client=client,
        )

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": [jfx_s1, jfx_s2]},
        )

        result = await stage.execute(ctx)

        assert "s1" in result["deployment_result"]
        assert "s2" in result["deployment_result"]
        assert result["deployment_result"]["s1"]["status"] == "DEPLOYED"
        assert result["deployment_result"]["s2"]["status"] == "DEPLOYED"


class TestDeployStageMultiStrategyIsolation:
    """T-4.11: Multi-strategy isolation — failures in one strategy don't block others."""

    @pytest.mark.asyncio
    async def test_one_strategy_failure_does_not_block_others(self, tmp_path: Path):
        """GIVEN strategy_ids=["s1", "s2", "s3"]
        AND deploy for s2 raises an exception
        WHEN execute runs
        THEN s1 and s3 still deploy successfully
        AND s2 has a failed entry in deployment_result.
        """
        jfx_s1 = _make_jfx(tmp_path, "s1")
        jfx_s2 = _make_jfx(tmp_path, "s2")
        jfx_s3 = _make_jfx(tmp_path, "s3")

        client = _mock_client()

        async def deploy_side_effect(jfx_path, strategy_id, config):
            if strategy_id == "s2":
                raise RuntimeError("simulated deploy failure")
            return _mock_deploy_result(strategy_id, 1)

        client.deploy.side_effect = deploy_side_effect

        stage = DeployStage(
            strategy_ids=["s1", "s2", "s3"],
            jcloud_client=client,
        )

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": [jfx_s1, jfx_s2, jfx_s3]},
        )

        result = await stage.execute(ctx)

        assert result["deployment_result"]["s1"]["status"] == "DEPLOYED"
        assert result["deployment_result"]["s2"]["status"] == "FAILED"
        assert result["deployment_result"]["s3"]["status"] == "DEPLOYED"
        assert "simulated deploy failure" in result["deployment_result"]["s2"]["errors"][0]


class TestDeployStageMissingStrategy:
    """T-4.11: Missing strategy handling."""

    @pytest.mark.asyncio
    async def test_missing_strategy_id_produces_failed_result(self, tmp_path: Path):
        """GIVEN strategy_ids=["s1", "missing"]
        AND compiled_strategies only has a path for s1
        WHEN execute runs
        THEN s1 deploys successfully
        AND missing produces a FAILED result with an error message
        without blocking s1.
        """
        jfx_s1 = _make_jfx(tmp_path, "s1")

        client = _mock_client()
        client.deploy.return_value = _mock_deploy_result("s1", 1)

        stage = DeployStage(
            strategy_ids=["s1", "missing"],
            jcloud_client=client,
        )

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": [jfx_s1]},
        )

        result = await stage.execute(ctx)

        assert result["deployment_result"]["s1"]["status"] == "DEPLOYED"
        assert result["deployment_result"]["missing"]["status"] == "FAILED"
        assert "not found" in result["deployment_result"]["missing"]["errors"][0].lower()
        assert client.deploy.call_count == 1


class TestDeployStageEdgeCases:
    """T-4.11 triangulation: empty strategy_ids, single strategy."""

    @pytest.mark.asyncio
    async def test_empty_strategy_ids_returns_empty_result(self, tmp_path: Path):
        """GIVEN strategy_ids=[]
        WHEN execute runs with compiled_strategies present
        THEN deployment_result is an empty dict and deploy is never called.
        """
        jfx_s1 = _make_jfx(tmp_path, "s1")

        client = _mock_client()

        stage = DeployStage(
            strategy_ids=[],
            jcloud_client=client,
        )

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": [jfx_s1]},
        )

        result = await stage.execute(ctx)

        assert result["deployment_result"] == {}
        assert client.deploy.call_count == 0

    @pytest.mark.asyncio
    async def test_single_strategy_deploys_once(self, tmp_path: Path):
        """GIVEN strategy_ids=["solo"]
        AND compiled_strategies has one .jfx path
        WHEN execute runs
        THEN deploy is called exactly once with the correct arguments.
        """
        jfx_solo = _make_jfx(tmp_path, "solo")

        client = _mock_client()
        client.deploy.return_value = _mock_deploy_result("solo", 1)

        stage = DeployStage(
            strategy_ids=["solo"],
            jcloud_client=client,
        )

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": [jfx_solo]},
        )

        result = await stage.execute(ctx)

        assert client.deploy.call_count == 1
        client.deploy.assert_called_once_with(jfx_solo, "solo", None)
        assert result["deployment_result"]["solo"]["status"] == "DEPLOYED"
