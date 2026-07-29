"""Autonomous Monitor Daemon — long-running asyncio monitor for live equity streaming.

This module provides:

- **MonitorConfig**: Dataclass holding daemon configuration, loadable from YAML
  with environment variable overrides (``AUTONOMOUS_MONITOR_*``).
- **AutonomousMonitorDaemon**: (Phase 2) Persistent asyncio loop.
- **NotifierDispatcher**: (Phase 2) Severity→channel routing.
- **AutoActionExecutor**: (Phase 2) Threshold-breach auto-actions.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Any

import yaml


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
