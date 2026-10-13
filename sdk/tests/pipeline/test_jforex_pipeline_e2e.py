"""Ciclo 5 tests — JForex pipeline integration (REQ-06).

Covers T5.1 (JForexDeployStage) including its Knowledge Lake failure path,
T5.2 (jforex_progress_fn used by ExecutionMonitor), and T5.3 (end-to-end
compile → deploy → monitor flow).

Strict TDD: written first — FAIL (RED) until the Ciclo 5 code exists.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from quantlab.pipeline.base import PipelineContext

# ---------------------------------------------------------------------------
# T5.1 — JForexDeployStage
# ---------------------------------------------------------------------------


class TestJForexDeployStage:
    """REQ-06 Scenario 1: deploy .jfx via JForexStrategyBridge."""

    def test_deploys_each_compiled_strategy(self, tmp_path: Path) -> None:
        """GIVEN compiled_strategies dict WHEN stage runs THEN bridge deploys each."""
        from quantlab.pipeline.stages.jforex_deploy_stage import JForexDeployStage

        jfx_a = tmp_path / "AlphaM15.jfx"
        jfx_b = tmp_path / "BetaH1.jfx"
        jfx_a.write_bytes(b"pk")
        jfx_b.write_bytes(b"pk")

        deployed: list[str] = []

        class FakeBridge:
            def deploy(self, jfx_path: Path) -> None:
                deployed.append(str(jfx_path))

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": {"AlphaM15": jfx_a, "BetaH1": jfx_b}},
        )
        stage = JForexDeployStage(bridge=FakeBridge())

        result = asyncio.run(stage.execute(ctx))

        assert set(deployed) == {str(jfx_a), str(jfx_b)}
        assert result["deployment_result"] == {
            "AlphaM15": {"status": "OK"},
            "BetaH1": {"status": "OK"},
        }

    def test_fail_closed_on_bridge_error(self, tmp_path: Path) -> None:
        """GIVEN bridge raises WHEN deploy THEN result FAILED, pipeline continues."""
        from quantlab.pipeline.stages.jforex_deploy_stage import JForexDeployStage

        jfx = tmp_path / "GammaM30.jfx"
        jfx.write_bytes(b"pk")

        class BrokenBridge:
            def deploy(self, jfx_path: Path) -> None:
                raise RuntimeError("jforex unavailable")

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": {"GammaM30": jfx}},
        )
        stage = JForexDeployStage(bridge=BrokenBridge())

        result = asyncio.run(stage.execute(ctx))

        assert result["deployment_result"]["GammaM30"]["status"] == "FAILED"
        assert "jforex unavailable" in result["deployment_result"]["GammaM30"]["errors"]

    def test_knowledge_lake_write_failure_is_logged_not_raised(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """GIVEN Knowledge Lake is unreachable WHEN a deploy fails THEN the
        FAILED result is still returned and the KB error is logged, not raised."""
        from quantlab.pipeline.stages.jforex_deploy_stage import JForexDeployStage

        jfx = tmp_path / "KbDown_M15.jfx"
        jfx.write_bytes(b"pk")

        class BrokenBridge:
            def deploy(self, jfx_path: Path) -> None:
                raise RuntimeError("jforex unavailable")

        class UnreachableStore:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            async def write(self, path: str, content: str) -> None:
                raise OSError("knowledge lake unreachable")

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": {"KbDown_M15": jfx}},
        )
        stage = JForexDeployStage(bridge=BrokenBridge())

        with (
            caplog.at_level(logging.WARNING),
            patch("quantlab.knowledge.store.KnowledgeStore", UnreachableStore),
        ):
            result = asyncio.run(stage.execute(ctx))

        # The deploy failure is reported, not masked by the KB failure.
        assert result["deployment_result"]["KbDown_M15"]["status"] == "FAILED"
        assert "jforex unavailable" in result["deployment_result"]["KbDown_M15"]["errors"]
        assert ctx.artifacts["deployment_result"] == result["deployment_result"]
        # The KB failure is observable to the operator, never silent.
        warnings = [
            record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.WARNING
        ]
        assert any("knowledge lake unreachable" in message for message in warnings), (
            f"expected a logged warning naming the KB error, got {warnings}"
        )

    def test_deploy_failure_is_written_to_knowledge_lake(self, tmp_path: Path) -> None:
        """GIVEN Knowledge Lake is reachable WHEN a deploy fails THEN the
        failure is recorded under ``deployment_failures``."""
        from quantlab.pipeline.stages.jforex_deploy_stage import JForexDeployStage

        jfx = tmp_path / "KbOk_M15.jfx"
        jfx.write_bytes(b"pk")
        written: list[tuple[str, str]] = []

        class BrokenBridge:
            def deploy(self, jfx_path: Path) -> None:
                raise RuntimeError("jforex unavailable")

        class RecordingStore:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            async def write(self, path: str, content: str) -> None:
                written.append((path, content))

        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": {"KbOk_M15": jfx}},
        )
        stage = JForexDeployStage(bridge=BrokenBridge())

        with patch("quantlab.knowledge.store.KnowledgeStore", RecordingStore):
            asyncio.run(stage.execute(ctx))

        assert len(written) == 1
        path, content = written[0]
        assert path.startswith("deployment_failures/")
        entry = json.loads(content)
        assert entry["strategy_id"] == "KbOk_M15"
        assert entry["type"] == "deployment_failure"
        assert entry["error"] == "jforex unavailable"

    def test_empty_compiled_yields_empty_result(self) -> None:
        """GIVEN no compiled_strategies WHEN stage runs THEN empty result."""
        from quantlab.pipeline.stages.jforex_deploy_stage import JForexDeployStage

        ctx = PipelineContext(config={}, artifacts={})
        stage = JForexDeployStage()

        result = asyncio.run(stage.execute(ctx))

        assert result["deployment_result"] == {}

    def test_list_input_unwraps_artifact_objects(self, tmp_path: Path) -> None:
        """GIVEN list of artifact objects WHEN stage runs THEN .path is used."""
        from quantlab.compiler.jfx import JfxArtifact
        from quantlab.pipeline.stages.jforex_deploy_stage import JForexDeployStage

        jfx = tmp_path / "DeltaH4.jfx"
        jfx.write_bytes(b"pk")
        deployed: list[Path] = []

        class FakeBridge:
            def deploy(self, jfx_path: Path) -> None:
                deployed.append(Path(jfx_path))

        ctx = PipelineContext(
            config={},
            artifacts={
                "compiled_strategies": [
                    JfxArtifact(path=jfx, source=jfx, class_name="DeltaH4")
                ]
            },
        )
        stage = JForexDeployStage(bridge=FakeBridge())

        result = asyncio.run(stage.execute(ctx))

        assert deployed == [jfx]
        assert result["deployment_result"]["0"]["status"] == "OK"


# ---------------------------------------------------------------------------
# T5.2 — JForex progress source for ExecutionMonitor
# ---------------------------------------------------------------------------


class TestJForexProgressFn:
    """REQ-06 Scenario 2: ExecutionMonitor polls JForexLiveFeed instead of SQX."""

    def test_feed_with_equity_yields_alive_progress(self, tmp_path: Path) -> None:
        """GIVEN feed with one equity point WHEN polled THEN (True, 0.5)."""
        from quantlab.jforex.live_feed import jforex_progress_fn

        feed = object()
        progress = jforex_progress_fn(feed, poll_equity_count=lambda: 3)

        alive, value = asyncio.run(progress())
        assert alive is True
        assert value == 0.5

    def test_feed_without_equity_yields_alive_no_progress(self, tmp_path: Path) -> None:
        """GIVEN feed with no equity points WHEN polled THEN (True, None)."""
        from quantlab.jforex.live_feed import jforex_progress_fn

        progress = jforex_progress_fn(object(), poll_equity_count=lambda: 0)

        alive, value = asyncio.run(progress())
        assert alive is True
        assert value is None

    def test_missing_feed_fails_closed(self) -> None:
        """GIVEN no feed WHEN polled THEN (False, None) — daemon lost."""
        from quantlab.jforex.live_feed import jforex_progress_fn

        progress = jforex_progress_fn(None)

        alive, value = asyncio.run(progress())
        assert alive is False
        assert value is None

    def test_feed_error_fails_closed(self) -> None:
        """GIVEN feed raises WHEN polled THEN (False, None)."""
        from quantlab.jforex.live_feed import jforex_progress_fn

        def boom() -> int:
            raise OSError("read failed")

        progress = jforex_progress_fn(object(), poll_equity_count=boom)

        alive, value = asyncio.run(progress())
        assert alive is False
        assert value is None

    def test_stage_routes_jforex_progress_into_monitor(self) -> None:
        """GIVEN ExecutionMonitorStage with progress_fn THEN monitor receives it."""
        from quantlab.pipeline.stages.execution_monitor_stage import (
            ExecutionMonitorStage,
        )

        captured: dict[str, object] = {}

        class FakeMonitor:
            async def monitor(
                self, campaign_id: str, phase: str, config: object
            ) -> object:
                captured["phase"] = phase
                return object()

        stage = ExecutionMonitorStage(monitor=FakeMonitor(), progress_fn=object())
        ctx = PipelineContext(config={"monitor_phase": "jforex_live"})

        result = asyncio.run(stage.execute(ctx))

        assert captured["phase"] == "jforex_live"
        assert "monitor_result" in result


# ---------------------------------------------------------------------------
# T5.3 — End-to-end pipeline flow
# ---------------------------------------------------------------------------


class TestJForexPipelineE2E:
    """Build → deploy → monitor chained through PipelineContext artifacts."""

    def test_compile_deploy_monitor_chain(self, tmp_path: Path) -> None:
        """GIVEN compile output WHEN deploy + monitor run THEN artifacts chain."""
        from quantlab.pipeline.base import Pipeline
        from quantlab.pipeline.stages.compile_stage import CompileStage
        from quantlab.pipeline.stages.execution_monitor_stage import (
            ExecutionMonitorStage,
        )
        from quantlab.pipeline.stages.jforex_deploy_stage import JForexDeployStage

        jfx = tmp_path / "E2E_M5.jfx"
        jfx.write_bytes(b"pk")
        monitor_calls: list[str] = []

        async def compile_fn(strategy_id: str) -> str:
            return str(jfx)

        class FakeDeployBridge:
            def deploy(self, jfx_path: Path) -> None:
                pass

        class FakeMonitor:
            async def monitor(
                self, campaign_id: str, phase: str, config: object
            ) -> object:
                monitor_calls.append(phase)
                return object()

        ctx = PipelineContext(
            config={"campaign_id": "camp", "monitor_phase": "live"},
            artifacts={"portfolio_result": {"E2E_M5": 1.0}},
        )

        pipeline = (
            Pipeline(name="jforex-e2e")
            .then(CompileStage(compile_fn=compile_fn))
            .then(JForexDeployStage(bridge=FakeDeployBridge()))
            .then(ExecutionMonitorStage(monitor=FakeMonitor()))
        )
        for stage in pipeline.stages:
            assert asyncio.run(stage.execute(ctx)) is not None

        assert list(ctx.artifacts["compiled_strategies"]) == [str(jfx)]
        assert ctx.artifacts["deployment_result"] == {"0": {"status": "OK"}}
        assert monitor_calls == ["live"]

    def test_deploy_failure_does_not_break_monitor_chain(self, tmp_path: Path) -> None:
        """GIVEN deploy fails WHEN chained THEN monitor still runs (fail-closed)."""
        from quantlab.pipeline.base import Pipeline
        from quantlab.pipeline.stages.compile_stage import CompileStage
        from quantlab.pipeline.stages.execution_monitor_stage import (
            ExecutionMonitorStage,
        )
        from quantlab.pipeline.stages.jforex_deploy_stage import JForexDeployStage

        jfx = tmp_path / "Fail_M15.jfx"
        jfx.write_bytes(b"pk")
        monitor_calls: list[str] = []

        async def compile_fn(strategy_id: str) -> str:
            return str(jfx)

        class BrokenBridge:
            def deploy(self, jfx_path: Path) -> None:
                raise RuntimeError("deploy down")

        class FakeMonitor:
            async def monitor(
                self, campaign_id: str, phase: str, config: object
            ) -> object:
                monitor_calls.append(phase)
                return object()

        ctx = PipelineContext(
            config={"monitor_phase": "live"},
            artifacts={"portfolio_result": {"Fail_M15": 1.0}},
        )

        pipeline = (
            Pipeline(name="jforex-e2e-fail")
            .then(CompileStage(compile_fn=compile_fn))
            .then(JForexDeployStage(bridge=BrokenBridge()))
            .then(ExecutionMonitorStage(monitor=FakeMonitor()))
        )
        for stage in pipeline.stages:
            assert asyncio.run(stage.execute(ctx)) is not None

        assert ctx.artifacts["deployment_result"]["0"]["status"] == "FAILED"
        assert monitor_calls == ["live"]
