"""Tests for DeploymentAgent real packaging — REQ-32.

Verifies the placeholder JAR stub (``PK\\x05\\x06``) is replaced by a real
deployable JAR with the compiled ``.jfx`` embedded and JCloud configuration
(account, server, symbols) applied; dry-run produces a mock package with
ZERO network calls.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from quantlab.agents.deployment_agent import (
    DeploymentAgent,
    JCloudConfig,
    build_cfx_jar,
    build_deployable_jar,
)


def _make_jfx(tmp_path: Path, name: str = "DemoStrategy") -> Path:
    """Write a fake compiled .jfx archive and return its path."""
    jfx = tmp_path / f"{name}.jfx"
    with zipfile.ZipFile(jfx, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{name}.class", b"fake class bytes")
    return jfx


def _account() -> JCloudConfig:
    return JCloudConfig(
        account="DUK-100USD-DEMO",
        server="jcloud.dukascopy.com",
        symbols=("EURUSD", "GBPUSD"),
    )


class TestJCloudConfig:
    """REQ-32: JCloud configuration (account, server, symbols)."""

    def test_manifest_round_trip(self) -> None:
        """GIVEN a JCloudConfig with account/server/symbols
        WHEN it is serialised to a manifest and back
        THEN account, server, and every symbol survive unchanged.
        """
        account = _account()
        manifest = account.to_manifest()

        assert manifest["account"] == "DUK-100USD-DEMO"
        assert manifest["server"] == "jcloud.dukascopy.com"
        assert manifest["symbols"] == ["EURUSD", "GBPUSD"]

        restored = JCloudConfig.from_manifest(manifest)
        assert restored == account


class TestDeployableJar:
    """REQ-32 scenario 1: real packaging with .jfx embedded."""

    def test_jar_embeds_jfx_bytes(self, tmp_path) -> None:
        """GIVEN a compiled .jfx and JCloud config
        WHEN build_deployable_jar packages it
        THEN a deployable JAR is produced with the exact .jfx payload embedded.
        """
        jfx = _make_jfx(tmp_path)
        jar = build_deployable_jar(jfx, tmp_path / "out" / "demo.jar", _account())

        with zipfile.ZipFile(jar) as zf:
            embedded = zf.read("strategies/DemoStrategy.jfx")

        assert embedded == jfx.read_bytes(), "the .jfx file must be embedded whole"

    def test_jar_contains_manifest(self, tmp_path) -> None:
        """GIVEN packaging
        WHEN inspecting the JAR
        THEN a valid META-INF/MANIFEST.MF entry is present.
        """
        jar = build_deployable_jar(_make_jfx(tmp_path), tmp_path / "out" / "demo.jar", _account())

        with zipfile.ZipFile(jar) as zf:
            names = zf.namelist()
            manifest = zf.read("META-INF/MANIFEST.MF").decode("utf-8")

        assert "META-INF/MANIFEST.MF" in names
        assert "Manifest-Version: 1.0" in manifest

    def test_jcloud_config_applied_in_jar(self, tmp_path) -> None:
        """GIVEN a JCloudConfig
        WHEN packaging
        THEN the JAR carries the applied config (account, server, symbols).
        """
        jar = build_deployable_jar(_make_jfx(tmp_path), tmp_path / "out" / "demo.jar", _account())

        with zipfile.ZipFile(jar) as zf:
            applied = json.loads(zf.read("jcloud.json").decode("utf-8"))

        assert applied["account"] == "DUK-100USD-DEMO"
        assert applied["server"] == "jcloud.dukascopy.com"
        assert applied["symbols"] == ["EURUSD", "GBPUSD"]


class TestDeploymentAgentJfx:
    """REQ-32: DeploymentAgent.package_jfx dry-run vs live."""

    @pytest.mark.asyncio
    async def test_dry_run_packages_mock_jar_no_network(self, tmp_path) -> None:
        """GIVEN DeploymentAgent with dry_run=True
        WHEN packaging a .jfx
        THEN a mock JAR is produced, no network/live deploy occurs
             (no instance ids, no endpoint), status DRY_RUN_SUCCESS.
        """
        jfx = _make_jfx(tmp_path)
        agent = DeploymentAgent(dry_run=True)

        result = await agent.package_jfx(
            jfx, _account(), campaign_id="camp-demo-1", output_dir=str(tmp_path / "deploy")
        )

        assert result.status == "DRY_RUN_SUCCESS"
        assert result.artifact_paths, "a mock JAR must be produced for inspection"
        jar = Path(result.artifact_paths[0])
        assert jar.exists()
        assert zipfile.is_zipfile(jar)
        assert not result.instance_ids, "dry-run must never simulate live instances"
        assert not result.endpoint_url, "dry-run must never touch the network path"

    @pytest.mark.asyncio
    async def test_live_path_simulates_deploy_without_http(self, tmp_path) -> None:
        """GIVEN DeploymentAgent with dry_run=False
        WHEN packaging a .jfx
        THEN the live stand-in returns DEPLOYED with instance ids — simulated
             locally, no real JCloud HTTP call is made by the SDK.
        """
        jfx = _make_jfx(tmp_path)
        agent = DeploymentAgent(dry_run=False)

        result = await agent.package_jfx(
            jfx, _account(), campaign_id="camp-demo-1", output_dir=str(tmp_path / "deploy")
        )

        assert result.status == "DEPLOYED"
        assert result.instance_ids
        assert result.endpoint_url
        assert result.jforex_package, "the real JAR is still produced locally"


class TestPlaceholderReplaced:
    """REQ-32: the PK\\x05\\x06 placeholder stub is gone."""

    @pytest.mark.asyncio
    async def test_cfx_packaging_produces_real_zip(self, tmp_path) -> None:
        """GIVEN the pipeline CFX packaging path
        WHEN it packages valid CFX bytes
        THEN the output JAR is a real ZIP with the CFX embedded — not the
             20-byte placeholder stub.
        """
        from quantlab.pipeline.base import PipelineContext

        cfx = b"PK\x05\x06" + b"\x00" * 120  # 124 bytes — passes len > 100
        agent = DeploymentAgent(dry_run=True)
        ctx = PipelineContext(
            config={"campaign_id": "camp-demo-1"},
            artifacts={"portfolio_cfx": cfx},
        )

        output = await agent.run(ctx)

        assert output["status"] == "DRY_RUN_SUCCESS"
        jar = Path(output["jforex_package"])
        assert jar.stat().st_size > 20, "placeholder stub must be replaced"
        with zipfile.ZipFile(jar) as zf:
            names = zf.namelist()
        assert "portfolio.cfx" in names
        assert "META-INF/MANIFEST.MF" in names

    def test_build_cfx_jar_embeds_bytes_and_manifest(self, tmp_path) -> None:
        """GIVEN CFX bytes and an output path
        WHEN build_cfx_jar runs
        THEN a real JAR carries the CFX bytes and a manifest.
        """
        payload = b"<project/>"
        jar = build_cfx_jar(payload, tmp_path / "out" / "portfolio.jar", "camp-demo-1")

        with zipfile.ZipFile(jar) as zf:
            assert zf.read("portfolio.cfx") == payload
            assert "META-INF/MANIFEST.MF" in zf.namelist()
