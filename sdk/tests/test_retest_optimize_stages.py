"""WU-5: retester / optimizer / dispatch stages + StageRegistry registration.

Covers REQ-07, REQ-08, REQ-09 (retest-optimize-stages spec) and REQ-17
(pipeline-core spec — stage registration).

Strict TDD: these tests are written first and must FAIL (RED) until the
stage modules and registry entries exist.
"""

import pytest

from quantlab.dsl.models import OptimizeBlock, ResearchConfig, RetestBlock
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.stages.config_review_stage import ConfigReviewStage
from quantlab.pipeline.stages.dispatch_stage import DispatchStage
from quantlab.pipeline.stages.optimizer_stage import OptimizerStage
from quantlab.pipeline.stages.retester_stage import RetesterStage


# ── Fakes ─────────────────────────────────────────────────────────────────────

class _FakeRetester:
    """Records the RetesterConfig it receives and returns a canned RetestResult."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def run(self, config, campaign_name=None, output_dir=None, timeout=None):
        from quantlab.phase4.retester import (
            MonteCarloResult,
            RetestResult,
            WalkForwardResult,
        )

        self.calls.append((config, campaign_name, output_dir))
        return RetestResult(
            strategy_id=config.strategy_id,
            monte_carlo=MonteCarloResult(
                runs=config.monte_carlo_runs,
                percentile=config.mc_percentile,
                percentile_net_profit=12.5,
                percentile_sharpe=1.3,
                percentile_drawdown=8.0,
                confidence_interval=(0.5, 1.5),
            ),
            walk_forward=WalkForwardResult(
                cycles=config.walkforward_cycles,
                avg_sharpe_ratio=1.1,
                avg_profit_factor=1.4,
                avg_drawdown=9.0,
                stability=0.8,
            ),
        )


class _FakeOptimizer:
    """Records the OptimizerConfig it receives and returns a canned OptimizationResult."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def run(self, config, campaign_name=None, output_dir=None, timeout=None):
        from quantlab.phase4.optimizer import OptimizationResult, WalkForwardCycle

        self.calls.append((config, campaign_name, output_dir))
        return OptimizationResult(
            strategy_id=config.strategy_id,
            cycles=[
                WalkForwardCycle(
                    cycle=1,
                    in_sample_start="2024-01-01",
                    in_sample_end="2024-06-30",
                    out_sample_start="2024-07-01",
                    out_sample_end="2024-12-31",
                    parameters={"max_sl_pips": 40},
                    metrics={"sharpe_ratio": 1.2},
                )
            ],
            summary={"num_cycles": 1, "avg_sharpe_ratio": 1.2},
            csv_path=None,
        )


class _FakeBuilder:
    """Duck-typed BuilderAgent used by DispatchStage tests.

    Exposes ``_dispatch_single`` (the AD-8 split boundary) plus a ``deploy``
    spy to prove the dispatch stage NEVER deploys (REQ-07 boundary / D4).
    """

    def __init__(self, dispatch_result=None):
        self.dispatch_calls: list[tuple] = []
        self.deploy_calls: list[tuple] = []
        self._dispatch_single_returns = dispatch_result

    async def _dispatch_single(
        self,
        cfx_bytes,
        config,
        skip_data_check=False,
        campaign_id=None,
        build_config=None,
        orchestrated=False,
    ):
        self.dispatch_calls.append(
            (cfx_bytes, config, skip_data_check, campaign_id, build_config)
        )
        if self._dispatch_single_returns is not None:
            return self._dispatch_single_returns

        # NOTE: cannot use a nested class here — class bodies bypass the
        # enclosing function scope (LOAD_NAME skips closures).
        from types import SimpleNamespace

        return SimpleNamespace(
            campaign_id=campaign_id or "sqx_test_1",
            cfx_bytes=cfx_bytes,
            sqcli_status="completed",
            export_paths=["/tmp/export.csv"],
        )

    async def deploy(self, *args, **kwargs):
        self.deploy_calls.append((args, kwargs))


def _research_config(retest=None, optimize=None) -> ResearchConfig:
    from quantlab.dsl.models import IterationConfig

    return ResearchConfig(
        campaign="RetestOptTest",
        market="EURUSD",
        timeframe="H1",
        iteration_config=IterationConfig(max_iterations=1),
        retest=retest,
        optimize=optimize,
    )


def _ctx(research_config: ResearchConfig, **artifacts) -> PipelineContext:
    return PipelineContext(config={}, artifacts={"research_config": research_config, **artifacts})


# ── REQ-17: StageRegistry registration ────────────────────────────────────────

class TestStageRegistryRegistration:
    """REQ-17: config_review / retester / optimizer / dispatch registered."""

    def test_registry_returns_retester_stage(self) -> None:
        stage_class = StageRegistry().get_stage_class("retester")
        assert stage_class is RetesterStage

    def test_registry_returns_optimizer_stage(self) -> None:
        stage_class = StageRegistry().get_stage_class("optimizer")
        assert stage_class is OptimizerStage

    def test_registry_returns_dispatch_stage(self) -> None:
        stage_class = StageRegistry().get_stage_class("dispatch")
        assert stage_class is DispatchStage

    def test_registry_returns_config_review_stage(self) -> None:
        stage_class = StageRegistry().get_stage_class("config_review")
        assert stage_class is ConfigReviewStage


# ── REQ-07/08: RetesterStage ──────────────────────────────────────────────────

class TestRetesterStage:
    """RetesterStage wraps phase4 Retester (REQ-07/08)."""

    def test_name(self) -> None:
        assert RetesterStage.name == "retester"

    def test_requires_research_config(self) -> None:
        assert RetesterStage.requires == ["research_config"]

    def test_provides_retest_result(self) -> None:
        assert RetesterStage.provides == ["retest_result"]

    @pytest.mark.asyncio
    async def test_execute_runs_phase4_retester(self) -> None:
        """GIVEN a ResearchConfig with a retest block
        WHEN RetesterStage executes
        THEN it runs phase4 Retester with a RetesterConfig mirroring the block
        AND writes the RetestResult into ``retest_result``.
        """
        fake = _FakeRetester()
        block = RetestBlock(
            strategy_id="S1",
            databanks=["EURUSD_H1"],
            monte_carlo_runs=50,
            mc_percentile=90,
            walkforward_cycles=3,
            min_trades=20,
            confidence_level=0.9,
        )
        stage = RetesterStage(retester=fake)
        ctx = _ctx(_research_config(retest=block))

        result = await stage.execute(ctx)

        assert result["retest_result"] is ctx.artifacts["retest_result"]
        assert len(fake.calls) == 1
        config = fake.calls[0][0]
        assert config.strategy_id == "S1"
        assert config.databanks == ["EURUSD_H1"]
        assert config.monte_carlo_runs == 50
        assert config.mc_percentile == 90
        assert config.walkforward_cycles == 3
        assert config.min_trades == 20
        assert config.confidence_level == 0.9
        assert fake.calls[0][1] == "RetestOptTest"  # campaign name
        assert ctx.artifacts["retest_result"].strategy_id == "S1"

    @pytest.mark.asyncio
    async def test_execute_without_retest_block_skips(self) -> None:
        """GIVEN a ResearchConfig with no retest block
        WHEN RetesterStage executes
        THEN it records a None retest_result and does NOT run the Retester.
        """
        fake = _FakeRetester()
        stage = RetesterStage(retester=fake)
        ctx = _ctx(_research_config())

        result = await stage.execute(ctx)

        assert result["retest_result"] is None
        assert ctx.artifacts["retest_result"] is None
        assert fake.calls == []


# ── REQ-09: OptimizerStage ────────────────────────────────────────────────────

class TestOptimizerStage:
    """OptimizerStage wraps phase4 Optimizer and parses CSV (REQ-09)."""

    def test_name(self) -> None:
        assert OptimizerStage.name == "optimizer"

    def test_requires_research_config(self) -> None:
        assert OptimizerStage.requires == ["research_config"]

    def test_provides_optimization_result(self) -> None:
        assert OptimizerStage.provides == ["optimization_result"]

    @pytest.mark.asyncio
    async def test_execute_parses_csv_into_optimization_result(self) -> None:
        """GIVEN a ResearchConfig with an optimize block
        WHEN OptimizerStage executes
        THEN it runs phase4 Optimizer and writes the parsed OptimizationResult.
        """
        fake = _FakeOptimizer()
        block = OptimizeBlock(
            strategy_id="S1",
            method="Genetic",
            objective="SharpeRatio",
            databanks=["EURUSD_H1"],
        )
        stage = OptimizerStage(optimizer=fake)
        ctx = _ctx(_research_config(optimize=block))

        result = await stage.execute(ctx)

        assert result["optimization_result"] is ctx.artifacts["optimization_result"]
        assert len(fake.calls) == 1
        config = fake.calls[0][0]
        assert config.strategy_id == "S1"
        assert config.method == "Genetic"
        assert config.objective == "SharpeRatio"
        assert config.databanks == ["EURUSD_H1"]
        parsed = ctx.artifacts["optimization_result"]
        assert parsed.strategy_id == "S1"
        assert parsed.summary["avg_sharpe_ratio"] == 1.2

    @pytest.mark.asyncio
    async def test_optimize_never_redispatches(self) -> None:
        """D4: after optimize there is NO feedback loop to re-dispatch.

        The optimizer fake exposes a dispatch spy; executing the stage must
        never call it.
        """
        fake = _FakeOptimizer()
        fake.dispatch_calls = []
        fake.dispatch = lambda *a, **k: fake.dispatch_calls.append((a, k)) or None
        block = OptimizeBlock(strategy_id="S1", databanks=["EURUSD_H1"])
        stage = OptimizerStage(optimizer=fake)
        ctx = _ctx(_research_config(optimize=block))

        await stage.execute(ctx)

        assert fake.dispatch_calls == []
        assert "HUMAN_APPROVE_CONFIG" not in ctx.artifacts  # no gate written either

    @pytest.mark.asyncio
    async def test_execute_without_optimize_block_skips(self) -> None:
        fake = _FakeOptimizer()
        stage = OptimizerStage(optimizer=fake)
        ctx = _ctx(_research_config())

        result = await stage.execute(ctx)

        assert result["optimization_result"] is None
        assert fake.calls == []


# ── DispatchStage ─────────────────────────────────────────────────────────────

class TestDispatchStage:
    """DispatchStage encapsulates builder dispatch; never deploys (AD-8)."""

    def test_name(self) -> None:
        assert DispatchStage.name == "dispatch"

    def test_requires_cfx_bytes(self) -> None:
        assert DispatchStage.requires == ["cfx_bytes"]

    def test_provides_dispatch_outputs(self) -> None:
        assert DispatchStage.provides == ["campaign_id", "sqcli_status", "export_paths"]

    @pytest.mark.asyncio
    async def test_execute_dispatches_via_injected_builder(self) -> None:
        """GIVEN an approved HUMAN_APPROVE_CONFIG gate decision
        WHEN DispatchStage executes
        THEN it dispatches via the builder and publishes dispatch outputs.
        """
        builder = _FakeBuilder()
        stage = DispatchStage(builder=builder)
        ctx = _ctx(
            _research_config(),
            cfx_bytes=b"cfx-bytes",
            gate_decision_HUMAN_APPROVE_CONFIG={"action": "approved", "reason": "ok"},
        )

        result = await stage.execute(ctx)

        assert len(builder.dispatch_calls) == 1
        cfx, config, skip_data, campaign_id, build_config = builder.dispatch_calls[0]
        assert cfx == b"cfx-bytes"
        assert campaign_id == "RetestOptTest"  # forwarded from research_config
        assert ctx.artifacts["campaign_id"] == "RetestOptTest"
        assert ctx.artifacts["sqcli_status"] == "completed"
        assert ctx.artifacts["export_paths"] == ["/tmp/export.csv"]
        assert result["campaign_id"] == "RetestOptTest"

    @pytest.mark.asyncio
    async def test_execute_never_deploys(self) -> None:
        """REQ-07 boundary: dispatch NEVER calls a deploy path (D4, no deploy)."""
        builder = _FakeBuilder()
        stage = DispatchStage(builder=builder)
        ctx = _ctx(
            _research_config(),
            cfx_bytes=b"cfx-bytes",
            gate_decision_HUMAN_APPROVE_CONFIG={"action": "approved"},
        )

        await stage.execute(ctx)

        assert builder.deploy_calls == []

    @pytest.mark.asyncio
    async def test_held_gate_blocks_dispatch(self) -> None:
        """REQ-05/06: a HOLD/absent approval on HUMAN_APPROVE_CONFIG blocks dispatch.

        GIVEN a gate decision that is not an approval
        WHEN DispatchStage executes
        THEN the builder is never called and dispatch_blocked is published.
        """
        builder = _FakeBuilder()
        stage = DispatchStage(builder=builder)
        ctx = _ctx(
            _research_config(),
            cfx_bytes=b"cfx-bytes",
            gate_decision_HUMAN_APPROVE_CONFIG={"action": "hold", "reason": "fail closed"},
        )

        result = await stage.execute(ctx)

        assert builder.dispatch_calls == []
        assert ctx.artifacts["dispatch_blocked"] is True
        assert result["dispatch_blocked"] is True
        assert result["campaign_id"] is None
