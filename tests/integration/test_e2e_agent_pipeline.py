"""End-to-end integration test for the QuantLab multi-agent pipeline.

Covers the 9-stage agent flow:
  research → hypothesis_builder → statistics → review →
  [gate: HUMAN_APPROVE_ITERATION] → portfolio → compile →
  [gate: HUMAN_APPROVE_DEPLOY] → deploy → demo → archive

Stages that need external data (SQX exports, JForex compiler, live broker)
are exercised with the minimum mocking required: injectable constructor
arguments already present on the stage classes.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from quantlab.pipeline.base import Pipeline, PipelineContext
from quantlab.pipeline.config import MultiAgentPipelineConfig, StageConfig
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.runner import PipelineRunner
from quantlab.pipeline.stages.gate_interceptor import (
    FallbackPolicy,
    GateInterceptorStage,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_mock_compile_fn():
    async def compile_fn(strategy_id: str) -> str:
        return f"build/compiled/{strategy_id}.jfx"

    return compile_fn


def _make_mock_deploy_agent():
    agent = AsyncMock()
    agent.package_jfx = AsyncMock(
        return_value={
            "jforex_package": "build/packages/portfolio.jar",
            "jcloud_config": {"account": "test", "strategy": "PrimaryStrategy"},
            "status": "packaged",
        }
    )
    return agent


def _make_mock_demo_deployer():
    deployer = AsyncMock()
    deployer.deploy = AsyncMock(
        return_value={
            "demo_window_days": 14,
            "status": "deployed_demo",
            "account": "demo-account",
        }
    )
    return deployer


def _make_mock_archive_phase():
    phase = AsyncMock()
    phase.run = AsyncMock(
        return_value={
            "plan": {"action": "maintain", "replacement_candidates": []},
            "stats": {"demo_sharpe": 1.2, "demo_trades": 45},
            "artifacts": ["archive/bundle.zip"],
            "status": "archived",
        }
    )
    return phase


def _build_stages(mock_compile_fn, mock_deploy_agent, mock_demo_deployer, mock_archive_phase):
    return [
        StageConfig(name="research", type="agent"),
        StageConfig(name="hypothesis_builder", type="agent"),
        StageConfig(name="statistics", type="agent"),
        StageConfig(name="review", type="agent"),
        StageConfig(name="portfolio", type="agent"),
        StageConfig(name="compile", type="agent"),
        StageConfig(name="deploy", type="agent"),
        StageConfig(name="demo", type="agent"),
        StageConfig(name="archive", type="agent"),
    ]


# ── Test ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_agent_pipeline_runs_end_to_end():
    registry = StageRegistry()

    mock_compile_fn = _make_mock_compile_fn()
    mock_deploy_agent = _make_mock_deploy_agent()
    mock_demo_deployer = _make_mock_demo_deployer()
    mock_archive_phase = _make_mock_archive_phase()

    stages = [
        registry.get_stage_class("research")(),
        registry.get_stage_class("hypothesis_builder")(),
        registry.get_stage_class("statistics")(),
        registry.get_stage_class("review")(),
        registry.get_stage_class("portfolio")(),
        registry.get_stage_class("compile")(compile_fn=mock_compile_fn),
        registry.get_stage_class("deploy")(agent=mock_deploy_agent, dry_run=True),
        registry.get_stage_class("demo")(deployer=mock_demo_deployer),
        registry.get_stage_class("archive")(phase=mock_archive_phase),
    ]

    pipeline = Pipeline(name="test-e2e", stages=stages)

    runner = PipelineRunner()
    gate_iter = GateInterceptorStage()
    gate_iter.name = "gate_human_approve_iteration"
    gate_iter.gate_id = "HUMAN_APPROVE_ITERATION"
    gate_iter.timeout_hours = 1.0
    gate_iter.fallback = FallbackPolicy.CONTINUE
    runner.register_gate("review", gate_iter)

    gate_deploy = GateInterceptorStage()
    gate_deploy.name = "gate_human_approve_deploy"
    gate_deploy.gate_id = "HUMAN_APPROVE_DEPLOY"
    gate_deploy.timeout_hours = 1.0
    gate_deploy.fallback = FallbackPolicy.CONTINUE
    runner.register_gate("deploy", gate_deploy)

    ctx = PipelineContext(
        config={
            "objectives": ["Find mean-reversion on EURUSD H1"],
            "campaign_name": "test-e2e",
        },
        artifacts={},
    )

    external_provides = {
        "export_paths": [],
        "strategy_analysis": {},
        "aggregate_stats": {},
        "monte_carlo_bands": {},
        "selected_strategies": ["PrimaryStrategy"],
        "gate_decision_HUMAN_APPROVE_PORTFOLIO": {"action": "APPROVED"},
        "live_equity": [],
    }

    result = await runner.run_with_gates(
        pipeline, ctx, external_provides=external_provides
    )

    all_stage_names = [s.stage_name for s in result.stages]
    assert result.error is None, f"Pipeline error: {result.error}"
    for sr in result.stages:
        assert sr.status.value == "completed", (
            f"Stage '{sr.stage_name}' did not complete: {sr.error}"
        )

    assert "research_config" in ctx.artifacts, (
        f"research_config missing. Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert "building_blocks" in ctx.artifacts, (
        f"building_blocks missing. Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert "strategies" in ctx.artifacts, (
        f"strategies missing. Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert "portfolio_result" in ctx.artifacts, (
        f"portfolio_result missing. Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert "compiled_strategies" in ctx.artifacts, (
        f"compiled_strategies missing. Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert "deployment_result" in ctx.artifacts, (
        f"deployment_result missing. Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert "demo_result" in ctx.artifacts, (
        f"demo_result missing. Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert "archive_bundle" in ctx.artifacts, (
        f"archive_bundle missing. Artifacts: {list(ctx.artifacts.keys())}"
    )

    gate_iter_key = "gate_decision_HUMAN_APPROVE_ITERATION"
    gate_deploy_key = "gate_decision_HUMAN_APPROVE_DEPLOY"
    assert gate_iter_key in ctx.artifacts, (
        f"Gate decision for HUMAN_APPROVE_ITERATION not recorded. "
        f"Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert gate_deploy_key in ctx.artifacts, (
        f"Gate decision for HUMAN_APPROVE_DEPLOY not recorded. "
        f"Artifacts: {list(ctx.artifacts.keys())}"
    )
    assert ctx.artifacts[gate_iter_key]["action"] == "fallback"
    assert ctx.artifacts[gate_deploy_key]["action"] == "fallback"
