"""OptimizerStage — runs phase4 Optimizer for the orchestrated campaign (REQ-09).

Mirrors the ``optimize`` block of ``ResearchConfig`` into an ``OptimizerConfig``
and runs the phase4 Optimizer (walk-forward optimization). The Optimizer parses
the exported CSV into an ``OptimizationResult``, which the stage publishes as an
``optimization_result`` artifact.

There is NO feedback loop: after optimize the flow stops at recommendations
plus a human gate — never a re-dispatch (D4).
"""

from __future__ import annotations

from typing import Any

from quantlab.dsl.models import OptimizeBlock, ResearchConfig
from quantlab.phase4.optimizer import Optimizer, OptimizerConfig
from quantlab.pipeline.base import PipelineContext, Stage


class OptimizerStage(Stage):
    """Optimize the strategy via phase4 Optimizer (REQ-09).

    **Requires**: research_config
    **Provides**: optimization_result
    """

    name: str = "optimizer"
    requires: list[str] = ["research_config"]
    provides: list[str] = ["optimization_result"]

    def __init__(
        self,
        optimizer: Optimizer | None = None,
        sqx_install_path: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        # Injectable for tests; the real Optimizer is constructed lazily so
        # registry instantiation stays side-effect free.
        self._optimizer = optimizer
        self._sqx_install_path = sqx_install_path
        self._output_dir = output_dir

    def _build_config(self, block: OptimizeBlock) -> OptimizerConfig:
        """Mirror the DSL ``optimize`` block into an ``OptimizerConfig``."""
        return OptimizerConfig(
            strategy_id=block.strategy_id,
            method=block.method,
            objective=block.objective,
            walkforward_cycles=block.walkforward_cycles,
            population=block.population,
            generations=block.generations,
            crossover=block.crossover,
            mutation=block.mutation,
            databanks=list(block.databanks or []),
        )

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Run phase4 Optimizer and publish ``optimization_result``.

        Args:
            ctx: Pipeline context with the ``research_config`` artifact.

        Returns:
            Dict with the parsed optimization result (or ``None`` when no
            optimize block is configured).
        """
        research_config: ResearchConfig = ctx.artifacts["research_config"]
        block = getattr(research_config, "optimize", None)
        if block is None:
            ctx.artifacts["optimization_result"] = None
            return {"optimization_result": None}

        optimizer = self._optimizer
        if optimizer is None:  # pragma: no cover - exercised by integration
            optimizer = Optimizer(sqx_install_path=self._sqx_install_path)

        config = self._build_config(block)
        result = await optimizer.run(
            config,
            campaign_name=research_config.campaign,
            output_dir=self._output_dir,
        )
        ctx.artifacts["optimization_result"] = result
        # D4: no re-dispatch after optimize — the flow stops at recommendations.
        return {"optimization_result": result}
