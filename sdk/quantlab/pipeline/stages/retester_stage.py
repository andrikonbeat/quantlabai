"""RetesterStage — runs phase4 Retester for the orchestrated campaign (REQ-07/08).

Mirrors the ``retest`` block of ``ResearchConfig`` into a ``RetesterConfig`` and
runs the phase4 Retester (Monte Carlo + Walk-Forward). The retest loop is
bounded: ``max_iterations`` from the block caps iterations; exceeding it halts
with a final report (D4). The stage writes a ``retest_result`` artifact. It
never triggers a dispatch or deploy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantlab.dsl.models import ResearchConfig, RetestBlock
from quantlab.phase4.retester import Retester, RetesterConfig
from quantlab.pipeline.base import PipelineContext, Stage


class RetesterStage(Stage):
    """Retest the strategy via phase4 Retester (REQ-07/08).

    **Requires**: research_config
    **Provides**: retest_result
    """

    name: str = "retester"
    requires: list[str] = ["research_config"]
    provides: list[str] = ["retest_result"]

    def __init__(
        self,
        retester: Retester | None = None,
        sqx_install_path: str | None = None,
        output_dir: str | None = None,
        cfx_path: str | Path | None = None,
    ) -> None:
        # Injectable for tests; the real Retester is constructed lazily so
        # registry instantiation stays side-effect free.
        self._retester = retester
        self._sqx_install_path = sqx_install_path
        self._output_dir = output_dir
        self._cfx_path = Path(cfx_path) if cfx_path else None

    def _build_config(self, block: RetestBlock) -> RetesterConfig:
        """Mirror the DSL ``retest`` block into a ``RetesterConfig``."""
        return RetesterConfig(
            strategy_id=block.strategy_id,
            databanks=list(block.databanks),
            monte_carlo_runs=block.monte_carlo_runs,
            mc_percentile=block.mc_percentile,
            walkforward_cycles=block.walkforward_cycles,
            min_trades=block.min_trades,
            confidence_level=block.confidence_level,
            broker_profile=block.broker_profile,
            cost_config=block.cost_config,
        )

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Run phase4 Retester and publish ``retest_result``.

        Args:
            ctx: Pipeline context with the ``research_config`` artifact.

        Returns:
            Dict with the retest result (or ``None`` when no retest block).
        """
        research_config: ResearchConfig = ctx.artifacts["research_config"]
        block = getattr(research_config, "retest", None)
        if block is None and self._cfx_path is None:
            ctx.artifacts["retest_result"] = None
            return {"retest_result": None}

        retester = self._retester
        if retester is None:  # pragma: no cover - exercised by integration
            retester = Retester(sqx_install_path=self._sqx_install_path)

        # DSL retest block takes precedence; a CFX path (no DSL block) sources
        # the config from the archive's RetesterData section.
        if block is not None:
            config = self._build_config(block)
        else:
            config = RetesterConfig.from_cfx(self._cfx_path)
        # REQ-1 (parameter-justification-matrix): the retest run produces a
        # matrix; a parameter deviating from its retest default without a
        # rationale raises ParameterMatrixError and blocks the run (spec:
        # "Matrix validation fails on missing rationale").
        from quantlab.agents.parameter_matrix import generate_run_matrix

        overrides = (
            ctx.config.get("rationale_overrides") if isinstance(ctx.config, dict) else None
        )
        parameter_matrix = generate_run_matrix(
            config, run_type="retest", rationale_overrides=overrides
        )
        # Bounded loop: Retester.run executes a single bounded campaign; the
        # max_iterations bound is enforced by the caller (WU-9 harness).
        result = await retester.run(
            config,
            campaign_name=research_config.campaign,
            output_dir=self._output_dir,
        )
        ctx.artifacts["retest_result"] = result
        ctx.artifacts["parameter_matrix"] = parameter_matrix
        return {
            "retest_result": result,
            "parameter_matrix": parameter_matrix,
        }
