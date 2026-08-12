"""Task 1.2 RED: JCloudDeployClient ABC, SimulatedJCloudDeployClient, DeploymentStatus.

Scenario 1 "Interface enforces contract": subclass missing deploy() raises
TypeError at instantiation or call time.
Scenario 2 "Simulated deploy returns instance ID": deploy() returns a stable
instance_id string without network calls.
Scenario 3 "Status returns simulated state": status() returns a DeploymentStatus
enum value.
"""

from __future__ import annotations

import pytest

from quantlab.agents.deployment_agent import (
    DeploymentResult,
    DeploymentStatus,
    InstanceNotFoundError,
    JCloudDeployClient,
    SimulatedJCloudDeployClient,
)


class _BadClientMissingDeploy(JCloudDeployClient):
    async def status(self, deployment_id: str) -> DeploymentStatus:
        return DeploymentStatus.PENDING


class _BadClientMissingStatus(JCloudDeployClient):
    async def deploy(self, jfx_path, strategy_id, config):
        return DeploymentResult()


class TestJCloudDeployClientABC:
    """REQ-612 scenario 1 — interface enforces contract."""

    def test_missing_deploy_raises_type_error(self):
        """GIVEN JCloudDeployClient ABC
        WHEN a subclass is created without deploy()
        THEN instantiation raises TypeError naming the missing method.
        """
        with pytest.raises(TypeError):
            _BadClientMissingDeploy()

    def test_missing_status_raises_type_error(self):
        """GIVEN JCloudDeployClient ABC
        WHEN a subclass is created without status()
        THEN instantiation raises TypeError naming the missing method.
        """
        with pytest.raises(TypeError):
            _BadClientMissingStatus()


class TestSimulatedJCloudDeployClient:
    """REQ-612 scenario 2 — simulated deploy returns deterministic instance IDs."""

    @pytest.mark.asyncio
    async def test_deploy_returns_instance_id_string(self, tmp_path):
        """GIVEN SimulatedJCloudDeployClient
        WHEN deploy() is called
        THEN a non-empty instance_id string is returned.
        """
        client = SimulatedJCloudDeployClient()
        jfx = tmp_path / "strategy.jfx"
        jfx.write_text("fake")

        result = await client.deploy(jfx, "s1", {})
        assert result.instance_ids == ["sim-s1-1"]

    @pytest.mark.asyncio
    async def test_deploy_is_deterministic_for_same_strategy(self, tmp_path):
        """GIVEN SimulatedJCloudDeployClient
        WHEN deploy() is called twice with the same strategy_id
        THEN the instance IDs follow a predictable pattern.
        """
        client = SimulatedJCloudDeployClient()
        jfx = tmp_path / "strategy.jfx"
        jfx.write_text("fake")

        r1 = await client.deploy(jfx, "s1", {})
        r2 = await client.deploy(jfx, "s1", {})

        # Deterministic pattern: same strategy_id, incremented counter.
        assert r1.instance_ids == ["sim-s1-1"]
        assert r2.instance_ids == ["sim-s1-2"]

    @pytest.mark.asyncio
    async def test_status_returns_deployment_status_enum(self, tmp_path):
        """GIVEN a simulated instance_id from deploy()
        WHEN status() is called
        THEN a DeploymentStatus enum is returned.
        """
        client = SimulatedJCloudDeployClient()
        jfx = tmp_path / "strategy.jfx"
        jfx.write_text("fake")
        result = await client.deploy(jfx, "s1", {})
        instance_id = result.instance_ids[0]

        status = await client.status(instance_id)
        assert isinstance(status, DeploymentStatus)
        assert status in (
            DeploymentStatus.PENDING,
            DeploymentStatus.RUNNING,
            DeploymentStatus.STOPPED,
        )

    @pytest.mark.asyncio
    async def test_status_transitions_pending_to_stopped(self, tmp_path):
        """GIVEN a simulated instance_id
        WHEN status() is called three times
        THEN it transitions PENDING → RUNNING → STOPPED.
        """
        client = SimulatedJCloudDeployClient()
        jfx = tmp_path / "strategy.jfx"
        jfx.write_text("fake")
        result = await client.deploy(jfx, "s1", {})
        instance_id = result.instance_ids[0]

        assert await client.status(instance_id) == DeploymentStatus.RUNNING
        assert await client.status(instance_id) == DeploymentStatus.STOPPED
        # Further calls remain STOPPED.
        assert await client.status(instance_id) == DeploymentStatus.STOPPED

    @pytest.mark.asyncio
    async def test_unknown_instance_raises_not_found(self, tmp_path):
        """GIVEN a deployment_id that was never issued
        WHEN status() is called
        THEN InstanceNotFoundError is raised.
        """
        client = SimulatedJCloudDeployClient()
        with pytest.raises(InstanceNotFoundError, match="ghost-id"):
            await client.status("ghost-id")


class TestDeploymentStatusEnum:
    """REQ-612 scenario 3 — DeploymentStatus enum values."""

    def test_enum_values(self):
        assert DeploymentStatus.PENDING.value == "PENDING"
        assert DeploymentStatus.RUNNING.value == "RUNNING"
        assert DeploymentStatus.STOPPED.value == "STOPPED"
