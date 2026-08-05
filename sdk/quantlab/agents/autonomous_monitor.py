"""Autonomous Monitor Daemon — long-running asyncio monitor for live equity streaming.

This module provides:

- **MonitorConfig**: Dataclass holding daemon configuration, loadable from YAML
  with environment variable overrides (``AUTONOMOUS_MONITOR_*``).
- **NotifierDispatcher**: Severity→channel routing with failure tolerance.
- **AutoActionExecutor**: Threshold-breach auto-actions (stop, reduce, re-optimize).
- **AutonomousMonitorDaemon**: (Phase 2) Persistent asyncio loop.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable

import yaml

from quantlab.agents.monitoring_agent import MonitoringAgent
from quantlab.gates.notifiers import (
    EmailNotifier,
    Notifier,
    SlackNotifier,
    WebhookNotifier,
)
from quantlab.knowledge.store import TimeSeriesStore
from quantlab.readers.models import EquityPoint
from quantlab.readers.result_reader import ResultReader


logger = logging.getLogger(__name__)

# ── Environment variable prefix ───────────────────────────────────────────────

_ENV_PREFIX = "AUTONOMOUS_MONITOR_"

# ── Env-var mapping (module-level, NOT a dataclass field) ─────────────────────

_ENV_MAP: dict[str, str] = {
    "drawdown_threshold": "DRAWDOWN_THRESHOLD",
    "sharpe_degradation_pct": "SHARPE_DEGRADATION_PCT",
    "compute_interval": "COMPUTE_INTERVAL",
    "stream_timeout": "STREAM_TIMEOUT",
    "heartbeat_interval": "HEARTBEAT_INTERVAL",
    "max_retries": "MAX_RETRIES",
    "knowledge_root": "KNOWLEDGE_ROOT",
}

# ── Config ────────────────────────────────────────────────────────────────────


@dataclass
class MonitorConfig:
    """Configuration for the autonomous monitor daemon.

    Load from YAML::

        cfg = MonitorConfig.from_yaml("config.yaml")

    Mutable fields can be overridden at construction time or via environment
    variables prefixed with ``AUTONOMOUS_MONITOR_`` (e.g.
    ``AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD=0.20``).

    Attributes:
        strategy_id: Strategy identifier (required).
        drawdown_threshold: Max drawdown fraction before alert (default 0.15).
        sharpe_degradation_pct: Sharpe ratio degradation fraction before
            alert (default 0.4).
        compute_interval: Seconds between metric/regime computation cycles
            (default 60).
        stream_timeout: Seconds without stream data before reconnect attempt
            (default 60).
        heartbeat_interval: Seconds between heartbeat emissions
            (default 30).
        max_retries: Maximum consecutive stream reconnect attempts before
            error state (default 5).
        knowledge_root: Path to the Knowledge Lake root directory
            (default ``"knowledge"``).
        notifiers: Dict mapping notifier name → config dict
            (default ``{}``).
    """

    strategy_id: str
    drawdown_threshold: float = 0.15
    sharpe_degradation_pct: float = 0.4
    compute_interval: int = 60
    stream_timeout: int = 60
    heartbeat_interval: int = 30
    max_retries: int = 5
    knowledge_root: str = "knowledge"
    notifiers: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Apply ``AUTONOMOUS_MONITOR_*`` env-var overrides after init."""
        self._apply_env_overrides()

    # ── YAML loading ────────────────────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: str) -> MonitorConfig:
        """Load config from a YAML file, then apply env-var overrides.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            A new ``MonitorConfig`` instance with YAML values + env overrides.
        """
        with open(path, "r") as f:
            data: dict[str, Any] = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"YAML file {path} does not contain a mapping")

        # Build from YAML data (unknown keys are ignored)
        known_keys = {
            "strategy_id",
            "drawdown_threshold",
            "sharpe_degradation_pct",
            "compute_interval",
            "stream_timeout",
            "heartbeat_interval",
            "max_retries",
            "knowledge_root",
            "notifiers",
        }
        kwargs: dict[str, Any] = {}
        for key in known_keys:
            if key in data:
                kwargs[key] = data[key]

        cfg = cls(**kwargs)
        cfg._apply_env_overrides()
        return cfg

    # ── Env override ────────────────────────────────────────────────────────────

    def _apply_env_overrides(self) -> None:
        """Override config fields from ``AUTONOMOUS_MONITOR_*`` env vars.

        Each field in ``_ENV_MAP`` is checked for a matching environment
        variable. If present and parseable, the env value wins.
        """
        for attr, suffix in _ENV_MAP.items():
            env_key = _ENV_PREFIX + suffix
            raw = os.environ.get(env_key)
            if raw is None:
                continue

            current = getattr(self, attr)
            try:
                if isinstance(current, bool):
                    parsed = raw.lower() in ("true", "1", "yes")
                elif isinstance(current, int):
                    parsed = int(raw)
                elif isinstance(current, float):
                    parsed = float(raw)
                else:
                    parsed = raw
                setattr(self, attr, parsed)
            except (ValueError, TypeError):
                logger.warning(
                    "Failed to parse env %s='%s' as %s — keeping default",
                    env_key,
                    raw,
                    type(current).__name__,
                )


# ── Notifier severity→channel routing ───────────────────────────────────────

_SEVERITY_ROUTES: dict[str, tuple[str, ...]] = {
    "CRITICAL": ("slack", "email", "webhook"),
    "WARNING": ("slack", "webhook"),
    "INFO": (),
}


class NotifierDispatcher:
    """Route alerts to notifier channels based on severity.

    Each severity level maps to a set of channel names (defined in
    ``_SEVERITY_ROUTES``). Only channels that have a configured notifier
    instance receive the alert. If a notifier's ``send()`` raises, the
    exception is logged at ``WARNING`` and dispatch continues to the next
    channel — a notification failure MUST never block the daemon loop.

    Usage::

        dispatcher = NotifierDispatcher(notifiers={
            "slack": SlackNotifier(webhook_url="..."),
            "email": EmailNotifier(...),
        })
        await dispatcher.dispatch(alert_dict)
    """

    def __init__(
        self,
        notifiers: dict[str, Notifier] | None = None,
    ) -> None:
        """Initialise with optional pre-built notifier instances.

        Args:
            notifiers: Dict mapping channel name → ``Notifier`` instance.
                When ``None``, defaults to an empty dict (log-only mode).
        """
        self._notifiers: dict[str, Notifier] = notifiers or {}

    # ── Public API ──────────────────────────────────────────────────────────

    async def dispatch(self, alert: dict[str, Any]) -> None:
        """Route *alert* to all notifiers matching its severity.

        Args:
            alert: Dict with at least keys ``severity``, ``message``,
                ``type``, ``strategy_id``. The full alert dict is forwarded
                to each notifier's ``send()`` as keyword arguments.
        """
        severity = alert.get("severity", "INFO")
        channels = _SEVERITY_ROUTES.get(severity, ())

        for channel in channels:
            notifier = self._notifiers.get(channel)
            if notifier is None:
                continue
            try:
                await notifier.send(alert.get("message", ""), **alert)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "NotifierDispatcher: %s failed for alert %s — continuing",
                    channel,
                    alert.get("type", "unknown"),
                    exc_info=True,
                )


# ── Auto-action executor ────────────────────────────────────────────────────

_ALERT_ACTION_MAP: dict[str, str] = {
    ("DRAWDOWN_BREACH", "CRITICAL"): "stop_strategy",
    ("REGIME_SHIFT", "WARNING"): "reduce_position",
    ("SHARPE_DEGRADATION", "WARNING"): "re_optimize",
}


class AutoActionExecutor:
    """Execute configurable auto-actions when threshold-breach alerts fire.

    Three actions are supported:

    - **stop_strategy**: Triggered by ``DRAWDOWN_BREACH`` (CRITICAL). Emits
      a ``STRATEGY_STOPPED`` event.
    - **reduce_position**: Triggered by ``REGIME_SHIFT`` (WARNING). Logs a
      50% position reduction request.
    - **re_optimize**: Triggered by ``SHARPE_DEGRADATION`` (WARNING). Logs a
      re-optimisation request.

    Each action MAY be enabled per strategy via the *enabled_actions* dict.
    Executed actions are persisted to the ``TimeSeriesStore`` as alert events.

    The actual strategy-control integration (MQTT/SQX API/CLI) is deferred —
    see design's open questions. Phase 2 implementation logs the action and
    records the event, but does NOT invoke external strategy control.
    """

    def __init__(
        self,
        config: MonitorConfig,
        store: TimeSeriesStore,
        *,
        enabled_actions: dict[str, bool] | None = None,
    ) -> None:
        """Initialise the executor.

        Args:
            config: Daemon configuration (provides ``strategy_id``).
            store: Time-series store for persisting action events.
            enabled_actions: Dict mapping action name → enabled flag.
                Defaults to all three actions enabled.
        """
        self._config = config
        self._store = store
        if enabled_actions is None:
            enabled_actions = {
                "stop_strategy": True,
                "reduce_position": True,
                "re_optimize": True,
            }
        self._enabled_actions = enabled_actions

    # ── Public API ──────────────────────────────────────────────────────────

    async def execute(self, alert: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute auto-actions for *alert* based on type/severity.

        Args:
            alert: Dict with at least ``type``, ``severity``,
                ``strategy_id``.

        Returns:
            List of action-result dicts, one per triggered action.
            Empty list when no action maps to the alert or the action
            is disabled.
        """
        alert_key = (alert.get("type", ""), alert.get("severity", ""))
        action = _ALERT_ACTION_MAP.get(alert_key)
        if action is None or not self._enabled_actions.get(action, False):
            return []

        result = await self._dispatch_action(action, alert)
        return [result]

    # ── Internal ────────────────────────────────────────────────────────────

    async def _dispatch_action(
        self,
        action: str,
        alert: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single action and persist the event.

        Args:
            action: Action name (``stop_strategy``, ``reduce_position``,
                or ``re_optimize``).
            alert: Original alert that triggered the action.

        Returns:
            Action result dict with ``action``, ``strategy_id``,
            ``status``, and action-specific fields.
        """
        strategy_id = alert.get("strategy_id", self._config.strategy_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        result: dict[str, Any] = {
            "action": action,
            "strategy_id": strategy_id,
            "status": "dispatched",
            "triggered_by": alert.get("type", "unknown"),
            "timestamp": now_iso,
        }

        if action == "stop_strategy":
            result["type"] = "STRATEGY_STOPPED"
        elif action == "reduce_position":
            result["reduction_pct"] = 50
        elif action == "re_optimize":
            result["type"] = "RE_OPTIMIZATION_REQUESTED"

        # Persist action event as an alert in the time-series store
        # Serialise details to JSON for TEXT column compatibility
        import json

        self._store.append_alert({
            "timestamp": now_iso,
            "type": result.get("type", action.upper()),
            "severity": alert.get("severity", "WARNING"),
            "strategy_id": strategy_id,
            "message": f"Auto-action '{action}' dispatched",
            "details": json.dumps(result),
        })

        logger.info("AutoActionExecutor: %s for %s — %s", action, strategy_id, result["status"])
        return result


# ── Daemon ───────────────────────────────────────────────────────────────────


class AutonomousMonitorDaemon:
    """Persistent asyncio daemon for live equity streaming, rolling metrics,
    regime detection, alert dispatch, and auto-actions.

    Wraps ``MonitoringAgent``'s metric/regime/alert functions in a persistent
    loop consuming ``ResultReader.stream_live()``. Alert routing via
    ``NotifierDispatcher`` and auto-actions via ``AutoActionExecutor``.
    Time-series data persisted to SQLite via ``TimeSeriesStore``.

    Usage::

        cfg = MonitorConfig(strategy_id="my_strat")
        daemon = AutonomousMonitorDaemon(cfg)
        await daemon.start()
        # … let it run …
        await daemon.stop()
        print(daemon.status())
    """

    def __init__(
        self,
        config: MonitorConfig,
        *,
        agent: MonitoringAgent | None = None,
        store: TimeSeriesStore | None = None,
        dispatcher: NotifierDispatcher | None = None,
        executor: AutoActionExecutor | None = None,
    ) -> None:
        """Initialise the daemon.

        Args:
            config: Daemon configuration.
            agent: Optional ``MonitoringAgent`` instance. Created from
                config when not provided.
            store: Optional ``TimeSeriesStore`` instance. Created from
                config when not provided.
            dispatcher: Optional ``NotifierDispatcher`` instance. Created
                from config when not provided.
            executor: Optional ``AutoActionExecutor`` instance. Created
                from config + store when not provided.
        """
        self._config = config
        self._state: str = "stopped"
        self._task: asyncio.Task[None] | None = None
        self._start_time: float = 0.0
        self._last_heartbeat: float = 0.0
        self._missed_heartbeats: int = 0
        self._latest_metrics: dict[str, Any] = {}
        self._equity_buffer: list[EquityPoint] = []
        self._last_compute: float = 0.0
        self._last_point_time: float = 0.0
        self._stream_retries: int = 0
        self._loop_exception: Exception | None = None

        # MetaGuardian live feed state (REQ-41 / REQ-40)
        self._stream_state: str = "connected"  # "connected" | "STREAM_LOST"
        self._live_eval_held: bool = False
        self._live_evaluator: Callable[[EquityPoint], Any] | None = None
        self._live_points: list[EquityPoint] = []

        # Backoff base for reconnection (per spec: 5s). Exposed for test injection.
        self._reconnect_base: float = 5.0

        # Create MonitoringAgent
        self._agent = agent or MonitoringAgent(
            drawdown_threshold=config.drawdown_threshold,
            sharpe_degradation_pct=config.sharpe_degradation_pct,
            knowledge_root=config.knowledge_root,
        )

        # Create TimeSeriesStore
        if store is not None:
            self._store = store
        else:
            db_dir = os.path.join(config.knowledge_root, "timeseries")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "monitor.db")
            self._store = TimeSeriesStore(db_path)

        # Create Dispatcher and Executor
        if dispatcher is not None:
            self._dispatcher = dispatcher
        else:
            self._dispatcher = NotifierDispatcher(
                notifiers=self._build_notifiers(config.notifiers),
            )

        self._executor = executor or AutoActionExecutor(config, self._store)

        # Store health tracking
        self._store_unhealthy = False

        # Health check for store
        from quantlab.robustness.knowledge_health import (
            HealthStatus,
            KnowledgeStoreHealthCheck,
        )

        self._health_check = KnowledgeStoreHealthCheck(self._store)

    # ── Lifecycle ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the daemon background loop.

        Idempotent — safe to call multiple times. Creates an ``asyncio.Task``
        running ``_run_loop()``.
        """
        if self._state == "running":
            return
        self._state = "running"
        self._start_time = time.time()
        self._last_compute = time.time()
        self._last_heartbeat = time.time()
        self._last_point_time = time.time()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("AutonomousMonitorDaemon: started for %s", self._config.strategy_id)

    async def stop(self) -> None:
        """Stop the daemon gracefully.

        Idempotent — safe to call when already stopped. Cancels the background
        task and waits for completion (up to 5s timeout).
        """
        if self._state == "stopped":
            return
        self._state = "stopped"
        if self._task is not None:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._task = None
        logger.info("AutonomousMonitorDaemon: stopped for %s", self._config.strategy_id)

    def status(self) -> dict[str, Any]:
        """Return current daemon status.

        Returns:
            Dict with keys: ``state``, ``uptime_seconds``,
            ``last_heartbeat``, ``metrics_count``, ``error``.
        """
        uptime = time.time() - self._start_time if self._start_time > 0 else 0.0
        return {
            "state": self._state,
            "uptime_seconds": round(uptime, 2),
            "last_heartbeat": round(self._last_heartbeat, 2),
            "metrics_count": len(self._latest_metrics),
            "error": str(self._loop_exception) if self._loop_exception else None,
            "store_healthy": not self._store_unhealthy,
            "store_health": "healthy" if not self._store_unhealthy else "unhealthy",
            "stream_state": self._stream_state,
            "live_eval_held": self._live_eval_held,
        }

    # ── Internal: stream factory (injectable for testing) ───────────────────

    def _get_stream(
        self,
        campaign_id: str | None = None,
    ) -> AsyncGenerator[EquityPoint, None]:
        """Create a live equity stream for the configured strategy."""
        return ResultReader.stream_live(
            campaign_id=campaign_id or self._config.strategy_id,
        )

    # ── MetaGuardian live feed (REQ-41 / REQ-40) ────────────────────────────

    @property
    def stream_state(self) -> str:
        """Live-feed state: ``"connected"`` or ``"STREAM_LOST"`` (REQ-40)."""
        return self._stream_state

    @property
    def live_eval_held(self) -> bool:
        """True while live MetaGuardian evaluation is held (REQ-40 s2)."""
        return self._live_eval_held

    def set_live_evaluator(
        self,
        evaluator: Callable[[EquityPoint], Any] | None,
    ) -> None:
        """Register the MetaGuardian live evaluator (REQ-40).

        The evaluator receives each live equity point once the daemon is
        connected. It may be sync or async. While the stream is held
        (STREAM_LOST) the evaluator is never invoked.
        """
        self._live_evaluator = evaluator

    def _hold_live_eval(self) -> None:
        """Enter the STREAM_LOST hold: no live-based transition may occur."""
        self._stream_state = "STREAM_LOST"
        self._live_eval_held = True

    def _release_live_eval(self) -> None:
        """Resume live evaluation (a fresh stream is available)."""
        self._stream_state = "connected"
        self._live_eval_held = False

    async def _deliver_live_point(self, point: EquityPoint) -> None:
        """Route a live equity point to the MetaGuardian feed (REQ-41).

        The raw point is buffered for the archive statistics feed. It is
        forwarded to the live evaluator only while connected — during a
        STREAM_LOST hold no live data reaches MetaGuardian, so no live-based
        state transition can occur (fail-closed, REQ-40 scenario 2).
        """
        self._live_points.append(point)
        if self._live_evaluator is None or self._live_eval_held:
            return
        result = self._live_evaluator(point)
        if inspect.isawaitable(result):
            await result

    async def stream_live(
        self,
        campaign_id: str,
    ) -> AsyncGenerator[EquityPoint, None]:
        """Stream live demo-account equity/positions to MetaGuardian (REQ-41).

        Consumes the account feed for *campaign_id*, delivers every point to
        the MetaGuardian live evaluator (REQ-40), and yields it to the caller.
        Heartbeat/metrics continue as before (REQ-41). When the stream is lost
        beyond ``max_retries``, a ``STREAM_LOST`` alert is dispatched and live
        evaluation holds — no live-based state transition occurs (fail-closed,
        REQ-40 scenario 2).

        Yields:
            EquityPoint — each point consumed from the account feed.
        """
        self._release_live_eval()
        while True:
            try:
                async for point in self._get_stream(campaign_id):
                    await self._on_point(point)
                    await self._maybe_heartbeat()
                    yield point
            except (ConnectionError, OSError) as exc:
                logger.warning("stream_live: %s", exc)
                if not await self._reconnect():
                    return
            else:
                return

    # ── Internal: main loop ─────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """Main daemon loop: consume stream, compute metrics, dispatch alerts."""
        try:
            while self._state == "running":
                try:
                    stream = self._get_stream()
                    async for point in stream:
                        if self._state != "running":
                            break
                        await self._on_point(point)

                        # Reset stall / retry tracking on successful point
                        self._last_point_time = time.time()
                        self._stream_retries = 0

                        # Periodic compute cycle
                        await self._maybe_compute()

                        # Periodic heartbeat
                        await self._maybe_heartbeat()

                except (ConnectionError, OSError) as exc:
                    logger.warning("Daemon stream error: %s", exc)
                    if not await self._reconnect():
                        break

                # Check heartbeat / compute / health even between stream iterations
                await self._maybe_heartbeat()
                await self._maybe_compute()
                await self._check_health()

                # Brief pause before next stream iteration
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info("Daemon loop cancelled")
            self._state = "stopped"
        except Exception as exc:  # noqa: BLE001
            self._loop_exception = exc
            self._state = "error"
            logger.exception("Daemon loop fatal error: %s", exc)

    async def _on_point(self, point: EquityPoint) -> None:
        """Process a single equity point: buffer it and deliver it to the
        MetaGuardian live feed (REQ-41)."""
        self._equity_buffer.append(point)
        await self._deliver_live_point(point)

    # ── Internal: compute cycle ─────────────────────────────────────────────

    async def _maybe_compute(self) -> None:
        """Run metrics computation if ``compute_interval`` has elapsed."""
        now = time.time()
        if now - self._last_compute < self._config.compute_interval:
            return
        await self._compute_cycle(now)

        # Check store health after compute cycle
        await self._check_store_health()

    async def _compute_cycle(self, now: float) -> None:
        """Execute one computation cycle: metrics → regime → alerts → dispatch."""
        if not self._equity_buffer:
            self._last_compute = now
            return

        equity = list(self._equity_buffer)

        # 1. Rolling metrics
        rolling = self._agent.compute_rolling_metrics(equity)
        self._latest_metrics = rolling

        # 2. Regime detection
        regime_alerts = self._agent.detect_regime_change(rolling)

        # 3. Performance alerts
        perf_alerts = self._agent.check_alerts(rolling, equity)

        # 4. Persist metrics
        self._persist_metrics(now, rolling)

        # 5. Dispatch + persist alerts
        import json

        all_alerts = regime_alerts + perf_alerts
        for alert in all_alerts:
            alert.setdefault("strategy_id", self._config.strategy_id)
            alert.setdefault(
                "timestamp", datetime.now(timezone.utc).isoformat()
            )
            alert.setdefault("message", alert.get("type", "alert"))

            # Serialise details to string for SQLite TEXT column
            details = alert.get("details")
            if details is not None and not isinstance(details, str):
                alert["details"] = json.dumps(details)

            await self._dispatcher.dispatch(alert)
            self._store.append_alert(alert)
            await self._executor.execute(alert)

        self._last_compute = now
        logger.debug(
            "Compute cycle: %d metrics, %d alerts",
            len(rolling),
            len(all_alerts),
        )

    def _persist_metrics(
        self, now: float, rolling: dict[str, Any]
    ) -> None:
        """Persist latest metric values to time-series store."""
        for metric_name, data in rolling.items():
            values = data.get("values", [])
            if values:
                self._store.append_metrics(
                    self._config.strategy_id,
                    now,
                    {metric_name: float(values[-1])},
                )

    # ── Internal: health check ──────────────────────────────────────────────

    async def _check_health(self) -> None:
        """Check if heartbeats have been missed (3-miss stale detection).

        When ``_last_heartbeat`` is older than 3× ``heartbeat_interval``
        despite the loop running, the daemon increments ``_missed_heartbeats``.
        At 3+ missed, a ``DAEMON_FAILURE`` CRITICAL alert is dispatched once.
        This detects cases where ``_maybe_heartbeat`` is called but the
        underlying storage or clock is stalled.
        """
        now = time.time()
        interval = self._config.heartbeat_interval
        threshold = interval * 3  # 3-miss stale threshold

        if now - self._last_heartbeat > threshold and self._state == "running":
            self._missed_heartbeats += 1
            if self._missed_heartbeats == 3:
                alert: dict[str, Any] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "DAEMON_FAILURE",
                    "severity": "CRITICAL",
                    "strategy_id": self._config.strategy_id,
                    "message": (
                        f"3 consecutive heartbeats missed — daemon may be stalled"
                    ),
                    "details": {
                        "last_heartbeat": self._last_heartbeat,
                        "missed_count": self._missed_heartbeats,
                    },
                }
                self._store.append_alert(alert)
                await self._dispatcher.dispatch(alert)
                logger.critical("Health check: %s", alert["message"])

    # ── Internal: store health check ──────────────────────────────────

    async def _check_store_health(self) -> None:
        """Check TimeSeriesStore health and dispatch alert if unhealthy."""
        result = await self._health_check.check()
        if result.status == HealthStatus.UNHEALTHY:
            self._store_unhealthy = True
            alert: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "STORE_UNHEALTHY",
                "severity": "CRITICAL",
                "strategy_id": self._config.strategy_id,
                "message": f"TimeSeriesStore unhealthy: {result.reason}",
                "details": {"reason": result.reason},
            }
            await self._dispatcher.dispatch(alert)
            self._store.append_alert(alert)
            logger.critical("Store health check failed: %s", result.reason)
        else:
            self._store_unhealthy = False

    # ── Internal: heartbeat ─────────────────────────────────────────────────

    async def _maybe_heartbeat(self) -> None:
        """Emit a heartbeat if ``heartbeat_interval`` has elapsed."""
        now = time.time()
        if now - self._last_heartbeat < self._config.heartbeat_interval:
            return

        self._store.append_heartbeat({
            "timestamp": now,
            "strategy_id": self._config.strategy_id,
            "equity_count": len(self._equity_buffer),
            "alert_count": 0,  # tracked externally in production
        })
        self._last_heartbeat = now
        self._missed_heartbeats = 0
        logger.debug("Heartbeat emitted for %s", self._config.strategy_id)

    # ── Internal: reconnect ─────────────────────────────────────────────────

    async def _reconnect(self) -> bool:
        """Attempt reconnection with exponential backoff.

        Returns:
            ``True`` if the caller should retry the stream, ``False`` when
            ``max_retries`` is exceeded (daemon enters ``error`` state).
        """
        self._stream_retries += 1
        if self._stream_retries > self._config.max_retries:
            logger.error(
                "Max retries (%d) exceeded, entering error state",
                self._config.max_retries,
            )
            self._state = "error"

            # STREAM_LOST hold — no live-based state transition may occur
            self._hold_live_eval()

            # Dispatch STREAM_LOST CRITICAL alert
            alert: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "STREAM_LOST",
                "severity": "CRITICAL",
                "strategy_id": self._config.strategy_id,
                "message": (
                    f"Stream lost after {self._config.max_retries} retries"
                ),
                "details": {"retries": self._stream_retries},
            }
            self._store.append_alert(alert)
            await self._dispatcher.dispatch(alert)
            return False

        delay = self._reconnect_base * (2 ** (self._stream_retries - 1))
        logger.warning(
            "Reconnecting in %.1fs (attempt %d/%d)",
            delay,
            self._stream_retries,
            self._config.max_retries,
        )
        await asyncio.sleep(delay)
        return True

    # ── Internal: notifier construction ─────────────────────────────────────

    @staticmethod
    def _build_notifiers(
        config: dict[str, dict[str, Any]],
    ) -> dict[str, Notifier]:
        """Build notifier instances from configuration dict.

        Args:
            config: Dict mapping channel name → config dict (from
                ``MonitorConfig.notifiers``).

        Returns:
            Dict mapping channel name → ``Notifier`` instance.
        """
        notifiers: dict[str, Notifier] = {}
        for name, cfg in config.items():
            name_lower = name.lower()
            try:
                if name_lower == "slack":
                    notifiers[name] = SlackNotifier(
                        webhook_url=cfg["webhook_url"],
                    )
                elif name_lower == "email":
                    notifiers[name] = EmailNotifier(
                        smtp_host=cfg["smtp_host"],
                        smtp_port=int(cfg["smtp_port"]),
                        from_addr=cfg["from_addr"],
                        to_addrs=cfg["to_addrs"],
                        username=cfg.get("username"),
                        password=cfg.get("password"),
                    )
                elif name_lower == "webhook":
                    notifiers[name] = WebhookNotifier(
                        url=cfg["url"],
                    )
                else:
                    logger.warning(
                        "Unknown notifier type '%s' — skipping", name
                    )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to build notifier '%s' — skipping", name
                )
        return notifiers
