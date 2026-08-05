"""Tests for the MetaGuardian live feed and STREAM_LOST hold — REQ-41, REQ-40.

Verifies ``AutonomousMonitorDaemon.stream_live(campaign_id)`` delivers live
demo-account equity/positions to the MetaGuardian live evaluator (REQ-41) while
heartbeat/metrics continue, and that a lost stream enters a STREAM_LOST hold
where no live-based state transition can occur (fail-closed, REQ-40 scenario
2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.agents.autonomous_monitor import (
    AutoActionExecutor,
    AutonomousMonitorDaemon,
    MonitorConfig,
    NotifierDispatcher,
)
from quantlab.agents.monitoring_agent import MonitoringAgent
from quantlab.knowledge.store import TimeSeriesStore
from quantlab.readers.models import EquityPoint


def _point(equity: float) -> EquityPoint:
    return EquityPoint(timestamp=datetime.now(timezone.utc), equity=equity)


def _daemon(
    *,
    stream_fn: Any,
    max_retries: int = 2,
    heartbeat_interval: int = 999,
) -> AutonomousMonitorDaemon:
    """Build a daemon with injected fakes and a scripted feed."""
    config = MonitorConfig(
        strategy_id="camp-live",
        compute_interval=999,
        heartbeat_interval=heartbeat_interval,
        stream_timeout=999,
        knowledge_root="/tmp",
        max_retries=max_retries,
    )
    daemon = AutonomousMonitorDaemon(
        config,
        agent=MagicMock(spec=MonitoringAgent),
        store=MagicMock(spec=TimeSeriesStore),
        dispatcher=MagicMock(spec=NotifierDispatcher),
        executor=MagicMock(spec=AutoActionExecutor),
    )
    daemon._reconnect_base = 0.001  # keep retries fast in tests
    daemon._get_stream = stream_fn  # type: ignore[method-assign]
    return daemon


def _feed(values: list[float], *, fail: bool = False):
    """Return an injectable ``_get_stream`` yielding/raising as scripted."""

    async def stream(_campaign_id: str | None = None):
        if fail:
            raise ConnectionError("simulated stream loss")
        for v in values:
            yield _point(v)

    return stream


class TestStreamLiveFeed:
    """REQ-41 scenario 1: demo feed streamed to MetaGuardian."""

    @pytest.mark.asyncio
    async def test_stream_live_delivers_equity_to_metaguardian(self) -> None:
        """GIVEN a live feed of equity points
        WHEN stream_live(campaign_id) consumes it
        THEN every point is delivered to the MetaGuardian evaluator.
        """
        received: list[EquityPoint] = []
        daemon = _daemon(stream_fn=_feed([100.0, 101.0, 99.0]))
        daemon.set_live_evaluator(lambda p: received.append(p))

        consumed = [p async for p in daemon.stream_live("camp-live-1")]

        assert len(received) == 3
        assert [p.equity for p in received] == [100.0, 101.0, 99.0]
        assert [p.equity for p in consumed] == [100.0, 101.0, 99.0]

    @pytest.mark.asyncio
    async def test_stream_live_keeps_heartbeat_metrics(self) -> None:
        """GIVEN a running feed
        WHEN stream_live runs
        THEN heartbeat/metrics continue as before (REQ-41).
        """
        store = MagicMock(spec=TimeSeriesStore)
        daemon = _daemon(stream_fn=_feed([100.0, 101.0]), heartbeat_interval=0)
        daemon._store = store  # type: ignore[assignment]

        async for _ in daemon.stream_live("camp-live-1"):
            pass

        assert store.append_heartbeat.called

    @pytest.mark.asyncio
    async def test_new_stream_releases_prior_hold(self) -> None:
        """GIVEN a prior STREAM_LOST hold
        WHEN a fresh stream_live starts
        THEN evaluation resumes (hold is per-stream, not sticky).
        """
        daemon = _daemon(stream_fn=_feed([100.0, 101.0]))
        daemon._hold_live_eval()
        assert daemon.live_eval_held is True

        async for _ in daemon.stream_live("camp-live-1"):
            pass

        assert daemon.live_eval_held is False
        assert daemon.stream_state == "connected"


class TestStreamLostHold:
    """REQ-40 scenario 2: no stream → STREAM_LOST hold, no live transition."""
    @pytest.mark.asyncio
    async def test_stream_lost_holds_and_never_evaluates(self) -> None:
        """GIVEN the live stream is unavailable beyond max retries
        WHEN stream_live runs
        THEN a STREAM_LOST alert fires, live evaluation holds, and no
        live-based state transition occurs.
        """
        store = MagicMock(spec=TimeSeriesStore)
        received: list[EquityPoint] = []
        daemon = _daemon(stream_fn=_feed([], fail=True), max_retries=0)
        daemon._store = store  # type: ignore[assignment]
        daemon.set_live_evaluator(lambda p: received.append(p))

        consumed = [p async for p in daemon.stream_live("camp-live-1")]

        assert daemon.stream_state == "STREAM_LOST"
        assert daemon.live_eval_held is True
        assert received == []  # evaluator never called → no transition
        assert consumed == []
        assert store.append_alert.called
        alert = store.append_alert.call_args[0][0]
        assert alert["type"] == "STREAM_LOST"

    @pytest.mark.asyncio
    async def test_held_daemon_does_not_deliver_to_evaluator(self) -> None:
        """GIVEN a held stream
        WHEN a live point arrives
        THEN it is not delivered to the evaluator — no transition possible.
        """
        received: list[EquityPoint] = []
        daemon = _daemon(stream_fn=_feed([100.0]))
        daemon._hold_live_eval()
        daemon.set_live_evaluator(lambda p: received.append(p))

        await daemon._deliver_live_point(_point(100.0))

        assert received == []
        assert daemon.live_eval_held is True

    @pytest.mark.asyncio
    async def test_reconnect_exhaustion_holds_live_eval(self) -> None:
        """GIVEN max reconnect retries exceeded
        WHEN the reconnect boundary fires
        THEN the daemon enters the STREAM_LOST hold (fail-closed).
        """
        daemon = _daemon(stream_fn=_feed([], fail=True), max_retries=0)

        ok = await daemon._reconnect()

        assert ok is False
        assert daemon.stream_state == "STREAM_LOST"
        assert daemon.live_eval_held is True


class TestFeedToLiveEval:
    """REQ-40/41 wiring: daemon feed → evaluate_live → DEFENSIVE + feedback."""

    @pytest.mark.asyncio
    async def test_daemon_feed_drives_defensive_via_evaluate_live(self) -> None:
        """GIVEN a live feed breaching 10% drawdown
        WHEN the daemon streams it into the evaluate_live evaluator
        THEN a DEFENSIVE evaluation with a feedback record results
        (REQ-40 scenario 1 through the REQ-41 feed).
        """
        from quantlab.guardian.live import evaluate_live
        from quantlab.guardian.models import PortfolioState

        evaluations: list[Any] = []
        window: list[EquityPoint] = []

        def evaluator(point: EquityPoint) -> None:
            window.append(point)
            if len(window) >= 3:
                evaluations.append(
                    evaluate_live(list(window), campaign_id="camp-wired")
                )

        daemon = _daemon(stream_fn=_feed([100.0, 100.0, 88.0]))
        daemon.set_live_evaluator(evaluator)

        async for _ in daemon.stream_live("camp-wired"):
            pass

        assert len(evaluations) == 1
        result = evaluations[0]
        assert result.state == PortfolioState.DEFENSIVE
        assert result.transitioned is True
        assert result.feedback is not None
        assert result.feedback.campaign_id == "camp-wired"
