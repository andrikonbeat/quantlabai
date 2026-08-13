"""WU7b RED: DemoWindowStore persistence wiring into DemoStage.

Tests for WU7b: DemoStage should wire DemoWindowStore persistence into its
lifecycle — load state on init, save state after demo run, handle missing/corrupt state.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.data.demo.store import DemoWindowStore, StateCorruptionError
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.demo_stage import DemoStage


def _make_window(campaign_id: str = "camp-001", started_at: str = "2026-01-01", expires_at: str = "2026-01-15", renewal_count: int = 0) -> dict:
    """Build a valid demo window state dict."""
    return {
        "campaign_id": campaign_id,
        "started_at": started_at,
        "expires_at": expires_at,
        "renewal_count": renewal_count,
    }


def _make_ctx(tmp_path: Path, campaign_id: str = "camp-001", deployment: dict | None = None) -> PipelineContext:
    """Build a minimal PipelineContext for DemoStage tests."""
    if deployment is None:
        deployment = {"status": "DEPLOYED"}
    return PipelineContext(
        artifacts={"deployment_result": deployment},
        config={"campaign_id": campaign_id, "knowledge_lake_root": str(tmp_path)},
    )


def test_demo_stage_loads_window_state_on_init(tmp_path: Path):
    """DemoStage should load persisted window state via DemoWindowStore on execute."""
    import asyncio

    store = DemoWindowStore(tmp_path, "camp-001")
    store.persist(_make_window())
    stage = DemoStage(store=store)
    ctx = _make_ctx(tmp_path)
    deployer = MagicMock()
    deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED"})
    stage._deployer = deployer

    result = asyncio.run(stage.execute(ctx))

    assert result is not None


def test_demo_stage_saves_window_state_after_deploy(tmp_path: Path):
    """DemoStage should persist window state after a successful deploy."""
    import asyncio

    store = DemoWindowStore(tmp_path, "camp-001")
    stage = DemoStage(store=store)
    ctx = _make_ctx(tmp_path)
    deployer = MagicMock()
    deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED"})
    stage._deployer = deployer

    asyncio.run(stage.execute(ctx))

    loaded = store.load("camp-001")
    assert "started_at" in loaded


def test_demo_stage_handles_missing_state_file(tmp_path: Path):
    """DemoStage should handle missing window state (no file yet) without crashing."""
    import asyncio

    store = DemoWindowStore(tmp_path, "camp-new")
    stage = DemoStage(store=store)
    ctx = _make_ctx(tmp_path, campaign_id="camp-new")
    deployer = MagicMock()
    deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED"})
    stage._deployer = deployer

    result = asyncio.run(stage.execute(ctx))
    assert result is not None


def test_demo_stage_handles_corrupt_state_file(tmp_path: Path):
    """DemoStage should handle corrupt window state (StateCorruptionError) gracefully."""
    import asyncio

    bad_file = tmp_path / "structured" / "demo" / "camp-bad" / "window.yaml"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text("not: [valid: yaml", encoding="utf-8")

    store = DemoWindowStore(tmp_path, "camp-bad")
    stage = DemoStage(store=store)
    ctx = _make_ctx(tmp_path, campaign_id="camp-bad")
    deployer = MagicMock()
    deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED"})
    stage._deployer = deployer

    result = asyncio.run(stage.execute(ctx))
    assert result is not None


class TestDemoStagePersistenceWiring:
    """WU7b: DemoWindowStore persistence wiring into DemoStage."""

    async def test_persists_after_successful_deploy(self, tmp_path: Path):
        store = DemoWindowStore(tmp_path, "camp-001")
        stage = DemoStage(store=store)
        ctx = _make_ctx(tmp_path)
        deployer = MagicMock()
        deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED", "demo_id": "demo-123"})
        stage._deployer = deployer

        await stage.execute(ctx)

        assert (tmp_path / "structured" / "demo" / "camp-001" / "window.yaml").exists()

    async def test_loads_existing_state_on_init(self, tmp_path: Path):
        store = DemoWindowStore(tmp_path, "camp-001")
        store.persist(_make_window())
        stage = DemoStage(store=store)
        ctx = _make_ctx(tmp_path)
        deployer = MagicMock()
        deployer.deploy = AsyncMock(return_value={"status": "DEPLOYED"})
        stage._deployer = deployer

        await stage.execute(ctx)

        loaded = store.load("camp-001")
        assert loaded["started_at"] == "2026-01-01"
