"""CompileStage — compiles the portfolio strategies into .jfx (REQ-29, REQ-01 phase 10).

Routes every strategy named by ``portfolio_result`` through the compiler
pipeline (``JForexDeployer.export_and_compile``: export .java → javac →
.jfx). The compiler is injectable for deterministic tests; failures are
fail-closed — a compile error halts the stage (REQ-29/30: no partial .jfx,
no silent fallback).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from quantlab.pipeline.base import PipelineContext, Stage

#: Compile one strategy id → its .jfx artifact path.
CompileFn = Callable[[str], Awaitable[str | Path]]


class CompileStage(Stage):
    """Compile each portfolio strategy into a .jfx archive (REQ-29).

    **Requires**: portfolio_result
    **Provides**: compiled_strategies
    """

    name: str = "compile"
    requires: list[str] = ["portfolio_result"]
    provides: list[str] = ["compiled_strategies"]

    def __init__(
        self,
        compile_fn: CompileFn | None = None,
        *,
        sqx_install_path: str | None = None,
        output_dir: str | Path | None = None,
    ) -> None:
        # Injectable for tests; the real path is constructed lazily so
        # registry instantiation stays side-effect free.
        self._compile_fn = compile_fn
        self._sqx_install_path = sqx_install_path
        self._output_dir = output_dir

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Compile every strategy in the portfolio and publish the outputs.

        Args:
            ctx: Pipeline context with ``portfolio_result`` (strategy →
                weight mapping; keys are the strategy ids to compile).

        Returns:
            Dict with ``compiled_strategies`` (list of .jfx artifact paths).
        """
        portfolio = ctx.artifacts.get("portfolio_result") or {}
        strategy_ids = list(portfolio)

        compile_fn = self._compile_fn
        if compile_fn is None:  # pragma: no cover - exercised by integration
            from quantlab.phase4.jforex_deploy import JForexDeployer

            deployer = JForexDeployer(sqx_install_path=self._sqx_install_path)

            async def compile_fn(strategy_id: str) -> str | Path:
                return await deployer.export_and_compile(
                    strategy_id,
                    self._output_dir or "build/compiled",
                )

        compiled = [await compile_fn(sid) for sid in strategy_ids]
        ctx.artifacts["compiled_strategies"] = compiled
        return {"compiled_strategies": compiled}
