"""JForexDeployStage — deploy compiled .jfx strategies to JForex4 (REQ-06).

Consumes the ``compiled_strategies`` artifact produced by :class:`CompileStage`
and deploys each ``.jfx`` package through :class:`JForexStrategyBridge`. The
bridge is injectable for deterministic tests; failures are fail-closed — a
deploy error records ``FAILED`` for that strategy and never raises partial
state into the pipeline.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quantlab.pipeline.base import PipelineContext, Stage

logger = logging.getLogger(__name__)


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
        kb_entries = []
        for sid, jfx_path in pairs:
            try:
                bridge.deploy(Path(jfx_path))
                results[sid] = {"status": "OK"}
            except Exception as exc:
                error_info = {
                    "strategy_id": sid,
                    "jfx_path": str(jfx_path),
                    "error": str(exc),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "type": "deployment_failure",
                }
                results[sid] = {"status": "FAILED", "errors": [str(exc)]}
                kb_entries.append(error_info)

        # Write failures to Knowledge Lake
        if kb_entries:
            await self._write_to_kb(kb_entries, "deployment_failures")

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

    async def _write_to_kb(self, entries: list[dict], category: str) -> None:
        """Write entries to Knowledge Lake."""
        try:
            from quantlab.knowledge.store import KnowledgeStore
            store = KnowledgeStore()
            for entry in entries:
                import json
                content = json.dumps(entry, default=str)
                path = f"{category}/{datetime.now(UTC).isoformat().replace(':', '-')}.json"
                await store.write(path, content)
        except Exception as exc:
            logger.warning("Failed to write to Knowledge Lake: %s", exc)
