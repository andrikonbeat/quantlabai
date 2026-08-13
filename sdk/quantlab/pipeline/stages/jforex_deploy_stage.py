"""JForexDeployStage — deploy compiled .jfx strategies to JForex4 (REQ-06).

Consumes the ``compiled_strategies`` artifact produced by :class:`CompileStage`
and deploys each ``.jfx`` package through :class:`JForexStrategyBridge`. The
bridge is injectable for deterministic tests; failures are fail-closed — a
deploy error records ``FAILED`` for that strategy and never raises partial
state into the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantlab.pipeline.base import PipelineContext, Stage


class JForexDeployStage(Stage):
    """Deploy every compiled strategy to JForex4 (REQ-06 Scenario 1).

    **Requires**: compiled_strategies
    **Provides**: deployment_result
    """

    name: str = "jforex_deploy"
    requires: list[str] = ["compiled_strategies"]
    provides: list[str] = ["deployment_result"]

    def __init__(self, bridge: Any | None = None) -> None:
        # Injectable for tests; the real bridge is constructed lazily so
        # registry instantiation stays side-effect free.
        self._bridge = bridge

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Deploy each compiled .jfx via JForexStrategyBridge.

        Args:
            ctx: Pipeline context with ``compiled_strategies`` (list of
                ``.jfx`` paths, a dict of ``strategy_id -> .jfx path``, or a
                list of artifact objects with ``.path``).

        Returns:
            Dict with ``deployment_result`` mapping strategy_id to outcome.
        """
        compiled = ctx.artifacts.get("compiled_strategies") or {}
        if not compiled:
            ctx.artifacts["deployment_result"] = {}
            return {"deployment_result": {}}

        bridge = self._bridge
        if bridge is None:  # pragma: no cover - exercised by integration
            from quantlab.jforex.strategy_bridge import JForexStrategyBridge

            bridge = JForexStrategyBridge()

        pairs = self._resolve_pairs(compiled)
        results: dict[str, Any] = {}
        for sid, jfx_path in pairs:
            try:
                bridge.deploy(Path(jfx_path))
                results[sid] = {"status": "OK"}
            except Exception as exc:  # noqa: BLE001 - fail-closed per strategy
                results[sid] = {"status": "FAILED", "errors": [str(exc)]}

        ctx.artifacts["deployment_result"] = results
        return {"deployment_result": results}

    @staticmethod
    def _resolve_pairs(
        compiled: Any,
    ) -> list[tuple[str, Any]]:
        """Normalize compiled_strategies into (strategy_id, jfx_path) pairs.

        Handles dict input (strategy_id keys) and list input (positional
        ids, unwrapping artifact objects to their ``.path``).
        """
        if isinstance(compiled, dict):
            return [
                (sid, value.path if hasattr(value, "path") else value)
                for sid, value in compiled.items()
            ]
        items = list(compiled)
        return [
            (str(idx), item.path if hasattr(item, "path") else item)
            for idx, item in enumerate(items)
        ]