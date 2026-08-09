"""F2: optimizer and retester runs produce a parameter justification matrix.

Spec (parameter-justification-matrix REQ-1 scenarios):
- "Optimizer run produces matrix": optimizer entries have source=optimized and
  rationales reference the optimization objective.
- "Builder/retester run produces matrix": retest entries document parameter,
  value, rationale, source, confidence.
- "Matrix validation fails on missing rationale": an entry with an empty
  rationale raises ParameterMatrixError and blocks the run.

Strict TDD: written first — RED until stage matrix emission exists.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.agents.parameter_matrix import ParameterMatrixError
from quantlab.dsl.models import IterationConfig, OptimizeBlock, ResearchConfig, RetestBlock
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.optimizer_stage import OptimizerStage
from quantlab.pipeline.stages.retester_stage import RetesterStage


def _cfg(retest=None, optimize=None) -> ResearchConfig:
    return ResearchConfig(
        campaign="MatrixPipe",
        market="EURUSD",
        timeframe="H1",
        iteration_config=IterationConfig(max_iterations=1),
        retest=retest,
        optimize=optimize,
    )


class TestOptimizerRunProducesMatrix:
    """Spec scenario: GIVEN an optimizer run THEN the matrix is produced."""

    @pytest.mark.asyncio
    async def test_optimizer_run_publishes_parameter_matrix(self) -> None:
        """GIVEN an optimizer run over the optimize block parameters
        WHEN the stage completes
        THEN ctx.artifacts["parameter_matrix"] has an entry per parameter
        AND each entry has parameter/value/rationale/source/confidence
        AND source is "optimized" with a rationale referencing the objective.
        """
        fake_optimizer = AsyncMock(return_value=MagicMock())
        stage = OptimizerStage(optimizer=fake_optimizer)
        block = OptimizeBlock(strategy_id="S1", databanks=["EURUSD_H1"])
        ctx = PipelineContext(config={}, artifacts={"research_config": _cfg(optimize=block)})

        await stage.execute(ctx)

        assert "parameter_matrix" in ctx.artifacts
        matrix = ctx.artifacts["parameter_matrix"]
        assert matrix, "optimizer matrix must not be empty"
        objective = block.objective  # "SharpeRatio"
        for entry in matrix:
            assert {"parameter", "value", "rationale", "source", "confidence"} <= set(entry)
            assert entry["source"] == "optimized"
            assert objective in entry["rationale"], (
                f"optimizer rationale must reference the objective ({objective})"
            )
        params = {e["parameter"]: e for e in matrix}
        assert params["generations"]["value"] == 50
        assert params["population"]["value"] == 100


class TestRetesterRunProducesMatrix:
    """Spec scenario: retest runs produce matrix entries with rationale."""

    @pytest.mark.asyncio
    async def test_retest_run_publishes_parameter_matrix(self) -> None:
        """GIVEN a retest run with default-valued parameters
        THEN the matrix documents each parameter with a self-contained
        rationale (source "default", "using SQX default").
        """
        fake_retester = AsyncMock(return_value=MagicMock())
        stage = RetesterStage(retester=fake_retester)
        block = RetestBlock(strategy_id="S1", databanks=["EURUSD_H1"])
        ctx = PipelineContext(
            config={"rationale_overrides": {"databanks": "required by retest block"}},
            artifacts={"research_config": _cfg(retest=block)},
        )

        await stage.execute(ctx)

        assert "parameter_matrix" in ctx.artifacts
        matrix = ctx.artifacts["parameter_matrix"]
        assert matrix
        for entry in matrix:
            assert {"parameter", "value", "rationale", "source", "confidence"} <= set(entry)
            assert entry["rationale"], "every retest entry needs a self-contained rationale"
        params = {e["parameter"]: e for e in matrix}
        assert params["monte_carlo_runs"]["value"] == 100

    @pytest.mark.asyncio
    async def test_missing_rationale_blocks_the_run(self) -> None:
        """GIVEN a retest run with a non-default parameter and no rationale
        WHEN the stage generates the matrix
        THEN ParameterMatrixError is raised and the run is blocked
        (spec: "Matrix validation fails on missing rationale").
        """
        fake_retester = AsyncMock(return_value=MagicMock())
        stage = RetesterStage(retester=fake_retester)
        block = RetestBlock(strategy_id="S1", databanks=["EURUSD_H1"], monte_carlo_runs=500)
        ctx = PipelineContext(
            config={"rationale_overrides": {"databanks": "required by retest block"}},
            artifacts={"research_config": _cfg(retest=block)},
        )

        with pytest.raises(ParameterMatrixError, match="monte_carlo_runs"):
            await stage.execute(ctx)

    @pytest.mark.asyncio
    async def test_rationale_overrides_unblock_the_run(self) -> None:
        """GIVEN the retest run carries rationale_overrides in ctx.config
        THEN the non-default parameter is justified (source "manual") and the
        run completes.
        """
        fake_retester = AsyncMock(return_value=MagicMock())
        stage = RetesterStage(retester=fake_retester)
        block = RetestBlock(strategy_id="S1", databanks=["EURUSD_H1"], monte_carlo_runs=500)
        ctx = PipelineContext(
            config={
                "rationale_overrides": {
                    "databanks": "required by retest block",
                    "monte_carlo_runs": "500 MC runs for regime A",
                },
            },
            artifacts={"research_config": _cfg(retest=block)},
        )

        await stage.execute(ctx)

        matrix = ctx.artifacts["parameter_matrix"]
        params = {e["parameter"]: e for e in matrix}
        assert params["monte_carlo_runs"]["value"] == 500
        assert params["monte_carlo_runs"]["source"] == "manual"
        assert params["monte_carlo_runs"]["rationale"] == "500 MC runs for regime A"
