"""ExecutionMonitor tests (execution-monitor spec, REQ-42).

Covers the long-polling monitor contract:

- Normal progress → CONTINUE, no stall event (polling records updates).
- Stall (no progress for 2x expected duration) → stall event, checkpoint
  written BEFORE LLM diagnostics, HOLD on LLM timeout (fail-closed).
- Stall resolved by remediation → CONTINUE with diagnostics attached.
- Daemon disconnection → daemon_lost event → HOLD.
- Stall threshold is configurable multiplier x expected duration; the stall
  event carries the measured stalled-for seconds (triangulation).
- Pure status-text → progress fraction mapping.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from quantlab.agents.execution_monitor import (
    ExecutionMonitor,
    MonitorResult,
    MonitorStatus,
    extract_progress_fraction,
)
from quantlab.substrate.executor import Phase, PhaseConfig


@dataclass
class FakeClock:
    """Deterministic monotonic clock for the monitor's stall accounting."""

    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _config(campaign_id: str = "campaign-x") -> PhaseConfig:
    return PhaseConfig(
        sqx_install_path="/home/ogzuz/Proyectos/SQX_144_2953_linux_20260601",
        campaign_id=campaign_id,
        force_mock=True,
    )


def _event_types(result: MonitorResult) -> list[str]:
    return [e.get("event_type") for e in result.events]


class TestProgressFraction:
    """Pure mapping of SQX status text to a progress signal."""

    def test_generated_count_maps_to_fraction(self) -> None:
        text = (
            "Status of project p\n"
            "Strategies generated                          12\n"
            "In databank                                      0\n"
        )
        assert extract_progress_fraction(text) == pytest.approx(0.012)

    def test_completed_status_is_terminal(self) -> None:
        text = "Project execution stopped\n"
        assert extract_progress_fraction(text) == 1.0

    def test_no_measurable_progress_returns_none(self) -> None:
        assert extract_progress_fraction("Status of project p\nStatus: running\n") is None

    def test_huge_generated_count_is_capped_below_completion(self) -> None:
        text = "Strategies generated                        99999\n"
        assert extract_progress_fraction(text) == pytest.approx(0.999)


class TestMonitorLoop:
    async def test_normal_progress_returns_continue_without_stall(self) -> None:
        clock = FakeClock()
        values = iter([(True, 0.2), (True, 0.5), (True, 1.0)])
        events: list[dict] = []

        async def progress_fn() -> tuple[bool, float | None]:
            clock.advance(1.0)
            return next(values)

        monitor = ExecutionMonitor(
            progress_fn=progress_fn,
            event_bus=events.append,
            now_fn=clock,
            poll_interval=0.001,
            expected_duration=10.0,
            stall_multiplier=2.0,
        )

        result = await monitor.monitor("campaign-x", Phase.BUILD, _config())

        assert result.status == MonitorStatus.CONTINUE
        assert "stall" not in _event_types(result)
        assert "campaign_complete" in _event_types(result)
        # Events flowed to the campaign event bus too.
        assert any(e.get("event_type") == "campaign_complete" for e in events)

    async def test_stall_with_llm_timeout_returns_hold(self) -> None:
        clock = FakeClock()
        order: list[str] = []

        async def progress_fn() -> tuple[bool, float | None]:
            clock.advance(5.0)
            return (True, 0.4)  # frozen progress forever

        async def checkpoint_writer() -> None:
            order.append("checkpoint")

        async def diagnostics_fn(_ctx: dict) -> dict | None:
            order.append("diagnostics")
            await asyncio.sleep(5.0)  # exceeds the 0.01s budget

        monitor = ExecutionMonitor(
            progress_fn=progress_fn,
            checkpoint_writer=checkpoint_writer,
            diagnostics_fn=diagnostics_fn,
            now_fn=clock,
            poll_interval=0.001,
            expected_duration=10.0,
            stall_multiplier=2.0,
            llm_timeout=0.01,
        )

        result = await monitor.monitor("campaign-x", Phase.OPTIMIZE, _config())

        assert result.status == MonitorStatus.HOLD
        assert result.checkpoint_written is True
        # Checkpoint MUST be written before diagnostics are invoked (REQ spec:
        # "a checkpoint is written immediately, then diagnostics after").
        assert order == ["checkpoint", "diagnostics"]
        event_types = _event_types(result)
        assert "stall" in event_types
        assert "diagnostics_timeout" in event_types
        assert result.diagnostics is None

    async def test_stall_sets_stalled_for_to_2x_expected(self) -> None:
        clock = FakeClock()
        stall_event: dict = {}

        async def progress_fn() -> tuple[bool, float | None]:
            clock.advance(5.0)
            return (True, 0.4)

        async def diagnostics_fn(_ctx: dict) -> dict | None:
            return None  # no remediation → HOLD, but record the stall event

        def capture(event: dict) -> None:
            if event.get("event_type") == "stall":
                stall_event.update(event)

        monitor = ExecutionMonitor(
            progress_fn=progress_fn,
            diagnostics_fn=diagnostics_fn,
            event_bus=capture,
            now_fn=clock,
            poll_interval=0.001,
            expected_duration=10.0,
            stall_multiplier=2.0,
            llm_timeout=1.0,
        )

        result = await monitor.monitor("campaign-x", Phase.RETEST, _config())

        assert result.status == MonitorStatus.HOLD
        # Progress froze for exactly 2 x 10s = 20s before the stall fired.
        assert stall_event.get("stalled_for") == pytest.approx(20.0)
        assert stall_event.get("threshold") == pytest.approx(20.0)

    async def test_stall_threshold_uses_configured_multiplier(self) -> None:
        clock = FakeClock()
        stall_event: dict = {}

        async def progress_fn() -> tuple[bool, float | None]:
            clock.advance(3.0)
            return (True, 0.4)

        async def diagnostics_fn(_ctx: dict) -> dict | None:
            return None

        def capture(event: dict) -> None:
            if event.get("event_type") == "stall":
                stall_event.update(event)

        monitor = ExecutionMonitor(
            progress_fn=progress_fn,
            diagnostics_fn=diagnostics_fn,
            event_bus=capture,
            now_fn=clock,
            poll_interval=0.001,
            expected_duration=5.0,
            stall_multiplier=3.0,
            llm_timeout=1.0,
        )

        result = await monitor.monitor("campaign-x", Phase.BUILD, _config())

        assert result.status == MonitorStatus.HOLD
        # 3 x 5s = 15s of frozen progress before the stall fired.
        assert stall_event.get("stalled_for") == pytest.approx(15.0)
        assert stall_event.get("threshold") == pytest.approx(15.0)

    async def test_advancing_progress_resets_the_stall_clock(self) -> None:
        clock = FakeClock()
        values = iter([(True, 0.1), (True, 0.3), (True, 0.6), (True, 1.0)])

        async def progress_fn() -> tuple[bool, float | None]:
            clock.advance(5.0)  # 20s total — well past 2x expected
            return next(values)

        monitor = ExecutionMonitor(
            progress_fn=progress_fn,
            now_fn=clock,
            poll_interval=0.001,
            expected_duration=5.0,
            stall_multiplier=2.0,
        )

        result = await monitor.monitor("campaign-x", Phase.BUILD, _config())

        assert result.status == MonitorStatus.CONTINUE
        assert "stall" not in _event_types(result)

    async def test_stall_with_remediation_returns_continue(self) -> None:
        clock = FakeClock()
        remediation = {"action": "restart_phase", "reason": "no strategy progress"}

        async def progress_fn() -> tuple[bool, float | None]:
            clock.advance(30.0)
            return (True, 0.4)

        async def checkpoint_writer() -> None:
            return None

        async def diagnostics_fn(_ctx: dict) -> dict | None:
            return remediation

        monitor = ExecutionMonitor(
            progress_fn=progress_fn,
            checkpoint_writer=checkpoint_writer,
            diagnostics_fn=diagnostics_fn,
            now_fn=clock,
            poll_interval=0.001,
            expected_duration=10.0,
            stall_multiplier=2.0,
            llm_timeout=1.0,
        )

        result = await monitor.monitor("campaign-x", Phase.PORTFOLIO, _config())

        assert result.status == MonitorStatus.CONTINUE
        assert result.diagnostics == remediation
        assert result.checkpoint_written is True
        assert "remediation" in _event_types(result)

    async def test_daemon_lost_returns_hold(self) -> None:
        clock = FakeClock()

        async def progress_fn() -> tuple[bool, float | None]:
            return (False, None)

        monitor = ExecutionMonitor(
            progress_fn=progress_fn,
            now_fn=clock,
            poll_interval=0.001,
        )

        result = await monitor.monitor("campaign-x", Phase.BUILD, _config())

        assert result.status == MonitorStatus.HOLD
        assert "daemon_lost" in _event_types(result)
        assert "HOLD" in result.message

    async def test_stall_without_diagnostics_provider_holds_fail_closed(self) -> None:
        clock = FakeClock()

        async def progress_fn() -> tuple[bool, float | None]:
            clock.advance(30.0)
            return (True, 0.4)

        monitor = ExecutionMonitor(
            progress_fn=progress_fn,
            now_fn=clock,
            poll_interval=0.001,
            expected_duration=10.0,
            stall_multiplier=2.0,
        )

        result = await monitor.monitor("campaign-x", Phase.BUILD, _config())

        assert result.status == MonitorStatus.HOLD
        assert "no diagnostics provider" in result.message
        assert "stall" in _event_types(result)
