"""DeployStage — packages compiled strategies into deployable artifacts (REQ-611, REQ-612, REQ-613).

Concrete implementation of the abstract ``DeployStage`` anchor: consumes the
compiled .jfx artifacts and deploys each strategy via ``JCloudDeployClient``.
The dry-run posture is preserved for backward compatibility; the client is
injectable for deterministic tests.
"""

from __future__ import annotations

from typing import Any

from quantlab.agents.deployment_agent import JCloudDeployClient, SimulatedJCloudDeployClient
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import DeployStage as _DeployStage


class DeployStage(_DeployStage):
    """Deploy compiled strategies via JCloudDeployClient (REQ-611/612/613).

    **Requires**: compiled_strategies
    **Provides**: deployment_result
    """

    name: str = "deploy"
    requires: list[str] = ["compiled_strategies"]
    provides: list[str] = ["deployment_result"]

    def __init__(
        self,
        agent: Any | None = None,
        *,
        dry_run: bool = True,
        strategy_ids: list[str] | None = None,
        jcloud_client: JCloudDeployClient | None = None,
    ) -> None:
        # Injectable for tests; the real JCloudDeployClient is constructed
        # lazily so registry instantiation stays side-effect free.
        self._agent = agent
        self._dry_run = dry_run
        self._strategy_ids = strategy_ids
        self._jcloud_client = jcloud_client

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Deploy each compiled strategy via JCloudDeployClient.

        When ``jcloud_client`` or ``strategy_ids`` is provided, the new
        multi-strategy deploy path is used. Otherwise, the legacy
        ``agent.package_jfx()`` path is used for backward compatibility.

        Args:
            ctx: Pipeline context with ``compiled_strategies`` (list of .jfx
                paths or dict of strategy_id -> .jfx path/JfxArtifact).

        Returns:
            Dict with ``deployment_result`` mapping strategy_id to deploy outcome.
        """
        compiled = ctx.artifacts.get("compiled_strategies") or {}
        if not compiled:
            ctx.artifacts["deployment_result"] = None
            return {"deployment_result": None}

        # Use new multi-strategy path when jcloud_client or strategy_ids is set.
        if self._jcloud_client is not None or self._strategy_ids is not None:
            return await self._execute_multi(ctx, compiled)

        # Legacy backward-compatible path: single agent.package_jfx() call.
        return await self._execute_legacy(ctx, compiled)

    async def _execute_multi(self, ctx: PipelineContext, compiled: Any) -> dict[str, Any]:
        """New path: deploy each strategy via JCloudDeployClient."""
        if self._strategy_ids is not None:
            strategy_ids = self._strategy_ids
        elif isinstance(compiled, dict):
            strategy_ids = list(compiled.keys())
        else:
            strategy_ids = ["0"]

        client = self._jcloud_client
        if client is None:  # pragma: no cover - exercised by integration
            client = SimulatedJCloudDeployClient()

        account = None
        if ctx.config:
            account = ctx.config.get("jcloud_account") or {}

        results: dict[str, Any] = {}
        for sid in strategy_ids:
            jfx_path = DeployStage._resolve_jfx_path(compiled, sid, strategy_ids)
            if jfx_path is None:
                results[sid] = {
                    "status": "FAILED",
                    "errors": [f"strategy_id {sid!r} not found in compiled_strategies"],
                }
                continue

            try:
                result = await client.deploy(jfx_path, sid, account)
                results[sid] = result.__dict__ if hasattr(result, "__dict__") else result
            except Exception as exc:  # noqa: BLE001
                results[sid] = {
                    "status": "FAILED",
                    "errors": [str(exc)],
                }

        ctx.artifacts["deployment_result"] = results
        return {"deployment_result": results}

    async def _execute_legacy(self, ctx: PipelineContext, compiled: Any) -> dict[str, Any]:
        """Legacy path: package the first compiled strategy via DeploymentAgent."""
        agent = self._agent
        if agent is None:  # pragma: no cover - exercised by integration
            from quantlab.agents.deployment_agent import DeploymentAgent

            agent = DeploymentAgent(dry_run=self._dry_run)

        account = None
        if ctx.config:
            account = ctx.config.get("jcloud_account")

        # compiled is a list in legacy mode; take the first entry.
        jfx_path = compiled[0] if isinstance(compiled, list) and compiled else None
        if jfx_path is None:
            ctx.artifacts["deployment_result"] = None
            return {"deployment_result": None}

        result = await agent.package_jfx(jfx_path, account)
        ctx.artifacts["deployment_result"] = result
        return {"deployment_result": result}

    @staticmethod
    def _resolve_jfx_path(
        compiled: Any,
        strategy_id: str,
        all_strategy_ids: list[str] | None = None,
    ) -> Any | None:
        """Resolve the .jfx path for a strategy_id from compiled artifacts.

        Handles both list (CompileStage output) and dict (CompilerPipeline
        direct output) formats. For lists, strategy_ids are matched by index
        using all_strategy_ids position. For dicts, strategy_id is the key.
        JfxArtifact values are unwrapped to their .path attribute.
        """
        if isinstance(compiled, dict):
            value = compiled.get(strategy_id)
            if value is None:
                return None
            return value.path if hasattr(value, "path") else value

        # List format: match by positional index in all_strategy_ids.
        if all_strategy_ids is not None:
            try:
                idx = all_strategy_ids.index(strategy_id)
                return compiled[idx] if 0 <= idx < len(compiled) else None
            except ValueError:
                return None

        # Fallback: treat strategy_id as a numeric index.
        try:
            idx = int(strategy_id)
            return compiled[idx] if 0 <= idx < len(compiled) else None
        except (ValueError, TypeError):
            return None
