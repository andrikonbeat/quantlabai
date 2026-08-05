"""DeployStage — packages compiled strategies into deployable JARs (REQ-32, REQ-01 phase 11).

Concrete implementation of the abstract ``DeployStage`` anchor: consumes the
compiled .jfx artifacts and packages the deployable JAR via
``DeploymentAgent.package_jfx``. The dry-run posture is the default (REQ-32:
dry-run produces a mock package with zero network); the agent is injectable
for deterministic tests.
"""

from __future__ import annotations

from typing import Any

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.agent_stages import DeployStage as _DeployStage


class DeployStage(_DeployStage):
    """Package the compiled strategy into a deployable JAR (REQ-32).

    **Requires**: compiled_strategies
    **Provides**: deployment_result
    """

    name: str = "deploy"
    requires: list[str] = ["compiled_strategies"]
    provides: list[str] = ["deployment_result"]

    def __init__(self, agent: Any | None = None, *, dry_run: bool = True) -> None:
        # Injectable for tests; the real DeploymentAgent is constructed
        # lazily so registry instantiation stays side-effect free.
        self._agent = agent
        self._dry_run = dry_run

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Package the first compiled strategy into a deployable JAR.

        Args:
            ctx: Pipeline context with ``compiled_strategies``.

        Returns:
            Dict with ``deployment_result`` (the packaged JAR outcome).
        """
        compiled = ctx.artifacts.get("compiled_strategies") or []
        if not compiled:
            ctx.artifacts["deployment_result"] = None
            return {"deployment_result": None}

        agent = self._agent
        if agent is None:  # pragma: no cover - exercised by integration
            from quantlab.agents.deployment_agent import DeploymentAgent

            agent = DeploymentAgent(dry_run=self._dry_run)

        account = None
        if ctx.config:
            account = ctx.config.get("jcloud_account")
        result = await agent.package_jfx(compiled[0], account)
        ctx.artifacts["deployment_result"] = result
        return {"deployment_result": result}
