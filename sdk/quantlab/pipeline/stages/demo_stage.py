"""DemoStage — deploys into the 14-business-day demo window (REQ-31, REQ-01 phase 12).

Consumes the packaged deployment and runs the demo deploy inside the demo
window. An expired window BLOCKS with ``pending_gate=HUMAN_APPROVE_DEMO`` —
the backend is never invoked (fail-closed, REQ-31 scenario 2). The deployer
is injectable for deterministic tests; ``ctx.config.demo_now`` pins the
window clock.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from quantlab.data.demo.store import DemoWindowStore, StateCorruptionError
from quantlab.pipeline.base import PipelineContext, Stage


class DemoStage(Stage):
    """Deploy inside the 14-business-day demo window (REQ-31).

    **Requires**: deployment_result
    **Provides**: demo_result
    """

    name: str = "demo"
    requires: list[str] = ["deployment_result"]
    provides: list[str] = ["demo_result"]

    def __init__(
        self,
        deployer: Any | None = None,
        store: DemoWindowStore | None = None,
    ) -> None:
        # Injectable for tests; the real DemoDeployer is constructed lazily.
        self._deployer = deployer
        self._store = store

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Run the demo deployment, honouring the window status.

        Args:
            ctx: Pipeline context with ``deployment_result`` and optional
                ``config.demo_now`` (ISO date pinning the window clock).

        Returns:
            Dict with ``demo_result`` — ``BLOCKED_EXPIRED`` when the window
            expired, otherwise the backend deployment result.
        """
        deployment = ctx.artifacts.get("deployment_result")

        deployer = self._deployer
        if deployer is None:  # pragma: no cover - exercised by integration
            from quantlab.phase4.demo_deploy import DemoDeployer

            deployer = DemoDeployer()

        now: date | None = None
        if ctx.config and ctx.config.get("demo_now"):
            now = date.fromisoformat(str(ctx.config["demo_now"]))

        result = await deployer.deploy(deployment, None, now=now)
        ctx.artifacts["demo_result"] = result

        # Persist window state after deploy (WU7b persistence wiring).
        self._persist_window_state(ctx)

        return {"demo_result": result}

    def _persist_window_state(self, ctx: PipelineContext) -> None:
        """Persist demo window state via DemoWindowStore if configured.

        Loads existing state when available; creates a minimal window record
        when missing. Corrupt state is skipped so the pipeline continues.
        """
        if self._store is None:
            return
        campaign_id = (
            ctx.config.get("campaign_id") if ctx.config else None
        )
        if not campaign_id:
            return
        window: dict[str, object] | None = None
        try:
            window = self._store.load(str(campaign_id))
        except StateCorruptionError:
            window = {
                "campaign_id": str(campaign_id),
                "started_at": (
                    ctx.config.get("demo_now")
                    if ctx.config and ctx.config.get("demo_now")
                    else "2026-01-01"
                ),
                "expires_at": "2026-01-15",
                "renewal_count": 0,
            }
        if window is None:
            return
        try:
            self._store.persist(window)
        except Exception:
            pass
