"""REQ-01/REQ-37: portfolio → compile → deploy → demo → archive stage chain.

The five post-optimize pipeline stages wrap the phase engines while declaring
the Stage I/O contract (name / requires / provides). Together they make the
full 14-phase lifecycle executable in one flow, preserving order (REQ-37).
"""

from __future__ import annotations

from datetime import date

import pytest

from quantlab.pipeline.base import Pipeline, PipelineContext
from quantlab.phase4.demo_deploy import DemoDeployer, DemoWindow


# ── Recording fakes (no AsyncMock — plain async functions) ──────────────────


async def _fake_optimize(weights: dict) -> dict:
    """Recorded portfolio optimizer: normalise nothing, echo weights."""
    return {k: round(w, 4) for k, w in weights.items()}


class _RecordingCompile:
    """Records every strategy handed to the compiler."""

    def __init__(self) -> None:
        self.strategies: list[str] = []

    async def __call__(self, strategy_id: str) -> str:
        self.strategies.append(strategy_id)
        return f"{strategy_id}.jfx"


class _FakeDeployAgent:
    """Minimal DeploymentAgent stand-in with an async package_jfx."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def package_jfx(self, jfx_path, account, *, campaign_id="demo", output_dir=None):
        self.calls.append((str(jfx_path), account))
        return {"status": "DRY_RUN_SUCCESS", "jfx_path": str(jfx_path)}


async def _fake_deploy(artifact, account) -> dict:
    return {"status": "DEPLOYED", "artifact": str(artifact)}


class _FakeArchivePhase:
    """Minimal ArchivePhase stand-in."""

    def __init__(self) -> None:
        self.calls = 0

    async def run(self, campaign_id, **kwargs):
        self.calls += 1
        return {"campaign_id": campaign_id, "plan": "MAINTAIN", "artifacts": []}


# ── Stage contracts ─────────────────────────────────────────────────────────


class TestStageContracts:
    """Each new stage declares its phase name and I/O contract."""

    def test_portfolio_stage_contract(self) -> None:
        from quantlab.pipeline.stages.agent_stages import PortfolioStage as Abstract

        from quantlab.pipeline.stages.portfolio_stage import PortfolioStage

        assert PortfolioStage.name == "portfolio"
        assert issubclass(PortfolioStage, Abstract)
        assert "portfolio_result" in PortfolioStage.provides

    def test_compile_stage_contract(self) -> None:
        from quantlab.pipeline.stages.compile_stage import CompileStage

        assert CompileStage.name == "compile"
        assert "compiled_strategies" in CompileStage.provides
        assert "portfolio_result" in CompileStage.requires

    def test_deploy_stage_contract(self) -> None:
        from quantlab.pipeline.stages.agent_stages import DeployStage as Abstract

        from quantlab.pipeline.stages.deploy_stage import DeployStage

        assert DeployStage.name == "deploy"
        assert issubclass(DeployStage, Abstract)
        assert "deployment_result" in DeployStage.provides

    def test_demo_stage_contract(self) -> None:
        from quantlab.pipeline.stages.demo_stage import DemoStage

        assert DemoStage.name == "demo"
        assert "demo_result" in DemoStage.provides
        assert "deployment_result" in DemoStage.requires

    def test_archive_stage_contract(self) -> None:
        from quantlab.pipeline.stages.archive_stage import ArchiveStage

        assert ArchiveStage.name == "archive"
        assert "archive_bundle" in ArchiveStage.provides
        assert "demo_result" in ArchiveStage.requires


# ── Individual stage behavior ───────────────────────────────────────────────


class TestPortfolioStageBehavior:
    async def test_normalizes_weights_into_portfolio_result(self) -> None:
        """GIVEN selected strategies with raw weights
        WHEN the portfolio stage runs
        THEN the normalized weights are published as portfolio_result.
        """
        from quantlab.pipeline.stages.portfolio_stage import PortfolioStage

        stage = PortfolioStage(optimize_fn=_fake_optimize)
        ctx = PipelineContext(
            config={"portfolio_weights": {"a": 0.6, "b": 0.4}},
            artifacts={"selected_strategies": ["a", "b"]},
        )
        out = await stage.execute(ctx)
        assert out["portfolio_result"] == {"a": 0.6, "b": 0.4}
        assert ctx.artifacts["portfolio_result"] == {"a": 0.6, "b": 0.4}


class TestCompileStageBehavior:
    async def test_compiles_each_portfolio_strategy(self) -> None:
        """GIVEN a portfolio result naming two strategies
        WHEN the compile stage runs
        THEN every strategy is routed to the compiler
        AND the artifacts carry the compiled outputs.
        """
        from quantlab.pipeline.stages.compile_stage import CompileStage

        compiler = _RecordingCompile()
        stage = CompileStage(compile_fn=compiler)
        ctx = PipelineContext(
            config={},
            artifacts={"portfolio_result": {"a": 0.6, "b": 0.4}},
        )
        out = await stage.execute(ctx)
        assert compiler.strategies == ["a", "b"]
        assert out["compiled_strategies"] == ["a.jfx", "b.jfx"]


class TestDeployStageBehavior:
    async def test_dry_run_default_packages_compiled_strategy(self) -> None:
        """GIVEN a compiled strategy
        WHEN the deploy stage runs with its default dry-run posture
        THEN the deployment agent packages the .jfx into a deployable JAR.
        """
        from quantlab.pipeline.stages.deploy_stage import DeployStage

        agent = _FakeDeployAgent()
        stage = DeployStage(agent=agent)
        ctx = PipelineContext(
            config={},
            artifacts={"compiled_strategies": ["a.jfx"]},
        )
        out = await stage.execute(ctx)
        assert agent.calls == [("a.jfx", None)]
        assert out["deployment_result"]["status"] == "DRY_RUN_SUCCESS"


class TestDemoStageBehavior:
    async def test_expired_window_blocks_renewal_fail_closed(self) -> None:
        """GIVEN the demo window expired
        WHEN the demo stage deploys
        THEN it blocks with pending HUMAN_APPROVE_DEMO (REQ-31 s2).
        """
        from quantlab.pipeline.stages.demo_stage import DemoStage

        window = DemoWindow(started_at=date(2026, 7, 1))
        deployer = DemoDeployer(
            deploy_fn=_fake_deploy, window=window, campaign_id="camp-1"
        )
        stage = DemoStage(deployer=deployer)
        ctx = PipelineContext(
            config={"demo_now": window.expires_at.isoformat()},
            artifacts={"deployment_result": {"status": "DEPLOYED"}},
        )
        out = await stage.execute(ctx)
        assert out["demo_result"].status == "BLOCKED_EXPIRED"
        assert out["demo_result"].pending_gate == "HUMAN_APPROVE_DEMO"

    async def test_active_window_deploys(self) -> None:
        """GIVEN the demo window active
        WHEN the demo stage deploys
        THEN the backend receives the deployment.
        """
        from quantlab.pipeline.stages.demo_stage import DemoStage

        window = DemoWindow(started_at=date(2026, 7, 1))
        deployer = DemoDeployer(
            deploy_fn=_fake_deploy, window=window, campaign_id="camp-1"
        )
        stage = DemoStage(deployer=deployer)
        ctx = PipelineContext(
            config={"demo_now": window.started_at.isoformat()},
            artifacts={"deployment_result": {"status": "DEPLOYED"}},
        )
        out = await stage.execute(ctx)
        assert out["demo_result"]["status"] == "DEPLOYED"


class TestArchiveStageBehavior:
    async def test_archive_composes_bundle(self) -> None:
        """GIVEN the demo phase completed
        WHEN the archive stage runs
        THEN an archive bundle with plan and stats is published.
        """
        from quantlab.pipeline.stages.archive_stage import ArchiveStage

        phase = _FakeArchivePhase()
        stage = ArchiveStage(phase=phase)
        ctx = PipelineContext(
            config={"campaign_id": "camp-1"},
            artifacts={"demo_result": {"status": "DEPLOYED"}},
        )
        out = await stage.execute(ctx)
        assert phase.calls == 1
        assert out["archive_bundle"]["campaign_id"] == "camp-1"
        assert out["archive_bundle"]["plan"] == "MAINTAIN"


# ── Full chain ──────────────────────────────────────────────────────────────


class TestFullChain:
    async def test_portfolio_to_archive_runs_in_order(self) -> None:
        """GIVEN the five post-optimize stages chained in order
        WHEN the pipeline executes
        THEN every phase artifact is published in lifecycle order (REQ-37).
        """
        from quantlab.pipeline.stages.archive_stage import ArchiveStage
        from quantlab.pipeline.stages.compile_stage import CompileStage
        from quantlab.pipeline.stages.demo_stage import DemoStage
        from quantlab.pipeline.stages.deploy_stage import DeployStage
        from quantlab.pipeline.stages.portfolio_stage import PortfolioStage

        window = DemoWindow(started_at=date(2026, 7, 1))
        pipeline = Pipeline(
            "post-optimize",
            stages=[
                PortfolioStage(optimize_fn=_fake_optimize),
                CompileStage(compile_fn=_RecordingCompile()),
                DeployStage(agent=_FakeDeployAgent()),
                DemoStage(
                    deployer=DemoDeployer(
                        deploy_fn=_fake_deploy,
                        window=window,
                        campaign_id="camp-1",
                    )
                ),
                ArchiveStage(phase=_FakeArchivePhase()),
            ],
        )
        ctx = PipelineContext(
            config={
                "portfolio_weights": {"a": 0.6, "b": 0.4},
                "demo_now": window.started_at.isoformat(),
                "campaign_id": "camp-1",
            },
            artifacts={"selected_strategies": ["a", "b"]},
        )
        for stage in pipeline.stages:
            await stage.execute(ctx)

        assert list(ctx.artifacts) == [
            "selected_strategies",
            "portfolio_result",
            "compiled_strategies",
            "deployment_result",
            "demo_result",
            "archive_bundle",
        ]
