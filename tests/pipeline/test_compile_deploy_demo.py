"""WU7c RED: compile→deploy→demo integration test.

Tests the full flow from compiled .jfx artifacts through deploy to demo,
using SimulatedJCloudDeployClient and DemoWindowStore.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.agents.deployment_agent import SimulatedJCloudDeployClient
from quantlab.data.demo.store import DemoWindowStore
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.deploy_stage import DeployStage
from quantlab.pipeline.stages.demo_stage import DemoStage


@pytest.fixture
def tmp_knowledge_lake(tmp_path: Path):
    """Create a temporary Knowledge Lake structure."""
    kl = tmp_path / "knowledge"
    for d in ["raw", "structured", "graph", "embeddings", "datasets",
              "pipeline-runs", "results", "stats", "campaigns", "agent-memory"]:
        (kl / d).mkdir(parents=True, exist_ok=True)
    return kl


def test_compile_deploy_demo_end_to_end(tmp_path: Path, tmp_knowledge_lake: Path):
    """Compile→Deploy→Demo pipeline produces demo_result with SimulatedJCloudDeployClient."""
    campaign_id = "camp-integration-001"
    strategy_ids = ["strat-a", "strat-b"]

    # Setup: simulate compiled .jfx artifacts
    jfx_dir = tmp_path / "compiled"
    jfx_dir.mkdir(parents=True, exist_ok=True)
    jfx_paths = {}
    for sid in strategy_ids:
        jfx = jfx_dir / f"{sid}.jfx"
        jfx.write_text(f"fake jfx for {sid}")
        jfx_paths[sid] = jfx

    # Setup deploy client
    client = SimulatedJCloudDeployClient()

    # Setup DemoWindowStore
    store = DemoWindowStore(tmp_knowledge_lake, campaign_id)

    # Setup stages — mock DemoDeployer to avoid jfx→jar packaging in integration test
    deploy_stage = DeployStage(jcloud_client=client)
    mock_deployer = MagicMock()
    mock_deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED", "demo_id": "demo-123"})
    demo_stage = DemoStage(deployer=mock_deployer, store=store)

    # Build context
    ctx = PipelineContext(
        artifacts={"compiled_strategies": jfx_paths},
        config={
            "campaign_id": campaign_id,
            "knowledge_lake_root": str(tmp_knowledge_lake),
        },
    )

    # Run deploy stage (returns dict)
    deploy_result = asyncio.run(deploy_stage.execute(ctx))
    assert "deployment_result" in deploy_result

    # Chain artifacts into demo stage
    ctx.artifacts.update(deploy_result)
    demo_result = asyncio.run(demo_stage.execute(ctx))
    assert "demo_result" in demo_result


def test_demo_stage_persists_window_after_deploy(tmp_path: Path, tmp_knowledge_lake: Path):
    """DemoStage persists window state after deploy via DemoWindowStore."""
    campaign_id = "camp-persist-001"
    store = DemoWindowStore(tmp_knowledge_lake, campaign_id)
    stage = DemoStage(store=store)
    deployer = MagicMock()
    deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED"})
    stage._deployer = deployer

    ctx = PipelineContext(
        artifacts={"deployment_result": {"status": "DEPLOYED"}},
        config={"campaign_id": campaign_id, "knowledge_lake_root": str(tmp_knowledge_lake)},
    )

    asyncio.run(stage.execute(ctx))

    window_path = tmp_knowledge_lake / "structured" / "demo" / campaign_id / "window.yaml"
    assert window_path.exists()


class TestCompileDeployDemoIntegration:
    """WU7c: compile→deploy→demo end-to-end integration."""

    async def test_full_flow_artifacts_chain(self, tmp_path: Path, tmp_knowledge_lake: Path):
        """Verify artifact chain: compiled_strategies → deployment_result → demo_result."""
        client = SimulatedJCloudDeployClient()
        deploy_stage = DeployStage(jcloud_client=client)
        mock_deployer = MagicMock()
        mock_deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED", "demo_id": "demo-123"})
        demo_stage = DemoStage(deployer=mock_deployer)

        ctx = PipelineContext(
            artifacts={"compiled_strategies": {"strat-1": Path("/fake/strat-1.jfx")}},
            config={"knowledge_lake_root": str(tmp_knowledge_lake)},
        )

        deploy_result = await deploy_stage.execute(ctx)
        assert "deployment_result" in deploy_result

        ctx.artifacts.update(deploy_result)
        demo_result = await demo_stage.execute(ctx)
        assert "demo_result" in demo_result
