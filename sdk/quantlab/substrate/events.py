"""Substrate event detection (REQ-42) — CampaignMonitor as the substrate's
event-detection component, parameterized per phase.

Stall/config-error signals detected on the substrate's polling flow out as
``WatcherEvent`` objects; a stall/error halts the phase for a human
(design state machine: ``stall/error → FAILED``).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from quantlab.sqx.campaign_monitor import (
    BaselineConfig,
    CampaignMonitor,
    WatcherEvent,
    compute_baseline,
)

logger = logging.getLogger(__name__)

# Stall severity levels that force a FAILED halt (fail-closed for humans).
_HALT_SEVERITIES = ("WARNING", "CRITICAL")


def phase_name(phase: Any) -> str:
    """Normalize a Phase enum or raw string to its phase name."""
    return phase.value if hasattr(phase, "value") else str(phase)


def baseline_for_phase(phase: Any, poll_interval: float = 5.0) -> BaselineConfig:
    """Phase-parameterized monitor baseline (build/retest/optimize/portfolio)."""
    name = phase_name(phase)
    if name == "build":
        config: dict[str, Any] = {"timeframe": "H1"}
    elif name in ("retest", "optimize"):
        config = {"timeframe": "H1", "walk_forward": True, "monte_carlo": True}
    else:  # portfolio
        config = {
            "timeframe": "H1",
            "walk_forward": False,
            "monte_carlo": False,
            "generations": 10,
        }
    return compute_baseline(config, poll_interval=poll_interval)


def has_halt_event(events: list[WatcherEvent]) -> bool:
    """Return whether any WARNING/CRITICAL stall/config event was emitted."""
    return any(e.severity in _HALT_SEVERITIES for e in events)


class SubstrateEventDetector:
    """CampaignMonitor wired as the substrate's per-phase event detector.

    Args:
        campaign_id: Campaign being monitored.
        base_url: SQX HTTP API base URL.
        phase: Phase enum value or phase name (build/retest/optimize/portfolio).
        poll_interval: Monitor poll interval (seconds).
        on_watcher_event: Callback for every emitted event.
        export_dir: Directory of exported artifacts (strategies.csv) that feed
            stall detection (REQ-14-style artifact signal).
    """

    def __init__(
        self,
        campaign_id: str,
        base_url: str,
        phase: Any,
        *,
        poll_interval: float = 1.0,
        on_watcher_event: Callable[[WatcherEvent], None] | None = None,
        export_dir: str | Path | None = None,
    ) -> None:
        self._campaign_id = campaign_id
        self._phase = phase
        self._monitor = CampaignMonitor(
            campaign_id=campaign_id,
            base_url=base_url,
            baseline=baseline_for_phase(phase, poll_interval=poll_interval),
            poll_interval=poll_interval,
            on_watcher_event=on_watcher_event,
            config={"timeframe": "H1"},
            export_dir=export_dir,
        )
        self._events: list[WatcherEvent] = []

    @property
    def events(self) -> list[WatcherEvent]:
        return list(self._events)

    @property
    def halt_detected(self) -> bool:
        return has_halt_event(self._events)

    async def run(self) -> list[WatcherEvent]:
        self._events = await self._monitor.run()
        return self._events

    async def cancel(self) -> None:
        await self._monitor.cancel()

    async def final_check(self) -> None:
        await self._monitor.final_check()
