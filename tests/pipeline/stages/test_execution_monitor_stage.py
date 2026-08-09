"""ExecutionMonitorStage tests (tasks 3.2 / 4.7, REQ-26).

The stage adapts :class:`ExecutionMonitor` to the pipeline ``Stage`` ABC:
it declares the I/O contract (``provides: monitor_result``), reads campaign
id and monitor tuning from ``ctx.config``, runs the injectable monitor, and
publishes the result to ``ctx.artifacts["monitor_result"]``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quantlab.agents.execution_monitor import ExecutionMonitor, MonitorResult, MonitorStatus
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.execution_monitor_stage import ExecutionMonitorStage


class TestExecutionMonitorStageContract:
    def test_name_and_io_contract(self) -> None:
        assert ExecutionMonitorStage.name == "execution_monitor"
        assert ExecutionMonitorStage.requires == []
        assert ExecutionMonitorStage.provides == ["monitor_result"]


class TestExecutionMonitorStageExecute:
    async def test_execute_runs_monitor_and_publishes_result(self) -> None:
        result = MonitorResult(
            status=MonitorStatus.HOLD,
            campaign_id="c1",
            phase="live_ops",
            message="stall detected",
        )
        monitor = AsyncMock(ExecutionMonitor)
        monitor.monitor = AsyncMock(return_value=result)
        stage = ExecutionMonitorStage(monitor=monitor)

        ctx = PipelineContext(
            config={"campaign_id": "c1", "monitor_phase": "live_ops"},
            artifacts={},
        )

        output = await stage.execute(ctx)

        assert output["monitor_result"] is result
        assert ctx.artifacts["monitor_result"] is result
        monitor.monitor.assert_awaited_once_with("c1", "live_ops", None)

    async def test_default_phase_and_campaign_id(self) -> None:
        result = MonitorResult(
            status=MonitorStatus.CONTINUE,
            campaign_id="campaign",
            phase="live_ops",
        )
        monitor = AsyncMock(ExecutionMonitor)
        monitor.monitor = AsyncMock(return_value=result)
        stage = ExecutionMonitorStage(monitor=monitor)

        ctx = PipelineContext(config={}, artifacts={})

        await stage.execute(ctx)

        monitor.monitor.assert_awaited_once_with("campaign", "live_ops", None)
