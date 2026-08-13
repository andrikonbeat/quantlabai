"""ExecutionMonitorStage — pipeline adapter for :class:`ExecutionMonitor` (REQ-26).

Wraps the long-polling ExecutionMonitor agent as a ``Stage`` so the live-ops
loop can compose it with ``guardian_evaluate`` / ``retester`` / ``optimizer``
stages. The stage is config-driven (no upstream artifact requirements): it
reads ``campaign_id``, ``monitor_phase`` and monitor tuning from
``ctx.config`` and publishes ``monitor_result`` to the context artifacts.

REQ-06 Scenario 2: when ``progress_fn`` is injected (e.g. a JForex live-feed
source built by :func:`quantlab.jforex.live_feed.jforex_progress_fn`), the
stage routes it into the monitor instead of the default SQX HTTP poller.
"""

from __future__ import annotations

from typing import Any

from quantlab.pipeline.base import PipelineContext, Stage


class ExecutionMonitorStage(Stage):
    """Monitor a running campaign with stall detection (REQ-26 event layer).

    **Requires**: (none — config-driven)
    **Provides**: monitor_result
    """

    name: str = "execution_monitor"
    requires: list[str] = []
    provides: list[str] = ["monitor_result"]

    def __init__(
        self,
        monitor: Any | None = None,
        *,
        progress_fn: Any | None = None,
    ) -> None:
        # Injectable for tests; the real ExecutionMonitor is constructed lazily.
        self._monitor = monitor
        self._progress_fn = progress_fn

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Run the monitor for the configured campaign and phase.

        Args:
            ctx: Pipeline context with ``config.campaign_id``,
                ``config.monitor_phase`` (default ``"live_ops"``) and optional
                tuning keys (``monitor_poll_interval``,
                ``monitor_expected_duration``, ``monitor_stall_multiplier``,
                ``monitor_llm_timeout``).

        Returns:
            Dict with ``monitor_result`` (a :class:`MonitorResult`).
        """
        campaign_id = "campaign"
        if ctx.config and ctx.config.get("campaign_id"):
            campaign_id = str(ctx.config["campaign_id"])
        phase = ctx.config.get("monitor_phase", "live_ops") if ctx.config else "live_ops"

        monitor = self._monitor
        if monitor is None:  # pragma: no cover - exercised by integration
            from quantlab.agents.execution_monitor import ExecutionMonitor

            monitor = ExecutionMonitor(progress_fn=self._progress_fn)

        result = await monitor.monitor(campaign_id, phase, None)
        ctx.artifacts["monitor_result"] = result
        return {"monitor_result": result}
